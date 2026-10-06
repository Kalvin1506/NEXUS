from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

def now(): return datetime.now(timezone.utc)

class KnowledgeArticle(BaseModel):
    kb_id:str; title:str; category:str; symptoms:list[str]; cause:str
    prerequisites:list[str]; resolution_steps:list[str]; escalation_conditions:str; tags:list[str]
    last_updated:str="2026-09-15"; usage:int=0; success_feedback:int=0

class HistoricalCase(BaseModel):
    case_id:str; description:str; application:str; category:str; subcategory:str
    troubleshooting_attempts:list[str]; failed_steps:list[str]; successful_steps:list[str]
    final_resolution:str; related_kb:list[str]; technician_notes:str; resolution_time:int; created_at:datetime

class Ticket(BaseModel):
    model_config=ConfigDict(extra="allow")
    ticket_id:str; description:str; normalized_description:str=""; application:str="Unknown"; error_text:str="Unknown"
    symptoms:list[str]=[]; technical_terms:list[str]=[]; category:str="Unknown"; subcategory:str="Unknown"
    classification_confidence:float=0; knowledge_confidence:float=0; historical_confidence:float=0
    status:str="Analyzed"; resolution_status:str="Pending Review"; reliable_match:bool=False
    kb_matches:list[dict[str,Any]]=[]; case_matches:list[dict[str,Any]]=[]; recommended_resolution:list[str]=[]
    source_references:list[str]=[]; analyst_notes:str=""; sla_risk:str="Normal"; sla_reasons:list[str]=[]
    dependency_impact:dict[str,Any]={}; created_at:datetime=Field(default_factory=now); updated_at:datetime=Field(default_factory=now)

class AnalyzeRequest(BaseModel):
    ticket_id:str|None=None; application:str|None=None; description:str; error_message:str|None=None
class TextRequest(BaseModel):
    description:str; application:str|None=None; error_message:str|None=None
class SearchRequest(BaseModel):
    query:str; category:str|None=None; limit:int=3
class ResolutionRequest(BaseModel):
    analyst_notes:str=""; resolution:list[str]|None=None
class TicketUpdate(BaseModel):
    model_config=ConfigDict(extra="allow")
    category:str|None=None; subcategory:str|None=None; application:str|None=None; recommended_resolution:list[str]|None=None
    analyst_notes:str|None=None; resolution_status:str|None=None; status:str|None=None
class Feedback(BaseModel):
    ticket_id:str; feedback_type:str; value:str; target_id:str|None=None; comment:str|None=None

