import os
from datetime import datetime,timezone,timedelta
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from .models import AnalyzeRequest,TextRequest,SearchRequest,ResolutionRequest,TicketUpdate,Feedback,Ticket
from .engine import analyze,classify,search_kb,search_cases,dependency_impact
from .data import KB,CASES,PATTERNS,SERVICES
from .repository import repo

app=FastAPI(title="NEXUS API",version="1.0.0",description="Evidence-grounded IT support intelligence")
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv("FRONTEND_ORIGIN","http://localhost:5173"),"http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
feedback_store=[]

@app.get("/health")
def health():return {"status":"healthy","storage":repo.mode,"demo_mode":os.getenv("DEMO_MODE","true").lower()=="true"}

@app.post("/api/tickets/analyze")
def analyze_ticket(req:AnalyzeRequest):
    if not req.description.strip():raise HTTPException(422,"Ticket description is required")
    result=analyze(req.model_dump())
    existing=repo.get(req.ticket_id) if req.ticket_id else None
    number=max([int(t.ticket_id.split("-")[-1]) for t in repo.all()]+[2040])+1
    tid=req.ticket_id or f"TKT-{number}"
    ticket=Ticket(ticket_id=tid,description=req.description,normalized_description=result["normalized_description"],application=result["application"],error_text=result["error_text"],symptoms=result["symptoms"],technical_terms=result["technical_terms"],category=result["category"],subcategory=result["subcategory"],classification_confidence=result["confidence"],knowledge_confidence=result["knowledge_confidence"],historical_confidence=result["historical_confidence"],reliable_match=result["reliable_match"],resolution_status="Suggested" if result["reliable_match"] else "No Reliable Match",kb_matches=result["knowledge_matches"],case_matches=result["historical_matches"],recommended_resolution=result["recommended_resolution"],source_references=result["source_references"],sla_risk=result["sla_risk"],sla_reasons=result["sla_reasons"],dependency_impact=result["dependency_impact"],created_at=existing.created_at if existing else datetime.now(timezone.utc))
    repo.save(ticket)
    return {"ticket":ticket,"analysis":result}

@app.post("/api/tickets/classify")
def classify_ticket(req:TextRequest):return classify(req.description,req.error_message or "")
@app.post("/api/knowledge/search")
def knowledge_search(req:SearchRequest):return {"matches":search_kb(req.query,req.category,req.limit)}
@app.post("/api/cases/search")
def case_search(req:SearchRequest):return {"matches":search_cases(req.query,category=req.category,limit=req.limit)}

@app.post("/api/tickets/{id}/resolution")
def resolution(id:str,req:ResolutionRequest):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    if req.resolution is not None:t.recommended_resolution=req.resolution
    t.analyst_notes=req.analyst_notes;t.resolution_status="Approved";repo.save(t);return t

@app.get("/api/tickets")
def tickets(search:str="",category:str="",application:str="",status:str="",confidence:str="",page:int=Query(1,ge=1),page_size:int=Query(100,ge=1,le=200)):
    items=repo.all();s=search.lower()
    items=[t for t in items if (not s or s in (t.ticket_id+" "+t.description+" "+t.application).lower()) and (not category or t.category==category) and (not application or t.application==application) and (not status or t.resolution_status==status)]
    if confidence=="high":items=[t for t in items if t.classification_confidence>=.8]
    if confidence=="low":items=[t for t in items if t.classification_confidence<.6]
    return items[(page-1)*page_size:page*page_size]
@app.get("/api/tickets/{id}")
def ticket(id:str):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    return t
@app.put("/api/tickets/{id}")
def update_ticket(id:str,req:TicketUpdate):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    for k,v in req.model_dump(exclude_unset=True).items():setattr(t,k,v)
    return repo.save(t)
@app.get("/api/knowledge")
def knowledge(search:str="",category:str=""):
    return [k for k in KB if (not search or search.lower() in (k.kb_id+" "+k.title+" "+" ".join(k.tags)).lower()) and (not category or k.category==category)]
@app.get("/api/knowledge/{id}")
def knowledge_one(id:str):
    k=next((x for x in KB if x.kb_id==id),None)
    if not k:raise HTTPException(404,"Article not found")
    return {**k.model_dump(),"related_cases":[c for c in CASES if id in c.related_kb]}
@app.get("/api/cases")
def cases(search:str="",category:str="",application:str="",outcome:str=""):
    s=search.lower();return [c for c in CASES if (not s or s in (c.case_id+" "+c.description).lower()) and (not category or c.category==category) and (not application or c.application==application) and (not outcome or (outcome=="successful" and c.successful_steps) or (outcome=="failed" and c.failed_steps))]
@app.get("/api/cases/{id}")
def case_one(id:str):
    c=next((x for x in CASES if x.case_id==id),None)
    if not c:raise HTTPException(404,"Case not found")
    return c
@app.get("/api/patterns")
def patterns():return PATTERNS
@app.get("/api/dependencies/{service}")
def dependencies(service:str):return dependency_impact(service)
@app.get("/api/dependencies")
def all_dependencies():return {"services":SERVICES,"edges":[{"from":name,"to":dep} for name,data in SERVICES.items() for dep in data["dependencies"]]}

@app.get("/api/dashboard")
def dashboard():
    items=repo.all(); cats=sorted(set(t.category for t in items)); now=datetime.now(timezone.utc)
    return {"tickets_analyzed":len(items),"high_confidence":round(sum(t.classification_confidence>=.8 for t in items)/len(items)*100),"no_matches":sum(not t.reliable_match for t in items),"knowledge_gaps":sum(p["pattern_type"]=="Knowledge Gap" for p in PATTERNS)+5,
      "categories":[{"name":c,"value":sum(t.category==c for t in items)} for c in cats],"trend":[{"day":(now-timedelta(days=d)).strftime("%a"),"tickets":sum((now-t.created_at).days==d for t in items)} for d in range(6,-1,-1)],"recent":items[:8],"storage_mode":repo.mode}
@app.post("/api/feedback")
def feedback(value:Feedback):feedback_store.append({**value.model_dump(),"created_at":datetime.now(timezone.utc)});return {"stored":True}

