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
    assert not d['reliable_match'];assert d['recommended_resolution']==[];assert 2<=len(d['investigation_suggestions'])<=5

def test_custom_text_ticket_id_does_not_break_next_generated_id():
    custom=c.post('/api/tickets/analyze',json={"ticket_id":"TKT-DEMO","description":"Application displays error CUSTOM-1."})
    assert custom.status_code==200;assert custom.json()['ticket']['ticket_id']=='TKT-DEMO'
    generated=c.post('/api/tickets/analyze',json={"description":"Application displays error CUSTOM-2."})
    assert generated.status_code==200;assert generated.json()['ticket']['ticket_id'].startswith('TKT-')
def test_top_three():assert len(c.post('/api/knowledge/search',json={"query":"login invalid token password reset"}).json()['matches'])==3
def test_case_memory():
    d=c.post('/api/cases/search',json={"query":"NovaHR password reset invalid token"}).json()['matches']
    assert d and d[0]['successful_steps'] and d[0]['failed_steps']
def test_update():
    d=c.put('/api/tickets/TKT-2041',json={"analyst_notes":"Reviewed by analyst"});assert d.status_code==200

def test_resolution_creates_case_memory_and_preserves_steps():
    before=len(c.get('/api/cases').json())
    payload={"final_resolution":"Clear authentication token cache","successful_steps":["Clear authentication token cache"],"failed_steps":["Restart authentication service","Reset user session"],"used_kb_articles":["KB-014"],"analyst_notes":"Validated with user","analyst_feedback":"Helpful"}
    result=c.post('/api/tickets/TKT-2042/resolve',json=payload)
    assert result.status_code==200
    body=result.json();assert body['message']=='Added to Case Memory';assert body['ticket']['status']=='Resolved'
    assert body['case']['successful_steps']==payload['successful_steps'];assert body['case']['failed_steps']==payload['failed_steps']
    assert len(c.get('/api/cases').json())==before+1

def test_cluster_rules_and_unrelated_exclusion():
    clusters=c.get('/api/clusters').json();nova=next(x for x in clusters if x['applications']==['NovaHR'])
    assert len(nova['ticket_ids'])>=3 and nova['confidence']>=.7
    assert all(not ('Vertex Finance' in x['applications'] and len(x['ticket_ids'])<3) for x in clusters)

def test_related_change_correlation_ignores_unrelated_change():
    changes=c.get('/api/tickets/TKT-2041/related-changes').json();ids={x['change_id'] for x in changes}
    assert 'CHG-102' in ids;assert 'CHG-091' not in ids;assert all('caused' not in x['language'].lower() for x in changes)

def test_every_resolution_step_is_traceable_and_no_unsupported_step():
    body=c.post('/api/tickets/analyze',json={"description":"Users cannot login to NovaHR after resetting their password. The screen shows INVALID_TOKEN."}).json()['ticket']
    assert len(body['traced_resolution'])==len(body['recommended_resolution'])
    assert all(x['source_kb_id'] and x['source_section'] and x['evidence_score']>0 for x in body['traced_resolution'])
    assert {x['step'] for x in body['traced_resolution']}==set(body['recommended_resolution'])

def test_kb_health_examples_and_conflict_detection():
    healthy=c.get('/api/knowledge/KB-014/health').json();poor=c.get('/api/knowledge/KB-041/health').json()
    assert healthy['health_status']=='Healthy';assert poor['health_status']=='Poor';assert healthy['health_reasons']
    conflicts=c.get('/api/knowledge/conflicts').json();assert any(set(x['articles'])=={'KB-014','KB-007'} for x in conflicts)

def test_historical_outcome_aggregation():
    data=c.get('/api/tickets/TKT-2041/historical-outcomes').json()
    assert data['similar_cases']>0;assert data['outcomes'];assert 'historical' in data['summary'].lower()

def test_handover_uses_stored_evidence_only():
    ticket=c.get('/api/tickets/TKT-2041').json();handover=c.get('/api/tickets/TKT-2041/handover').json()
    assert handover['current_issue']==ticket['normalized_description']
    assert all(x['id'] in {m['kb_id'] for m in ticket['kb_matches']} for x in handover['evidence']['knowledge'])
    assert all(step in ticket['recommended_resolution'] for step in handover['current_recommendation'])

def test_explanation_uses_existing_evidence():
    ticket=c.get('/api/tickets/TKT-2041').json();data=c.get('/api/tickets/TKT-2041/explanation').json()
    assert data['classification_evidence']['category']==ticket['category']
    assert all(x['id'] in {m['case_id'] for m in ticket['case_matches']} for x in data['historical_evidence'])
    assert data['evidence_strength']['label'] in ('Strong','Moderate','Weak')

def test_no_match_extension_invariant():
    ticket=c.post('/api/tickets/analyze',json={"description":"Application displays error XYZ-982."}).json()['ticket']
    assert not ticket['reliable_match'];assert ticket['recommended_resolution']==[];assert ticket['traced_resolution']==[]
    assert 2<=len(ticket['investigation_suggestions'])<=5

