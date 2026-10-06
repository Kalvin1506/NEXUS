import os
from app.ai.base import AIProvider
from app.ai.demo_provider import DemoProvider
from app.ai.service import AIService,configured_provider
from app.engine import analyze

PAYLOAD={"description":"Users cannot login to NovaHR after resetting their password. The screen shows INVALID_TOKEN.","application":None,"error_message":None}

class FakeGemini(AIProvider):
    name="gemini";model="gemini-2.5-flash"
    def __init__(self):self.resolution_calls=0;self.category="Authentication";self.bad=False;self.resolution_steps=[]
    def normalize_ticket(self,ticket):
        if self.bad:raise RuntimeError("malformed JSON")
        return {"normalized_description":PAYLOAD["description"],"application":"NovaHR","symptoms":["Unable to authenticate"],"error_codes":["INVALID_TOKEN"],"technical_terms":["token","password"]}
    def extract_ticket_fields(self,ticket):return {"application":"NovaHR","affected_function":"Login","symptoms":["Unable to authenticate"],"error_message":"INVALID_TOKEN","technical_terms":["token"],"environment":None}
    def classify_ticket(self,ticket):return {"category":self.category,"subcategory":"Token / Session","supporting_terms":["INVALID_TOKEN","login"],"confidence":.93}
    def summarize_cases(self,evidence):return {"summary":"Historically effective in similar cases.","historically_effective_steps":["Clear authentication token cache","Invented action"],"historically_less_effective_steps":["Restart authentication service","Delete database"]}
    def draft_grounded_resolution(self,evidence):self.resolution_calls+=1;return {"resolution_steps":self.resolution_steps,"summary":"Grounded draft","source_references":["KB-014"]}
    def suggest_investigation_steps(self,ticket):return {"suggestions":["Confirm whether the issue affects one user or multiple users.","Capture the exact error and timestamp before escalating with evidence."],"caution":"Analyst review required."}
    def generate_explanation(self,evidence):return {"ticket_evidence":[],"knowledge_evidence":[],"historical_evidence":[],"dependency_evidence":[],"change_correlation":[],"summary":"Restart the invented quantum service"}
    def generate_handover(self,evidence):return {"current_issue":"Invented issue","status":"Invented","attempted_steps":["Invented action"],"failed_steps":["Delete database"],"current_recommendation":"Invented fix","evidence":["Invented evidence"],"pending_actions":["Invented action"]}
    def generate_kb_draft(self,evidence):return {"title":"Draft","symptoms":[],"prerequisites":[],"resolution_steps":["Invented action"],"escalation_conditions":[],"source_cases":["CASE-FAKE"],"draft":True}

def local_result():return analyze(PAYLOAD)

def test_valid_gemini_classification():
    result=AIService(FakeGemini()).understand_ticket(PAYLOAD,local_result())
    assert result["analysis_mode"]=="gemini";assert result["classification"]["category"]=="Authentication"

def test_invalid_category_is_rejected():
    provider=FakeGemini();provider.category="Made Up Category"
    result=AIService(provider).understand_ticket(PAYLOAD,local_result())
    assert result["classification"]["category"]==local_result()["category"]

def test_malformed_response_falls_back():
    provider=FakeGemini();provider.bad=True
    result=AIService(provider).understand_ticket(PAYLOAD,local_result())
    assert result["analysis_mode"]=="local";assert result["fallback_message"]

def test_missing_api_key_uses_local_provider(monkeypatch):
    monkeypatch.setenv("DEMO_MODE","false");monkeypatch.delenv("GEMINI_API_KEY",raising=False);monkeypatch.setenv("AI_PROVIDER","gemini")
    assert isinstance(configured_provider(),DemoProvider)

def test_no_reliable_match_skips_llm_resolution():
    provider=FakeGemini();result=AIService(provider).draft_resolution({},[],False,[],[])
    assert result["mode"]=="skipped";assert provider.resolution_calls==0

def test_no_match_gets_separate_investigation_suggestions():
    result=AIService(FakeGemini()).suggest_investigation_steps({"description":"Unknown error","application":"Hexaware","category":"Authentication"})
    assert result["mode"]=="gemini";assert 2<=len(result["suggestions"])<=5

def test_unsupported_llm_resolution_step_removed():
    local=local_result();provider=FakeGemini();provider.resolution_steps=[{"step":"Restart the production database","source_kb_id":"KB-014","source_section":"Resolution Step 1"}]
    result=AIService(provider).draft_resolution(PAYLOAD,local["knowledge_matches"],True,local["recommended_resolution"],local["traced_resolution"])
    assert result["steps"]==[];assert result["mode"]=="rejected"

def test_grounded_resolution_source_is_preserved():
    local=local_result();provider=FakeGemini();allowed=local["knowledge_matches"][0]["article"]["resolution_steps"][0];provider.resolution_steps=[{"step":allowed,"source_kb_id":"KB-014","source_section":"Resolution Step 1"}]
    result=AIService(provider).draft_resolution(PAYLOAD,local["knowledge_matches"],True,local["recommended_resolution"],local["traced_resolution"])
    assert result["traced"][0]["source_kb_id"]=="KB-014";assert result["traced"][0]["evidence_score"]>0

def test_historical_summary_filters_unsupported_steps():
    cases=[{"successful_steps":["Clear authentication token cache"],"failed_steps":["Restart authentication service"],"description":"Token failure"}]
    result=AIService(FakeGemini()).summarize_history(cases,{"summary":"Local","outcomes":[]})
    assert result["historically_effective_steps"]==["Clear authentication token cache"]
    assert result["historically_less_effective_steps"]==["Restart authentication service"]

def test_handover_does_not_invent_facts():
    evidence={"current_issue":"NovaHR login failure","ticket_status":"In Progress","already_attempted":{"successful":["Clear token cache"],"failed":["Restart service"]},"evidence":{"knowledge":[{"id":"KB-014","score":.91}],"historical":[]},"current_recommendation":["Clear token cache"],"related_cluster":None,"possible_related_change":None,"pending_action":"Clear token cache"}
    result=AIService(FakeGemini()).enhance_handover(evidence)["llm_handover"]
    assert result["current_issue"]==evidence["current_issue"];assert result["attempted_steps"]==[];assert "Invented" not in str(result)

def test_demo_mode_remains_deterministic(monkeypatch):
    monkeypatch.setenv("DEMO_MODE","true");monkeypatch.setenv("GEMINI_API_KEY","not-used")
    service=AIService(configured_provider());local=local_result();result=service.understand_ticket(PAYLOAD,local)
    assert result["analysis_mode"]=="local";assert result["classification"]["category"]=="Authentication"
