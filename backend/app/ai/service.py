import logging,os,re
from difflib import SequenceMatcher
from typing import Any
from pydantic import ValidationError
from .base import AIProvider
from .demo_provider import DemoProvider
from .gemini_provider import GeminiProvider
from .schemas import NormalizedTicket,ExtractedTicketFields,ClassificationSuggestion,GroundedResolution,InvestigationSuggestions,HistoricalSummary,ExplanationOutput,HandoverOutput,KBDraftOutput

log=logging.getLogger("nexus.ai")
VALID_CATEGORIES={"Authentication","Performance","Application Error","Network","Database","Access / Permissions","Integration","Batch Processing"}

def configured_provider()->AIProvider:
    demo=os.getenv("DEMO_MODE","true").lower()=="true";key=os.getenv("GEMINI_API_KEY","").strip();selected=os.getenv("AI_PROVIDER","gemini").lower()
    if demo or not key or selected!="gemini":
        reason="demo_mode" if demo else "missing_api_key" if not key else "unsupported_provider"
        log.info("provider=local model=deterministic fallback=%s",reason);return DemoProvider()
    return GeminiProvider(key,model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),temperature=float(os.getenv("AI_TEMPERATURE","0.2")),fallback_model=os.getenv("GEMINI_FALLBACK_MODEL","gemini-3.5-flash-lite"))

class AIService:
    def __init__(self,provider:AIProvider|None=None):self.provider=provider or configured_provider()
    @property
    def enhanced(self):return self.provider.name=="gemini"

    def understand_ticket(self,payload:dict[str,Any],local:dict[str,Any])->dict[str,Any]:
        local_normalized={"normalized_description":local["normalized_description"],"application":None if local["application"]=="Unknown" else local["application"],"symptoms":local["symptoms"],"error_codes":[] if local["error_text"]=="Unknown" else [local["error_text"]],"technical_terms":local["technical_terms"]}
        local_extracted={"application":local_normalized["application"],"affected_function":None,"symptoms":local["symptoms"],"error_message":None if local["error_text"]=="Unknown" else local["error_text"],"technical_terms":local["technical_terms"],"environment":None}
        local_classification={"category":local["category"],"subcategory":local["subcategory"],"supporting_terms":local.get("matched_terms",[]),"confidence":local["confidence"]}
        if not self.enhanced:return {"analysis_mode":"local","normalized":local_normalized,"extracted_fields":local_extracted,"classification":local_classification,"fallback_message":None}
        context={**payload,"local_normalized":local_normalized,"local_extracted":local_extracted,"local_classification":local_classification}
        try:
            normalized=NormalizedTicket.model_validate(self.provider.normalize_ticket(context)).model_dump()
            extracted=ExtractedTicketFields.model_validate(self.provider.extract_ticket_fields(context)).model_dump()
            suggested=ClassificationSuggestion.model_validate(self.provider.classify_ticket({**context,"normalized":normalized,"extracted":extracted})).model_dump()
            if suggested["category"] not in VALID_CATEGORIES:
                log.warning("provider=%s invalid_category=%s fallback=local_classification",self.provider.name,suggested["category"]);suggested=local_classification
            return {"analysis_mode":"gemini","normalized":normalized,"extracted_fields":extracted,"classification":suggested,"fallback_message":None}
        except Exception as exc:
            log.warning("provider=%s fallback=local reason=%s",self.provider.name,type(exc).__name__)
            return {"analysis_mode":"local","normalized":local_normalized,"extracted_fields":local_extracted,"classification":local_classification,"fallback_message":"Enhanced analysis unavailable. Local analysis was used."}

    @staticmethod
    def _norm(value:str):return re.sub(r"[^a-z0-9]+"," ",value.lower()).strip()
    @staticmethod
    def _safe_summary(candidate:str,source:Any,fallback:str):
        source_words=set(re.findall(r"[a-z0-9_]+",str(source).lower()))|{"historically","effective","less","seen","similar","cases","limited","evidence","suggests","possible","relationship","supporting","recommendation","ticket","knowledge","dependency","change","and","the","in","a","is","was","of","to","from"}
        meaningful={x for x in re.findall(r"[a-z0-9_]+",candidate.lower()) if len(x)>3}
        return candidate if meaningful<=source_words else fallback
    def draft_resolution(self,ticket:dict[str,Any],matches:list[dict[str,Any]],reliable:bool,local_steps:list[str],local_traced:list[dict[str,Any]])->dict[str,Any]:
        if not reliable:return {"steps":[],"traced":[],"sources":[],"summary":"","mode":"skipped"}
        if not self.enhanced:return {"steps":local_steps,"traced":local_traced,"sources":list(dict.fromkeys(x["source_kb_id"] for x in local_traced)),"summary":"","mode":"local"}
        allowed={}
        scores={m["kb_id"]:m["score"] for m in matches}
        for match in matches:
            for index,step in enumerate(match["article"]["resolution_steps"],1):allowed[(match["kb_id"],f"Resolution Step {index}")]=step
        evidence={"ticket":ticket,"articles":[{"kb_id":m["kb_id"],"title":m["title"],"score":m["score"],"allowed_resolution_steps":[{"step":s,"source_section":f"Resolution Step {i}"} for i,s in enumerate(m["article"]["resolution_steps"],1)]} for m in matches]}
        try:result=GroundedResolution.model_validate(self.provider.draft_grounded_resolution(evidence))
        except Exception as exc:
            log.warning("provider=%s grounding_fallback=local reason=%s",self.provider.name,type(exc).__name__);return {"steps":local_steps,"traced":local_traced,"sources":list(dict.fromkeys(x["source_kb_id"] for x in local_traced)),"summary":"","mode":"local"}
        traced=[]
        for item in result.resolution_steps:
            original=allowed.get((item.source_kb_id,item.source_section))
            if not original:continue
            ratio=SequenceMatcher(None,self._norm(item.step),self._norm(original)).ratio()
            if ratio<.68:continue
            traced.append({"step":item.step,"source_kb_id":item.source_kb_id,"source_section":item.source_section,"evidence_score":scores[item.source_kb_id]})
        if not traced:return {"steps":[],"traced":[],"sources":[],"summary":"","mode":"rejected"}
        return {"steps":[x["step"] for x in traced],"traced":traced,"sources":list(dict.fromkeys(x["source_kb_id"] for x in traced)),"summary":result.summary,"mode":"gemini"}

    def suggest_investigation_steps(self,ticket:dict[str,Any])->dict[str,Any]:
        application=ticket.get("application") or "the affected application"
        category=ticket.get("category") or "Unknown"
        category_check={
            "Authentication":f"Verify the account is active and review the current session or lockout status for {application} through the approved support console.",
            "Performance":f"Compare the response time in {application} with a known working workflow and record the affected page, filters, and time range.",
            "Application Error":f"Reproduce the issue once in a safe session and capture the complete error, timestamp, and any correlation identifier from {application}.",
            "Network":"Confirm the user's approved network or VPN connection and compare access with a known working endpoint.",
            "Database":"Capture the exact application error and timestamp, then check the approved database or service health dashboard for a matching event.",
            "Access / Permissions":f"Verify the user's approved role and access request status for {application} without changing permissions.",
            "Integration":"Capture the affected endpoint, timestamp, request identifier, and response code, then check the approved integration status page.",
            "Batch Processing":"Record the job identifier, run timestamp, scheduler state, and exact failure message without rerunning the job.",
        }.get(category,f"Capture the exact error, timestamp, affected workflow, and user impact for {application}.")
        local=[
            "Confirm whether the issue affects one user, several users, or the entire service.",
            category_check,
            "Check the approved service-status and recent-change records for events matching the reported time.",
            "If the issue remains unresolved, escalate it with the collected evidence and the safe reproduction steps.",
        ]
        if not self.enhanced:return {"suggestions":local,"mode":"local"}
        try:
            payload={"ticket":ticket,"constraints":{"minimum":2,"maximum":5,"low_risk_only":True}}
            result=InvestigationSuggestions.model_validate(self.provider.suggest_investigation_steps(payload)).model_dump()
        except Exception as exc:
            log.warning("provider=%s investigation_fallback=local reason=%s",self.provider.name,type(exc).__name__);return {"suggestions":local,"mode":"local"}
        forbidden=re.compile(r"\b(delete|drop|truncate|format|reboot|restart|disable|bypass|grant|revoke|deploy|execute|run\s+(?:a\s+)?command|change\s+(?:a\s+)?configuration)\b",re.I)
        suggestions=[]
        for value in result["suggestions"]:
            suggestion=re.sub(r"^\s*(?:[-*]|\d+[.)])\s*","",value).strip()
            if len(suggestion)<18 or suggestion.isdigit() or forbidden.search(suggestion):continue
            if suggestion not in suggestions:suggestions.append(suggestion[:300])
        if len(suggestions)<2:return {"suggestions":local,"mode":"local"}
        return {"suggestions":suggestions[:5],"mode":"gemini"}

    def summarize_history(self,cases:list[dict[str,Any]],local_summary:dict[str,Any]):
        if not self.enhanced:return {**local_summary,"analysis_mode":"local"}
        allowed_success={x for case in cases for x in case.get("successful_steps",[])};allowed_failure={x for case in cases for x in case.get("failed_steps",[])}
        try:result=HistoricalSummary.model_validate(self.provider.summarize_cases({"cases":cases})).model_dump()
        except Exception:return {**local_summary,"analysis_mode":"local"}
        result["summary"]=self._safe_summary(result["summary"],cases,local_summary.get("summary","Historical evidence is limited."))
        result["historically_effective_steps"]=[x for x in result["historically_effective_steps"] if x in allowed_success]
        result["historically_less_effective_steps"]=[x for x in result["historically_less_effective_steps"] if x in allowed_failure]
        result["analysis_mode"]="gemini";return result

    def enhance_handover(self,evidence:dict[str,Any]):
        if not self.enhanced:return {**evidence,"analysis_mode":"local"}
        allowed_attempted=set(evidence.get("already_attempted",{}).get("successful",[])+evidence.get("already_attempted",{}).get("failed",[]));failed=set(evidence.get("already_attempted",{}).get("failed",[]));recommendations=evidence.get("current_recommendation",[]);pending=[evidence.get("pending_action")] if evidence.get("pending_action") else []
        try:result=HandoverOutput.model_validate(self.provider.generate_handover(evidence)).model_dump()
        except Exception:return {**evidence,"analysis_mode":"local"}
        known_evidence=[f"{x['id']} — {round(x['score']*100)}%" for group in evidence.get("evidence",{}).values() for x in group]
        return {**evidence,"llm_handover":{"current_issue":evidence["current_issue"],"status":evidence["ticket_status"],"attempted_steps":[x for x in result["attempted_steps"] if x in allowed_attempted],"failed_steps":[x for x in result["failed_steps"] if x in failed],"current_recommendation":result["current_recommendation"] if result["current_recommendation"] in recommendations else (recommendations[0] if recommendations else ""),"evidence":known_evidence,"pending_actions":[x for x in result["pending_actions"] if x in pending]},"analysis_mode":"gemini"}

    def enhance_explanation(self,evidence:dict[str,Any]):
        if not self.enhanced:return {**evidence,"analysis_mode":"local"}
        try:result=ExplanationOutput.model_validate(self.provider.generate_explanation(evidence)).model_dump()
        except Exception:return {**evidence,"analysis_mode":"local"}
        result["summary"]=self._safe_summary(result["summary"],evidence,"")
        return {**evidence,"narrative":result,"analysis_mode":"gemini"}

    def generate_kb_draft(self,evidence:dict[str,Any]):
        source_cases={c.get("case_id") for c in evidence.get("cases",[])};allowed_steps={x for c in evidence.get("cases",[]) for x in c.get("successful_steps",[])}
        local={"draft":True,"title":evidence.get("suggested_title","Draft Knowledge Article"),"symptoms":evidence.get("symptoms",[]),"prerequisites":[],"resolution_steps":sorted(allowed_steps),"escalation_conditions":[],"source_cases":sorted(source_cases),"analysis_mode":"local"}
        if not self.enhanced:return local
        try:result=KBDraftOutput.model_validate(self.provider.generate_kb_draft(evidence)).model_dump()
        except Exception:return local
        result["resolution_steps"]=[x for x in result["resolution_steps"] if x in allowed_steps];result["source_cases"]=[x for x in result["source_cases"] if x in source_cases];result["draft"]=True;result["analysis_mode"]="gemini";return result

ai_service=AIService()
