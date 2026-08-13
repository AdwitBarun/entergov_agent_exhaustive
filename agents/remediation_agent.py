"""
agents/remediation_agent.py
==============================
Deterministic Remediation Agent - runs LAST in the pipeline (see
core/orchestrator.py), after every other agent, since it needs their
combined findings as input.

For every medium/high/critical finding, generates a companion "remediation
candidate" Finding suggesting a concrete next action, using a small
category -> action lookup (MAP below). This is suggestion generation only;
it does NOT execute any remediation - "auto_remediable"/route flags just
signal how much human sign-off would be needed before something acts on
these suggestions elsewhere.

Called from: core/orchestrator.py -> remediation_agent.run(base_findings)
"""
from core.models import AgentResult, Finding

# category -> suggested remediation action text. Falls back to the original
# finding's own `recommendation` if its category isn't in this map.
MAP = {"COMP": "Backfill from source, apply mandatory-field validation and quarantine incomplete records.", "UNIQ": "Apply survivorship rules using stable business keys.", "VALID": "Add domain constraints and reject invalid ranges at ingestion.", "PII/Sensitive Data": "Mask or tokenize sensitive fields, enforce RBAC and validate consent/purpose.", "Data Contract": "Block breaking changes until downstream contracts are updated and approved.", "PDF/OCR": "Run OCR and route low-confidence detections to review."}


def run(findings):
    """
    Args:
        findings: flat list of Finding objects from every other agent
                  (built by core/orchestrator.py before calling this).

    Returns an AgentResult whose findings are all category "REM-ACTION-001",
    one per qualifying source finding, carrying a `source_finding_id` in
    evidence so the UI/report can trace a remediation suggestion back to the
    original issue.
    """
    out=[]
    for x in findings:
        if x.severity in {"medium", "high", "critical"}:
            action = MAP.get(x.category, x.recommendation)
            out.append(Finding("Remediation Agent", "REM-ACTION-001", x.severity, f"Remediate: {x.issue}", "Approve remediation, execute, then rerun validation to verify improvement.", x.dataset, x.column, min(x.confidence,.9), {"source_finding_id": x.finding_id, "suggested_action": action, "affected_records": x.affected_rows, "affected_pct": x.affected_pct}, x.business_impact, x.severity == "medium", x.severity in {"high", "critical"}, "Recommended Action", "Approval Required" if x.severity in {"high", "critical"} else "Auto-fix", x.regulatory_impact))
    return AgentResult("Remediation Agent", "Ready", max(0,100-len(out)*5), f"Generated {len(out)} remediation candidates.", out)
