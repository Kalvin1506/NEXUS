"""Explainable operational intelligence built only from stored NEXUS evidence."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from .data import CHANGES, KB, SERVICES
from .models import IncidentCluster, KnowledgeHealth
from .engine import similarity, tokens

def detect_clusters(tickets:list[Any], window_minutes:int=60, minimum:int=3, threshold:float=.35)->list[IncidentCluster]:
    groups=defaultdict(list)
    for ticket in tickets:
        error=ticket.error_text if ticket.error_text not in (None,"","Unknown") else ""
        signal=error or (ticket.technical_terms[0] if ticket.technical_terms else ticket.subcategory)
        groups[(ticket.application,ticket.category,signal)].append(ticket)
    clusters=[];number=19
    for (app,category,signal),items in groups.items():
        items=sorted(items,key=lambda x:x.created_at)
        if len(items)<minimum:continue
        span=(items[-1].created_at-items[0].created_at).total_seconds()/60
        textual=sum(similarity(items[0].description,x.description) for x in items[1:])/max(1,len(items)-1)
        if span>window_minutes or textual<threshold:continue
        terms=Counter(x for t in items for x in tokens(" ".join([t.description,*t.technical_terms]))).most_common(6)
        errors=Counter(t.error_text for t in items if t.error_text not in (None,"","Unknown")).most_common(3)
        dependencies=SERVICES.get(app,{}).get("dependencies",[])
        confidence=min(.97,.55+min(.2,len(items)*.02)+min(.15,textual*.15)+(.07 if errors else 0))
        clusters.append(IncidentCluster(cluster_id=f"CL-{number:03d}",title=f"{app} {category.lower()} tickets",ticket_ids=[t.ticket_id for t in items],applications=[app],categories=[category],common_terms=[x for x,_ in terms],common_errors=[x for x,_ in errors],possible_components=dependencies,first_seen=items[0].created_at,last_seen=items[-1].created_at,confidence=round(confidence,2),status="Detected"))
        number+=1
    return clusters

def correlate_changes(ticket:Any)->list[dict[str,Any]]:
    results=[];ticket_terms=set(tokens(" ".join([ticket.description,*ticket.technical_terms])))
    deps=set(SERVICES.get(ticket.application,{}).get("dependencies",[]))
    for change in CHANGES:
        minutes=(ticket.created_at-change["start_time"]).total_seconds()/60
        if minutes < -15 or minutes > 180:continue
        component_match=change["component"] in deps or change["component"]==ticket.application
        app_match=change["application"]==ticket.application
        shared=sorted(ticket_terms & set(change["tags"]))
        if not (component_match or app_match or shared):continue
        score=.25+(.3 if component_match else 0)+(.2 if app_match else 0)+min(.15,len(shared)*.05)+(.1 if 0<=minutes<=90 else 0)
        results.append({**change,"minutes_before_ticket":round(minutes),"shared_tags":shared,"correlation":round(min(.95,score),2),"relationship":"Strong" if score>=.75 else "Moderate" if score>=.5 else "Weak","language":"Possible relationship based on timing and configured service metadata."})
    return sorted(results,key=lambda x:x["correlation"],reverse=True)

def aggregate_outcomes(case_matches:list[dict[str,Any]])->dict[str,Any]:
    stats=defaultdict(lambda:{"success":0,"failure":0})
    for case in case_matches:
        for step in case.get("successful_steps",[]):stats[step]["success"]+=1
        for step in case.get("failed_steps",[]):stats[step]["failure"]+=1
    rows=[{"step":step,**counts} for step,counts in stats.items()]
    rows.sort(key=lambda x:(x["success"]-x["failure"],x["success"]),reverse=True)
    summary=(f"Among similar historical cases, {rows[0]['step'].lower()} has the strongest successful outcome." if rows and rows[0]["success"]>rows[0]["failure"] else "Historical evidence is limited or mixed; analyst review is required.")
    return {"similar_cases":len(case_matches),"outcomes":rows,"summary":summary}

def knowledge_health(article)->KnowledgeHealth:
    total=article.successful_resolutions+article.failed_resolutions
    rate=article.successful_resolutions/total if total else 0
    reviewed=datetime.fromisoformat(article.last_updated).replace(tzinfo=timezone.utc)
    days=max(0,(datetime.now(timezone.utc)-reviewed).days)
    conflicts=len(article.conflicts_with);reasons=[]
    if rate<.5:reasons.append("Resolution success rate is below 50%")
    elif rate<.75:reasons.append("Resolution outcomes are mixed")
    else:reasons.append("Resolution success rate is strong")
    if days>365:reasons.append("Article has not been reviewed in over one year")
    elif days>90:reasons.append("Article review is older than 90 days")
    else:reasons.append("Article was reviewed recently")
    if conflicts:reasons.append(f"{conflicts} known procedural conflict requires analyst awareness")
    positive=article.success_feedback;negative=article.negative_feedback
    if rate<.5 or (positive+negative and positive/(positive+negative)<.5):status="Poor"
    elif rate<.75 or days>365 or conflicts>1:status="Needs Review"
    else:status="Healthy"
    return KnowledgeHealth(kb_id=article.kb_id,usage_count=article.usage,positive_feedback=positive,negative_feedback=negative,successful_resolutions=article.successful_resolutions,failed_resolutions=article.failed_resolutions,success_rate=round(rate,2),last_reviewed=article.last_updated,days_since_review=days,conflict_count=conflicts,health_status=status,health_reasons=reasons)

def knowledge_conflicts(matches:list[dict[str,Any]]|None=None)->list[dict[str,Any]]:
    ids={m["kb_id"] for m in matches if m.get("score",0)>=.55} if matches else {k.kb_id for k in KB}
    seen=set();result=[]
    for article in KB:
        for other in article.conflicts_with:
            pair=tuple(sorted((article.kb_id,other)))
            if pair in seen or not set(pair)<=ids:continue
            seen.add(pair);result.append({"articles":list(pair),"reason":"Troubleshooting sequence differs between structured procedures.","action":"Analyst review required."})
    return result

def evidence_strength(ticket)->dict[str,Any]:
    reasons=[];score=0
    if ticket.reliable_match:score+=2;reasons.append("A reliable knowledge match supports the recommendation")
    supporting=sum(m.get("score",0)>=.55 for m in ticket.kb_matches)
    if supporting>1:score+=1;reasons.append(f"{supporting} knowledge articles provide supporting evidence")
    if ticket.historical_confidence>=.75:score+=1;reasons.append("A strongly similar historical case was found")
    outcomes=aggregate_outcomes(ticket.case_matches)
    if outcomes["outcomes"] and outcomes["outcomes"][0]["success"]>outcomes["outcomes"][0]["failure"]:score+=1;reasons.append("Historical outcomes consistently favor the leading step")
    label="Strong" if score>=4 else "Moderate" if score>=2 else "Weak"
    return {"label":label,"reasons":reasons or ["Available evidence is limited"]}

def handover(ticket,cluster=None)->dict[str,Any]:
    changes=correlate_changes(ticket); outcomes=aggregate_outcomes(ticket.case_matches)
    return {"ticket_id":ticket.ticket_id,"current_issue":ticket.normalized_description or ticket.description,"ticket_status":ticket.resolution_status,
      "already_attempted":{"failed":[x["step"] for x in outcomes["outcomes"] if x["failure"]],"successful":[x["step"] for x in outcomes["outcomes"] if x["success"]]},
      "evidence":{"knowledge":[{"id":m["kb_id"],"score":m["score"]} for m in ticket.kb_matches[:2]],"historical":[{"id":m["case_id"],"score":m["similarity"]} for m in ticket.case_matches[:2]]},
      "current_recommendation":ticket.recommended_resolution,"related_cluster":{"id":cluster.cluster_id,"ticket_count":len(cluster.ticket_ids)} if cluster else None,
      "possible_related_change":changes[0]["change_id"] if changes else None,"pending_action":ticket.recommended_resolution[-1] if ticket.recommended_resolution else "Analyst investigation required due to insufficient evidence."}

def explanation(ticket,cluster=None)->dict[str,Any]:
    changes=correlate_changes(ticket);outcomes=aggregate_outcomes(ticket.case_matches)
    return {"ticket_evidence":[*ticket.symptoms,*ticket.technical_terms,*([] if ticket.application=="Unknown" else [ticket.application])],
      "classification_evidence":{"category":ticket.category,"subcategory":ticket.subcategory,"confidence":ticket.classification_confidence},
      "knowledge_evidence":[{"id":m["kb_id"],"score":m["score"]} for m in ticket.kb_matches if m.get("score",0)>=.3],
      "historical_evidence":[{"id":m["case_id"],"score":m["similarity"]} for m in ticket.case_matches if m.get("similarity",0)>=.3],
      "historical_outcomes":outcomes,"dependency_evidence":ticket.dependency_impact,"possible_related_change":changes[0] if changes else None,
      "related_cluster":cluster.model_dump() if cluster else None,"evidence_strength":evidence_strength(ticket),"knowledge_conflicts":knowledge_conflicts(ticket.kb_matches)}
