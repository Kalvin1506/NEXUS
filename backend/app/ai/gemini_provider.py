import json,logging,time
from typing import Any,Type
import httpx
from pydantic import BaseModel,ValidationError
from .base import AIProvider
from . import prompts
from .schemas import NormalizedTicket,ExtractedTicketFields,ClassificationSuggestion,GroundedResolution,InvestigationSuggestions,HistoricalSummary,ExplanationOutput,HandoverOutput,KBDraftOutput

log=logging.getLogger("nexus.ai")

class GeminiProvider(AIProvider):
    name="gemini"
    def __init__(self,api_key:str,model:str="gemini-2.5-flash",temperature:float=.2,timeout:float=15,fallback_model:str|None=None):
        self.api_key=api_key;self.model=model;self.active_model=model;self.fallback_model=fallback_model;self.temperature=temperature;self.timeout=timeout
    def _generate(self,system:str,payload:dict[str,Any],schema:Type[BaseModel]):
        body={"systemInstruction":{"parts":[{"text":system}]},"contents":[{"role":"user","parts":[{"text":json.dumps(payload,default=str)}]}],"generationConfig":{"temperature":self.temperature,"responseMimeType":"application/json"}}
        last=None;models=[self.active_model]
        if self.fallback_model and self.fallback_model not in models:models.append(self.fallback_model)
        for model in models:
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                started=time.perf_counter()
                try:
                    response=httpx.post(url,headers={"x-goog-api-key":self.api_key},json=body,timeout=self.timeout)
                    response.raise_for_status();raw=response.json()["candidates"][0]["content"]["parts"][0]["text"]
                    result=schema.model_validate_json(raw);self.active_model=model;log.info("provider=%s model=%s latency_ms=%d parsing=success",self.name,model,(time.perf_counter()-started)*1000);return result.model_dump()
                except (httpx.HTTPError,KeyError,IndexError,ValidationError,json.JSONDecodeError) as exc:
                    last=exc;status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
                    log.warning("provider=%s model=%s attempt=%d latency_ms=%d parsing=failure status=%s error=%s",self.name,model,attempt+1,(time.perf_counter()-started)*1000,status,type(exc).__name__)
                    if status==404:break
        raise RuntimeError("Gemini response unavailable or invalid") from last
    def normalize_ticket(self,ticket):return self._generate(prompts.NORMALIZE,ticket,NormalizedTicket)
    def extract_ticket_fields(self,ticket):return self._generate(prompts.EXTRACT,ticket,ExtractedTicketFields)
    def classify_ticket(self,ticket):return self._generate(prompts.CLASSIFY,ticket,ClassificationSuggestion)
    def summarize_cases(self,evidence):return self._generate(prompts.CASES,evidence,HistoricalSummary)
    def draft_grounded_resolution(self,evidence):return self._generate(prompts.RESOLUTION,evidence,GroundedResolution)
    def suggest_investigation_steps(self,ticket):return self._generate(prompts.INVESTIGATION,ticket,InvestigationSuggestions)
    def generate_explanation(self,evidence):return self._generate(prompts.EXPLANATION,evidence,ExplanationOutput)
    def generate_handover(self,evidence):return self._generate(prompts.HANDOVER,evidence,HandoverOutput)
    def generate_kb_draft(self,evidence):return self._generate(prompts.KB_DRAFT,evidence,KBDraftOutput)
