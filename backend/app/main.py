import os,logging,re
from datetime import datetime,timezone,timedelta
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from .models import AnalyzeRequest,TextRequest,SearchRequest,ResolutionRequest,ResolveRequest,TicketUpdate,Feedback,Ticket,HistoricalCase,ClusterStatusRequest,KBDraftRequest
from .engine import analyze,complete_analysis,classify,search_kb,search_cases,dependency_impact
from .data import KB,CASES,PATTERNS,SERVICES,CHANGES
from .intelligence import detect_clusters,correlate_changes,aggregate_outcomes,knowledge_health,knowledge_conflicts,handover,explanation
from .repository import repo
from .ai.service import ai_service
logging.getLogger("nexus.ai").setLevel(logging.INFO)

app=FastAPI(title="NEXUS API",version="1.0.0",description="Evidence-grounded IT support intelligence")
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv("FRONTEND_ORIGIN","http://localhost:5173"),"http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
feedback_store=[]
cluster_statuses={}

def add_event(ticket,event_type,description,metadata=None):
    ticket.timeline.append({"event_id":f"EVT-{ticket.ticket_id}-{len(ticket.timeline)+1}","ticket_id":ticket.ticket_id,"event_type":event_type,"description":description,"timestamp":datetime.now(timezone.utc),"metadata":metadata or {}})

def current_clusters():
    clusters=detect_clusters(repo.all())
    for cluster in clusters:cluster.status=cluster_statuses.get(cluster.cluster_id,cluster.status)
    return clusters

def ticket_cluster(ticket_id):return next((c for c in current_clusters() if ticket_id in c.ticket_ids),None)

@app.get("/health")
def health():return {"status":"healthy","storage":repo.mode,"demo_mode":os.getenv("DEMO_MODE","true").lower()=="true","analysis_provider":ai_service.provider.name,"analysis_model":getattr(ai_service.provider,"active_model",ai_service.provider.model),"configured_primary_model":ai_service.provider.model}

@app.post("/api/tickets/analyze")
def analyze_ticket(req:AnalyzeRequest):
    if not req.description.strip():raise HTTPException(422,"Ticket description is required")
    payload=req.model_dump();local=analyze(payload);understanding=ai_service.understand_ticket(payload,local)
    if understanding["analysis_mode"]=="gemini":
        normalized=understanding["normalized"];extracted=understanding["extracted_fields"];suggested=understanding["classification"]
        ext={"normalized_description":normalized["normalized_description"],"application":extracted.get("application") or normalized.get("application") or local["application"],"error_text":extracted.get("error_message") or (normalized.get("error_codes") or [local["error_text"]])[0],"symptoms":extracted.get("symptoms") or normalized.get("symptoms") or local["symptoms"],"technical_terms":extracted.get("technical_terms") or normalized.get("technical_terms") or local["technical_terms"]}
        cls={"category":suggested["category"],"subcategory":suggested["subcategory"],"confidence":suggested["confidence"],"matched_terms":suggested.get("supporting_terms",[])}
        result=complete_analysis(payload,ext,cls)
    else:result=local
    grounded=ai_service.draft_resolution({"description":req.description,"application":result["application"],"category":result["category"],"subcategory":result["subcategory"]},result["knowledge_matches"],result["reliable_match"],result["recommended_resolution"],result["traced_resolution"])
    result["recommended_resolution"]=grounded["steps"];result["traced_resolution"]=grounded["traced"];result["source_references"]=grounded["sources"]
    investigation={"suggestions":[],"mode":None}
    if not result["reliable_match"]:
        investigation=ai_service.suggest_investigation_steps({"description":req.description,"normalized_description":result["normalized_description"],"application":result["application"],"error_text":result["error_text"],"category":result["category"],"subcategory":result["subcategory"],"symptoms":result["symptoms"]})
    existing=repo.get(req.ticket_id) if req.ticket_id else None
    if req.ticket_id:
        tid=req.ticket_id
    else:
        numbers=[int(match.group(1)) for item in repo.all() if (match:=re.search(r"(\d+)$",item.ticket_id))]
        tid=f"TKT-{max(numbers+[2040])+1}"
    created=existing.created_at if existing else datetime.now(timezone.utc)
    timeline=existing.timeline if existing else []
    ticket=Ticket(ticket_id=tid,description=req.description,normalized_description=result["normalized_description"],application=result["application"],error_text=result["error_text"],symptoms=result["symptoms"],technical_terms=result["technical_terms"],category=result["category"],subcategory=result["subcategory"],classification_confidence=result["confidence"],knowledge_confidence=result["knowledge_confidence"],historical_confidence=result["historical_confidence"],reliable_match=result["reliable_match"],resolution_status="Suggested" if result["reliable_match"] and result["recommended_resolution"] else "No Reliable Match",kb_matches=result["knowledge_matches"],case_matches=result["historical_matches"],recommended_resolution=result["recommended_resolution"],traced_resolution=result["traced_resolution"],investigation_suggestions=investigation["suggestions"],investigation_suggestions_mode=investigation["mode"],source_references=result["source_references"],sla_risk=result["sla_risk"],sla_reasons=result["sla_reasons"],dependency_impact=result["dependency_impact"],created_at=created,timeline=timeline,analysis_mode=understanding["analysis_mode"],analysis_notice=understanding["fallback_message"])
    if not existing:add_event(ticket,"created","Ticket created")
    add_event(ticket,"normalized","Ticket text normalized")
    add_event(ticket,"classified",f"Classified as {ticket.category} / {ticket.subcategory}",{"confidence":ticket.classification_confidence})
    if ticket.kb_matches:add_event(ticket,"knowledge_retrieved",f"{ticket.kb_matches[0]['kb_id']} retrieved — {round(ticket.knowledge_confidence*100)}%",{"kb_id":ticket.kb_matches[0]["kb_id"],"score":ticket.knowledge_confidence})
    if ticket.case_matches:add_event(ticket,"case_matched",f"{ticket.case_matches[0]['case_id']} matched — {round(ticket.historical_confidence*100)}%",{"case_id":ticket.case_matches[0]["case_id"],"score":ticket.historical_confidence})
    if ticket.recommended_resolution:add_event(ticket,"resolution_generated","Evidence-grounded resolution generated",{"sources":ticket.source_references})
    if ticket.investigation_suggestions:add_event(ticket,"investigation_suggested","Unverified investigation suggestions generated for analyst review",{"mode":ticket.investigation_suggestions_mode})
    repo.save(ticket)
    cluster=ticket_cluster(ticket.ticket_id)
    if cluster:
        ticket.related_cluster_ids=[cluster.cluster_id];add_event(ticket,"cluster_detected",f"Related ticket cluster {cluster.cluster_id} detected",{"cluster_id":cluster.cluster_id});repo.save(ticket)
    changes=correlate_changes(ticket);ticket.related_changes=changes
    if changes:add_event(ticket,"change_correlated",f"Possible relationship with {changes[0]['change_id']}",{"change_id":changes[0]["change_id"],"correlation":changes[0]["correlation"]});repo.save(ticket)
    return {"ticket":ticket,"analysis":result,"analysis_mode":understanding["analysis_mode"],"normalized_description":result["normalized_description"],"classification":understanding["classification"],"extracted_fields":understanding["extracted_fields"],"message":understanding["fallback_message"]}

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
    elif t.reliable_match:
        grounded=ai_service.draft_resolution({"description":t.description,"application":t.application,"category":t.category,"subcategory":t.subcategory},t.kb_matches,t.reliable_match,t.recommended_resolution,t.traced_resolution)
        t.recommended_resolution=grounded["steps"];t.traced_resolution=grounded["traced"];t.source_references=grounded["sources"]
    t.analyst_notes=req.analyst_notes;t.resolution_status="Approved";add_event(t,"approved","Analyst approved recommendation");repo.save(t);return t

@app.post("/api/tickets/{id}/resolve")
def resolve_ticket(id:str,req:ResolveRequest):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    resolved=datetime.now(timezone.utc);minutes=max(1,round((resolved-t.created_at).total_seconds()/60))
    t.status="Resolved";t.resolution_status="Resolved";t.analyst_notes=req.analyst_notes;t.resolved_at=resolved
    add_event(t,"resolved","Ticket resolved by analyst",{"resolution_time":minutes})
    number=max([int(c.case_id.split("-")[-1]) for c in CASES]+[1826])+1
    case=HistoricalCase(case_id=f"CASE-{number}",description=t.description,application=t.application,category=t.category,subcategory=t.subcategory,troubleshooting_attempts=list(dict.fromkeys(req.failed_steps+req.successful_steps)),failed_steps=req.failed_steps,successful_steps=req.successful_steps,final_resolution=req.final_resolution,related_kb=req.used_kb_articles,technician_notes=req.analyst_notes,resolution_time=minutes,created_at=resolved)
    CASES.append(case)
    for kb_id in req.used_kb_articles:
        article=next((k for k in KB if k.kb_id==kb_id),None)
        if article:
            article.usage+=1
            if req.analyst_feedback.lower() in ("helpful","resolution helpful"):article.success_feedback+=1
            else:article.negative_feedback+=1
            if req.successful_steps:article.successful_resolutions+=1
            if req.failed_steps and not req.successful_steps:article.failed_resolutions+=1
    add_event(t,"case_memory_updated",f"Added to Case Memory as {case.case_id}",{"case_id":case.case_id});repo.save(t)
    return {"ticket":t,"outcome":{"ticket_id":id,"final_resolution":req.final_resolution,"successful_steps":req.successful_steps,"failed_steps":req.failed_steps,"used_kb_articles":req.used_kb_articles,"analyst_notes":req.analyst_notes,"resolution_time":minutes,"resolved_at":resolved,"final_category":t.category,"final_subcategory":t.subcategory,"analyst_feedback":req.analyst_feedback},"case":case,"message":"Added to Case Memory"}

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
    changes=req.model_dump(exclude_unset=True)
    for k,v in changes.items():setattr(t,k,v)
    add_event(t,"escalated" if changes.get("resolution_status")=="Escalated" else "analyst_edited","Ticket escalated" if changes.get("resolution_status")=="Escalated" else "Analyst edited ticket",{"fields":list(changes)})
    return repo.save(t)
@app.get("/api/knowledge")
def knowledge(search:str="",category:str=""):
    return [{**k.model_dump(),"health":knowledge_health(k).model_dump()} for k in KB if (not search or search.lower() in (k.kb_id+" "+k.title+" "+" ".join(k.tags)).lower()) and (not category or k.category==category)]
@app.get("/api/knowledge/conflicts")
def conflicts():return knowledge_conflicts()
@app.post("/api/knowledge/draft")
def kb_draft(req:KBDraftRequest):return ai_service.generate_kb_draft(req.model_dump())
@app.get("/api/knowledge/{id}")
def knowledge_one(id:str):
    k=next((x for x in KB if x.kb_id==id),None)
    if not k:raise HTTPException(404,"Article not found")
    return {**k.model_dump(),"related_cases":[c for c in CASES if id in c.related_kb],"health":knowledge_health(k)}
@app.get("/api/knowledge/{id}/health")
def kb_health(id:str):
    k=next((x for x in KB if x.kb_id==id),None)
    if not k:raise HTTPException(404,"Article not found")
    return knowledge_health(k)
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

@app.get("/api/clusters")
def clusters():return current_clusters()
@app.get("/api/clusters/{id}")
def cluster_one(id:str):
    c=next((x for x in current_clusters() if x.cluster_id==id),None)
    if not c:raise HTTPException(404,"Cluster not found")
    tickets=[repo.get(tid) for tid in c.ticket_ids];changes=[]
    for t in tickets:
        for change in correlate_changes(t):
            if change["change_id"] not in [x["change_id"] for x in changes]:changes.append(change)
    timeline=sorted([event for t in tickets for event in t.timeline],key=lambda x:x.get("timestamp",datetime.now(timezone.utc)))
    return {**c.model_dump(),"tickets":tickets,"related_changes":changes,"timeline":timeline,"analyst_notes":""}
@app.post("/api/clusters/{id}/status")
def cluster_status(id:str,req:ClusterStatusRequest):
    allowed={"Detected","Under Review","Confirmed Related","Dismissed","Resolved"}
    if req.status not in allowed:raise HTTPException(422,"Invalid cluster status")
    if not any(c.cluster_id==id for c in current_clusters()):raise HTTPException(404,"Cluster not found")
    cluster_statuses[id]=req.status;return next(c for c in current_clusters() if c.cluster_id==id)

@app.get("/api/changes")
def changes():
    clusters=current_clusters();result=[]
    for change in CHANGES:
        related=[t.ticket_id for t in repo.all() if any(x["change_id"]==change["change_id"] for x in correlate_changes(t))]
        related_clusters=[c.cluster_id for c in clusters if any(t in c.ticket_ids for t in related)]
        result.append({**change,"related_tickets":related,"related_clusters":related_clusters})
    return result
@app.get("/api/changes/{id}")
def change_one(id:str):
    change=next((x for x in changes() if x["change_id"]==id),None)
    if not change:raise HTTPException(404,"Change not found")
    return change

@app.get("/api/tickets/{id}/timeline")
def ticket_timeline(id:str):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    return t.timeline
@app.get("/api/tickets/{id}/related-changes")
def ticket_changes(id:str):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    return correlate_changes(t)
@app.get("/api/tickets/{id}/historical-outcomes")
def historical_outcomes(id:str):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    local=aggregate_outcomes(t.case_matches);return {**local,"enhanced_summary":ai_service.summarize_history(t.case_matches,local)}
@app.get("/api/tickets/{id}/handover")
def ticket_handover(id:str):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    return ai_service.enhance_handover(handover(t,ticket_cluster(id)))
@app.get("/api/tickets/{id}/explanation")
def ticket_explanation(id:str):
    t=repo.get(id)
    if not t:raise HTTPException(404,"Ticket not found")
    return ai_service.enhance_explanation(explanation(t,ticket_cluster(id)))
@app.get("/api/dependencies/{service}")
def dependencies(service:str):return dependency_impact(service)
@app.get("/api/dependencies")
def all_dependencies():return {"services":SERVICES,"edges":[{"from":name,"to":dep} for name,data in SERVICES.items() for dep in data["dependencies"]]}

@app.get("/api/dashboard")
def dashboard():
    items=repo.all(); cats=sorted(set(t.category for t in items)); now=datetime.now(timezone.utc)
    clusters=current_clusters(); correlated=sum(bool(correlate_changes(t)) for t in items);needs_review=sum(knowledge_health(k).health_status!="Healthy" for k in KB)
    return {"tickets_analyzed":len(items),"high_confidence":round(sum(t.classification_confidence>=.8 for t in items)/len(items)*100),"no_matches":sum(not t.reliable_match for t in items),"knowledge_gaps":sum(p["pattern_type"]=="Knowledge Gap" for p in PATTERNS)+5,"open_clusters":sum(c.status not in ("Dismissed","Resolved") for c in clusters),"recent_change_correlations":correlated,"kb_needing_review":needs_review,"current_signals":[{"type":"cluster","id":c.cluster_id,"text":f"{len(c.ticket_ids)} related {c.title}"} for c in clusters[:2]]+[{"type":"knowledge","id":k.kb_id,"text":f"{k.title} — {knowledge_health(k).health_status}"} for k in KB if knowledge_health(k).health_status!="Healthy"][:1],
      "categories":[{"name":c,"value":sum(t.category==c for t in items)} for c in cats],"trend":[{"day":(now-timedelta(days=d)).strftime("%a"),"tickets":sum((now-t.created_at).days==d for t in items)} for d in range(6,-1,-1)],"recent":items[:8],"storage_mode":repo.mode}
@app.post("/api/feedback")
def feedback(value:Feedback):feedback_store.append({**value.model_dump(),"created_at":datetime.now(timezone.utc)});return {"stored":True}

