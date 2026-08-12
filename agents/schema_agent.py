from difflib import get_close_matches
from core.models import AgentResult, Finding
def run(profile, baseline=None):
    dataset = profile.get("dataset",{}).get("name","uploaded_dataset"); current = {c["column"]: c.get("dtype") for c in profile.get("columns_profile", [])}; findings=[]
    if not baseline:
        findings.append(Finding("Schema/Data Contract Agent", "SCH-BASE-001", "info", "No baseline schema or data contract was provided.", "Save this trusted run as a baseline or upload a data contract for future comparison.", dataset, None, 1.0, {"current_columns": list(current)}, "Schema drift cannot be fully classified without a baseline.", False, False, "Baseline Missing", "Auto-log"))
        return AgentResult("Schema/Data Contract Agent", "Baseline Needed", 90, "No baseline provided. Drift check is informational.", findings, {"current_schema": current})
    prev = baseline.get("schema", baseline if isinstance(baseline, dict) else {})
    added = sorted(set(current) - set(prev)); removed = sorted(set(prev) - set(current)); changed = sorted([c for c in current if c in prev and str(current[c]) != str(prev[c])])
    renamed=[]
    for r in removed:
        m = get_close_matches(r, added, n=1, cutoff=.72)
        if m: renamed.append({"previous": r, "current_candidate": m[0]})
    if added or removed or changed or renamed:
        sev = "critical" if removed or changed else "high" if renamed else "medium"
        findings.append(Finding("Schema/Data Contract Agent", "SCH-DRIFT-001", sev, "Schema drift detected against supplied baseline/data contract.", "Classify breaking vs non-breaking change, update downstream contracts and rerun validation.", dataset, None, .97, {"added": added, "removed": removed, "type_changed": changed, "rename_candidates": renamed}, "Breaking schema changes can fail pipelines, reports and downstream products.", False, True, "Data Contract", "Block Pipeline" if sev == "critical" else "Human Review"))
    return AgentResult("Schema/Data Contract Agent", "Issues Found" if findings else "Healthy", max(0,100-len(findings)*20), f"Schema check: {len(added)} added, {len(removed)} removed, {len(changed)} type changes.", findings, {"current_schema": current})
