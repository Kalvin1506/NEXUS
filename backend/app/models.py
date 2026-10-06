from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

def now(): return datetime.now(timezone.utc)

class KnowledgeArticle(BaseModel):
    kb_id:str; title:str; category:str; symptoms:list[str]; cause:str
    prerequisites:list[str]; resolution_steps:list[str]; escalation_conditions:str; tags:list[str]
    last_updated:str="2026-09-15"; usage:int=0; success_feedback:int=0; negative_feedback:int=0
    successful_resolutions:int=0; failed_resolutions:int=0; procedure_tags:list[str]=[]
    step_order:list[str]=[]; conflicts_with:list[str]=[]

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
    traced_resolution:list[dict[str,Any]]=[]
    investigation_suggestions:list[str]=[]; investigation_suggestions_mode:str|None=None
    source_references:list[str]=[]; analyst_notes:str=""; sla_risk:str="Normal"; sla_reasons:list[str]=[]
    dependency_impact:dict[str,Any]={}; timeline:list[dict[str,Any]]=[]; related_cluster_ids:list[str]=[]
    related_changes:list[dict[str,Any]]=[]; resolved_at:datetime|None=None
    analysis_mode:str="local"; analysis_notice:str|None=None
    created_at:datetime=Field(default_factory=now); updated_at:datetime=Field(default_factory=now)

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

class ResolveRequest(BaseModel):
    final_resolution:str
    successful_steps:list[str]=[]
    failed_steps:list[str]=[]
    used_kb_articles:list[str]=[]
    analyst_notes:str=""
    analyst_feedback:str="Helpful"

class ResolutionOutcome(BaseModel):
    ticket_id:str; final_resolution:str; successful_steps:list[str]; failed_steps:list[str]
    used_kb_articles:list[str]; analyst_notes:str; resolution_time:int; resolved_at:datetime
    final_category:str; final_subcategory:str; analyst_feedback:str

class IncidentCluster(BaseModel):
    cluster_id:str; title:str; ticket_ids:list[str]; applications:list[str]; categories:list[str]
    common_terms:list[str]; common_errors:list[str]; possible_components:list[str]
    first_seen:datetime; last_seen:datetime; confidence:float; status:str="Detected"

class ChangeRecord(BaseModel):
    change_id:str; title:str; description:str; component:str; application:str
    change_type:str; start_time:datetime; end_time:datetime|None=None; owner:str; status:str; tags:list[str]=[]

class TimelineEvent(BaseModel):
    event_id:str; ticket_id:str; event_type:str; description:str
    timestamp:datetime=Field(default_factory=now); metadata:dict[str,Any]={}

class KnowledgeHealth(BaseModel):
    kb_id:str; usage_count:int; positive_feedback:int; negative_feedback:int
    successful_resolutions:int; failed_resolutions:int; success_rate:float
    last_reviewed:str; days_since_review:int; conflict_count:int
    health_status:str; health_reasons:list[str]

class ClusterStatusRequest(BaseModel):
    status:str

class KBDraftRequest(BaseModel):
    suggested_title:str="Draft Knowledge Article"
    symptoms:list[str]=[]
    cases:list[dict[str,Any]]=[]

