"""
agents/metadata_agent.py
===========================
Deterministic Metadata Agent. Builds a simple data catalog from the profile
(one entry per column: classification, criticality, nullability, lineage
status) and flags columns that need an assigned owner but don't appear to
have one (lineage_status/certification_status are always "Unknown"/
"Uncertified" placeholders in this version - see ARCHITECTURE.md "Known Gaps",
there's no actual ownership/lineage data source wired in).

Called from: core/orchestrator.py -> metadata_agent.run(profile)
"""
from core.models import AgentResult, Finding


def run(profile):
    """
    Builds `metadata['catalog']` (a list of per-column catalog entries, shown
    in the 'Policy & Metadata' tab) and raises META-CAT-001 if any column
    that's sensitive/high-criticality lacks explicit owner metadata.
    """
    dataset = profile.get("dataset",{}).get("name","uploaded_dataset"); catalog=[]; missing=[]
    for c in profile.get("columns_profile", []):
        cls = "Sensitive / PII" if c.get("potential_pii") else "Business Data"; needs = cls == "Sensitive / PII" or c.get("business_criticality") in {"critical", "high"}
        catalog.append({"column": c["column"], "data_type": c.get("dtype"), "semantic_type": c.get("semantic_type"), "classification": cls, "nullable": c.get("is_nullable"), "unique_ratio": c.get("unique_ratio"), "business_criticality": c.get("business_criticality"), "needs_owner": needs, "lineage_status": "Unknown", "certification_status": "Uncertified"})
        if needs: missing.append(c["column"])
    findings=[]
    if missing:
        findings.append(Finding("Metadata Agent", "META-CAT-001", "medium", "Important fields lack owner, lineage or certification metadata.", "Add owner, source system, lineage, refresh SLA, retention period and certification status.", dataset, None, .86, {"columns": missing[:20], "affected_records": 0}, "Unclear ownership and lineage slows incident response and governance approvals.", False, True, "Catalog Completeness", "Data Owner Review"))
    return AgentResult("Metadata Agent", "Issues Found" if findings else "Healthy", max(0,100-len(missing)*3), f"Cataloged {len(catalog)} columns.", findings, {"catalog": catalog})
