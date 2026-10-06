"""Deterministic demo intelligence: normalization, classification, TF-IDF-like retrieval and evidence gating."""
import math, os, re
from collections import Counter
from typing import Any
from .data import KB, CASES, SERVICES

TOKEN=re.compile(r"[a-z0-9_]+")
STOP={"the","a","an","is","are","to","of","and","for","after","with","in","on","it","this","that","user","users"}
def tokens(text:str): return [x for x in TOKEN.findall(text.lower()) if x not in STOP and len(x)>1]
def normalize(text:str):
    text=re.sub(r"\s+"," ",text.strip())
    return text[:1].upper()+text[1:] if text else text
def similarity(a:str,b:str):
    ca,cb=Counter(tokens(a)),Counter(tokens(b)); vocab=set(ca)|set(cb)
    dot=sum(ca[x]*cb[x] for x in vocab); den=math.sqrt(sum(v*v for v in ca.values())*sum(v*v for v in cb.values()))
    return dot/den if den else 0
def article_text(k): return " ".join([k.title,k.category,*k.symptoms,k.cause,*k.tags])
def case_text(c): return " ".join([c.description,c.application,c.category,c.subcategory,*c.troubleshooting_attempts,c.final_resolution])

RULES=[
(("login","password","token","invalid_token","sso","authenticate","session"),"Authentication","Token / Session"),
(("slow","latency","performance","takes","timeout"),"Performance","Slow Response"),
(("500","xyz-","exception","error","crash","export failed"),"Application Error","Runtime Error"),
(("vpn","dns","network","host not found","connectivity"),"Network","Connectivity"),
(("database","connection pool","sql","connections"),"Database","Connectivity"),
(("access denied","permission","role","restricted"),"Access / Permissions","Role / Permission"),
(("api","502","gateway","integration","sync","synchronization"),"Integration","API / Synchronization"),
(("batch","scheduler","job","nightly"),"Batch Processing","Job Failure")]
APPS=["NovaHR","Atlas CRM","Orbit ERP","Pulse Inventory","Vertex Finance"]

def classify(description:str,error:str=""):
    text=(description+" "+error).lower(); scored=[]
    for terms,cat,sub in RULES:
        hits=sum(1 for x in terms if x in text); scored.append((hits,cat,sub))
    hits,cat,sub=max(scored)
    if hits==0:return {"category":"Unknown","subcategory":"Unknown","confidence":.34,"matched_terms":[]}
    matched=[x for terms,c,s in RULES if c==cat for x in terms if x in text]
    return {"category":cat,"subcategory":sub,"confidence":round(min(.97,.63+hits*.1),2),"matched_terms":matched}

def extract(description:str,application:str|None,error:str|None):
    normalized=normalize(description); low=normalized.lower()
    app=application or next((a for a in APPS if a.lower() in low),"Unknown")
    errors=[]
    for pat in [r"\bHTTP\s*\d{3}\b",r"\bINVALID_TOKEN\b",r"\b[A-Z]{2,10}-\d{2,5}\b"]:
        errors += re.findall(pat,normalized,re.I)
    symptoms=[]
    for words,label in [(("cannot login","can't login","login fail"),"Unable to authenticate"),(("slow","takes over"),"Slow response"),(("access denied","permission denied"),"Access denied"),(("not updating","stale","sync"),"Data not synchronized"),(("batch","job aborted"),"Batch failure"),(("502","500","error"),"Application error")]:
        if any(w in low for w in words): symptoms.append(label)
    terms=sorted(set(tokens(normalized)) & {"token","session","password","sso","vpn","dns","api","gateway","batch","scheduler","database","timeout","sync","permission","role"})
    return {"normalized_description":normalized,"application":app,"error_text":error or (", ".join(errors) if errors else "Unknown"),"symptoms":symptoms or ["Unspecified symptom"],"technical_terms":terms}

def search_kb(query:str,category:str|None=None,limit=3):
    qtok=set(tokens(query)); results=[]
    for k in KB:
        semantic=similarity(query,article_text(k)); overlap=qtok & set(tokens(article_text(k)))
        category_bonus=.12 if category and k.category==category else 0
        score=min(.99,semantic*.78+min(.18,len(overlap)*.035)+category_bonus)
        results.append({"kb_id":k.kb_id,"title":k.title,"category":k.category,"score":round(score,2),"matched_terms":sorted(overlap)[:5],"why_matched":", ".join(sorted(overlap)[:4]) or "Category similarity","article":k.model_dump()})
    return sorted(results,key=lambda x:x["score"],reverse=True)[:limit]

def search_cases(query:str,application:str|None=None,category:str|None=None,limit=3):
    results=[]
    for c in CASES:
        score=similarity(query,case_text(c))*.78+(.12 if application and c.application==application else 0)+(.1 if category and c.category==category else 0)
        results.append({"case_id":c.case_id,"description":c.description,"application":c.application,"category":c.category,"subcategory":c.subcategory,"similarity":round(min(.99,score),2),"failed_steps":c.failed_steps,"successful_steps":c.successful_steps,"troubleshooting_attempts":c.troubleshooting_attempts,"final_resolution":c.final_resolution,"related_kb":c.related_kb,"resolution_time":c.resolution_time,"created_at":c.created_at})
    return sorted(results,key=lambda x:x["similarity"],reverse=True)[:limit]

def dependency_impact(component:str):
    if component in SERVICES:
        downstream=[name for name,data in SERVICES.items() if component in data["dependencies"]]
        return {"problem_component":component,"dependencies":SERVICES[component]["dependencies"],"potentially_affected":downstream,"estimated_note":"Estimated from configured dependency relationships."}
    app=next((a for a in APPS if a.lower() in component.lower()),None)
    return {"problem_component":app or component,"dependencies":SERVICES.get(app,{}).get("dependencies",[]),"potentially_affected":[app] if app else [],"estimated_note":"Estimated from configured dependency relationships."}

def analyze(payload:dict[str,Any]):
    ext=extract(payload["description"],payload.get("application"),payload.get("error_message")); cls=classify(payload["description"],ext["error_text"])
    query=" ".join([payload["description"],ext["error_text"],*ext["symptoms"]]); kb=search_kb(query,cls["category"]); cases=search_cases(query,ext["application"],cls["category"])
    threshold=float(os.getenv("KB_MATCH_THRESHOLD","0.38"))
    # Category agreement alone is not evidence. Require a shared, distinctive term;
    # generic words such as "error" or "application" cannot unlock a resolution.
    generic={"error","application","user","users","failed","failure","service","display","displays"}
    distinctive=[x for x in (kb[0]["matched_terms"] if kb else []) if x not in generic]
    reliable=bool(kb and kb[0]["score"]>=threshold and cls["confidence"]>=.5 and distinctive)
    resolution=[]; sources=[]
    if reliable:
        # Grounding invariant: every step is copied from retrieved KB evidence only.
        for match in kb:
            if match["score"]>=max(threshold*.8,.3):
                sources.append(match["kb_id"])
                for step in match["article"]["resolution_steps"]:
                    if step not in resolution: resolution.append(step)
                if len(resolution)>=5: break
        resolution=resolution[:5]
    failed=Counter(x for c in cases if c["similarity"]>=.35 for x in c["failed_steps"])
    successful=Counter(x for c in cases if c["similarity"]>=.35 for x in c["successful_steps"])
    hours_open=18; sla=[]
    if not reliable:sla.append("No high-confidence knowledge match")
    if cases and cases[0]["resolution_time"]>60:sla.append("Similar cases historically required extended resolution time")
    if hours_open/24>=.7:sla.append("Ticket is beyond 70% of the response window")
    return {**ext,**cls,"knowledge_matches":kb,"historical_matches":cases,"knowledge_confidence":kb[0]["score"] if kb else 0,"historical_confidence":cases[0]["similarity"] if cases else 0,
      "reliable_match":reliable,"recommended_resolution":resolution,"source_references":sources,"no_match_message":None if reliable else "The available knowledge base does not contain enough evidence to recommend a reliable resolution.",
      "previous_evidence":{"failed":[{"step":x,"count":n} for x,n in failed.most_common(3)],"successful":[{"step":x,"count":n} for x,n in successful.most_common(3)]},
      "sla_risk":"Elevated" if sla else "Normal","sla_reasons":sla,"dependency_impact":dependency_impact(ext["application"]),"demo_mode":os.getenv("DEMO_MODE","true").lower()=="true"}

