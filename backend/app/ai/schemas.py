from pydantic import BaseModel, Field

class NormalizedTicket(BaseModel):
    normalized_description:str
    application:str|None=None
    symptoms:list[str]=[]
    error_codes:list[str]=[]
    technical_terms:list[str]=[]

class ExtractedTicketFields(BaseModel):
    application:str|None=None
    affected_function:str|None=None
    symptoms:list[str]=[]
    error_message:str|None=None
    technical_terms:list[str]=[]
    environment:str|None=None

class ClassificationSuggestion(BaseModel):
    category:str
    subcategory:str
    supporting_terms:list[str]=[]
    confidence:float=Field(ge=0,le=1)

class GroundedResolutionStep(BaseModel):
    step:str
    source_kb_id:str
    source_section:str

class GroundedResolution(BaseModel):
    resolution_steps:list[GroundedResolutionStep]=[]
    summary:str=""
    source_references:list[str]=[]

class InvestigationSuggestions(BaseModel):
    suggestions:list[str]=Field(min_length=2,max_length=5)
    caution:str="These suggestions are not validated against the knowledge base and require analyst review."

class HistoricalSummary(BaseModel):
    summary:str
    historically_effective_steps:list[str]=[]
    historically_less_effective_steps:list[str]=[]

class ExplanationOutput(BaseModel):
    ticket_evidence:list[str]=[]
    knowledge_evidence:list[str]=[]
    historical_evidence:list[str]=[]
    dependency_evidence:list[str]=[]
    change_correlation:list[str]=[]
    summary:str=""

class HandoverOutput(BaseModel):
    current_issue:str
    status:str
    attempted_steps:list[str]=[]
    failed_steps:list[str]=[]
    current_recommendation:str=""
    evidence:list[str]=[]
    pending_actions:list[str]=[]

class KBDraftOutput(BaseModel):
    title:str
    symptoms:list[str]=[]
    prerequisites:list[str]=[]
    resolution_steps:list[str]=[]
    escalation_conditions:list[str]=[]
    source_cases:list[str]=[]
    draft:bool=True

