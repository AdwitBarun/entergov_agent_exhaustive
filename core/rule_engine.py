from core.models import SEVERITY_WEIGHT, AuditEvent, now_iso
ROUTES = ["Block Pipeline", "Compliance Review", "Security Review", "Human Review", "Data Owner Review", "Approval Required", "Auto-fix", "Auto-log"]
def normalize_route(f):
    if f.severity == "critical": return f.route if f.route in {"Block Pipeline", "Compliance Review", "Security Review"} else "Block Pipeline"
    if f.confidence < .85 and f.severity in {"medium", "high"}: return "Human Review"
    if f.regulatory_impact: return "Compliance Review"
    return f.route or "Auto-log"
def risk_score(f):
    return int(min(100, round(SEVERITY_WEIGHT.get(f.severity,.5)*55 + min(25,(f.affected_pct or 0)*.25+min(f.affected_rows or 0,10000)/10000*10) + (12 if f.regulatory_impact else 0) + max(0,min(8,f.confidence*8)))))
def aggregate_results(agent_results, dataset_name="uploaded_dataset"):
    cards=[]; scored=[]; audit=[]
    for r in agent_results:
        cards.append({"agent": r.agent, "status": r.status, "score": round(float(r.score),2), "summary": r.summary})
        for f in r.findings:
            f.route=normalize_route(f); f.risk_score=risk_score(f); d=f.to_dict(); d["dataset"]=d.get("dataset") or dataset_name
            if not isinstance(d.get("evidence"), dict): d["evidence"]={"items": d.get("evidence", [])}
            d["risk_score"]=f.risk_score; scored.append(d)
            audit.append(AuditEvent(now_iso(), f.agent, "finding.generated", {"finding_id": f.finding_id, "rule_id": f.rule_id, "severity": f.severity, "route": f.route}).__dict__)
    non=[x for x in scored if x["severity"] != "info"]; agg=min(100, int(sum(x["risk_score"] for x in non)/max(1,len(non))+min(20,len(non)))) if non else 0
    sev={s: sum(1 for x in scored if x["severity"]==s) for s in ["critical","high","medium","low","info"]}; routes={r:sum(1 for x in scored if x["route"]==r) for r in ROUTES}
    review=[x for x in scored if x["route"] in {"Block Pipeline","Compliance Review","Security Review","Human Review","Data Owner Review","Approval Required"}]; low=[x for x in scored if x["confidence"]<.85 and x["severity"]!="info"]
    return {"agent_cards":cards,"findings":sorted(scored,key=lambda x:x["risk_score"],reverse=True),"overall":{"max_risk":max([x["risk_score"] for x in scored],default=0),"aggregate_risk":agg,"total_findings":len(scored),"review_queue":len(review),"low_confidence":len(low),"severity_counts":sev,"routes":routes},"audit":audit}
