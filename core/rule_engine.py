"""
core/rule_engine.py
=====================
Deterministic post-processing applied AFTER all agents have produced their
raw Findings, and BEFORE the LLM reasoning layer runs.

This module does three things, all rule-based (no LLM involved):
1. normalize_route()  - decides which review queue/route a Finding goes to,
                         overriding whatever the originating agent guessed,
                         based on severity/confidence/regulatory flags.
2. risk_score()        - converts a Finding into a single 0-100 risk number.
3. aggregate_results()  - merges every agent's AgentResult into the final
                          `result` dict consumed by core/orchestrator.py,
                          agents/reasoning_agents.py and app.py. This also
                          writes the audit trail (AuditEvent per finding).

Called from: core/orchestrator.py -> aggregate_results(results, dataset_name)
"""
from core.models import SEVERITY_WEIGHT, AuditEvent, now_iso

# All possible values a Finding.route can end up with.
ROUTES = ["Block Pipeline", "Compliance Review", "Security Review", "Human Review", "Data Owner Review", "Approval Required", "Auto-fix", "Auto-log"]


def normalize_route(f):
    """
    Recompute the routing decision for a Finding using fixed business rules
    (not the route the individual agent originally assigned), so that
    routing is consistent across every agent:

    - critical severity  -> always one of the "stop the pipeline" routes.
    - low confidence + medium/high severity -> force Human Review (don't
      trust an uncertain automated call for anything risky).
    - regulatory_impact True -> force Compliance Review.
    - otherwise, keep whatever route the agent originally set.
    """
    if f.severity == "critical": return f.route if f.route in {"Block Pipeline", "Compliance Review", "Security Review"} else "Block Pipeline"
    if f.confidence < .85 and f.severity in {"medium", "high"}: return "Human Review"
    if f.regulatory_impact: return "Compliance Review"
    return f.route or "Auto-log"


def risk_score(f):
    """
    Compute a 0-100 risk score for a single Finding from four weighted signals:
    - severity (up to 55 points, via SEVERITY_WEIGHT)
    - blast radius: affected_pct and affected_rows (up to 25 points)
    - regulatory_impact flag (flat +12 points if True)
    - model confidence (up to 8 points)
    The result is clamped to [0, 100].
    """
    return int(min(100, round(SEVERITY_WEIGHT.get(f.severity,.5)*55 + min(25,(f.affected_pct or 0)*.25+min(f.affected_rows or 0,10000)/10000*10) + (12 if f.regulatory_impact else 0) + max(0,min(8,f.confidence*8)))))


def aggregate_results(agent_results, dataset_name="uploaded_dataset"):
    """
    Merge a list of AgentResult objects (one per agent that ran) into the
    single aggregated dict that flows through the rest of the app.

    For every Finding across every agent:
      - overwrite its route via normalize_route()
      - compute and attach its risk_score
      - append an AuditEvent recording that the finding was generated

    Returns a dict with keys:
      agent_cards   - small summary per agent, used for the "Agent Health" cards in app.py
      findings      - all findings across all agents, sorted by risk_score descending
      overall       - aggregate risk, max risk, severity/route counts, review-queue size
      audit         - list of AuditEvent dicts (one per finding), shown in the Audit Trail tab

    NOTE: this function does NOT call any LLM. LLM enrichment happens
    afterwards in agents/reasoning_agents.py::enrich_governance_result().
    """
    cards=[]; scored=[]; audit=[]
    for r in agent_results:
        cards.append({"agent": r.agent, "status": r.status, "score": round(float(r.score),2), "summary": r.summary})
        for f in r.findings:
            f.route=normalize_route(f); f.risk_score=risk_score(f); d=f.to_dict(); d["dataset"]=d.get("dataset") or dataset_name
            if not isinstance(d.get("evidence"), dict): d["evidence"]={"items": d.get("evidence", [])}
            d["risk_score"]=f.risk_score; scored.append(d)
            audit.append(AuditEvent(now_iso(), f.agent, "finding.generated", {"finding_id": f.finding_id, "rule_id": f.rule_id, "severity": f.severity, "route": f.route}).__dict__)
    # Aggregate risk = average risk score of non-"info" findings, nudged up by
    # how many such findings there are (capped at +20), then clamped to 100.
    non=[x for x in scored if x["severity"] != "info"]; agg=min(100, int(sum(x["risk_score"] for x in non)/max(1,len(non))+min(20,len(non)))) if non else 0
    sev={s: sum(1 for x in scored if x["severity"]==s) for s in ["critical","high","medium","low","info"]}; routes={r:sum(1 for x in scored if x["route"]==r) for r in ROUTES}
    review=[x for x in scored if x["route"] in {"Block Pipeline","Compliance Review","Security Review","Human Review","Data Owner Review","Approval Required"}]; low=[x for x in scored if x["confidence"]<.85 and x["severity"]!="info"]
    return {"agent_cards":cards,"findings":sorted(scored,key=lambda x:x["risk_score"],reverse=True),"overall":{"max_risk":max([x["risk_score"] for x in scored],default=0),"aggregate_risk":agg,"total_findings":len(scored),"review_queue":len(review),"low_confidence":len(low),"severity_counts":sev,"routes":routes},"audit":audit}
