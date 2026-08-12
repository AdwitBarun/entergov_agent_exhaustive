from core.models import AgentResult, Finding
MAP = {"COMP": "Backfill from source, apply mandatory-field validation and quarantine incomplete records.", "UNIQ": "Apply survivorship rules using stable business keys.", "VALID": "Add domain constraints and reject invalid ranges at ingestion.", "PII/Sensitive Data": "Mask or tokenize sensitive fields, enforce RBAC and validate consent/purpose.", "Data Contract": "Block breaking changes until downstream contracts are updated and approved.", "PDF/OCR": "Run OCR and route low-confidence detections to review."}
def run(findings):
    out=[]
    for x in findings:
        if x.severity in {"medium", "high", "critical"}:
            action = MAP.get(x.category, x.recommendation)
            out.append(Finding("Remediation Agent", "REM-ACTION-001", x.severity, f"Remediate: {x.issue}", "Approve remediation, execute, then rerun validation to verify improvement.", x.dataset, x.column, min(x.confidence,.9), {"source_finding_id": x.finding_id, "suggested_action": action, "affected_records": x.affected_rows, "affected_pct": x.affected_pct}, x.business_impact, x.severity == "medium", x.severity in {"high", "critical"}, "Recommended Action", "Approval Required" if x.severity in {"high", "critical"} else "Auto-fix", x.regulatory_impact))
    return AgentResult("Remediation Agent", "Ready", max(0,100-len(out)*5), f"Generated {len(out)} remediation candidates.", out)
