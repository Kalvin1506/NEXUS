import os
os.environ["DEMO_MODE"]="true"
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_health():assert c.get('/health').status_code==200
def test_token_ticket_grounded():
    d=c.post('/api/tickets/analyze',json={"description":"Users cannot login to NovaHR after resetting their password. The screen shows INVALID_TOKEN."}).json()
    assert d['ticket']['category']=='Authentication';assert d['ticket']['kb_matches'][0]['kb_id']=='KB-014';assert d['ticket']['reliable_match']
    allowed={s for m in d['ticket']['kb_matches'] for s in m['article']['resolution_steps']}
    assert set(d['ticket']['recommended_resolution']) <= allowed
def test_no_match_has_no_resolution():
    d=c.post('/api/tickets/analyze',json={"description":"Application displays error XYZ-982."}).json()['ticket']
    assert not d['reliable_match'];assert d['recommended_resolution']==[]
def test_top_three():assert len(c.post('/api/knowledge/search',json={"query":"login invalid token password reset"}).json()['matches'])==3
def test_case_memory():
    d=c.post('/api/cases/search',json={"query":"NovaHR password reset invalid token"}).json()['matches']
    assert d and d[0]['successful_steps'] and d[0]['failed_steps']
def test_update():
    d=c.put('/api/tickets/TKT-2041',json={"analyst_notes":"Reviewed by analyst"});assert d.status_code==200

