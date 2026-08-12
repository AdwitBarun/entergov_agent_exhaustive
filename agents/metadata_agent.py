from core.models import AgentResult, Finding
def run(profile):
    dataset = profile.get("dataset",{}).get("name","uploaded_dataset"); catalog=[]; missing=[]
    for c in profile.get("columns_profile", []):
        cls = "Sensitive / PII" if c.get("potential_pii") else "Business Data"; needs = cls == "Sensitive / PII" or c.get("business_criticality") in {"critical", "high"}
        catalog.append({"column": c["column"], "data_type": c.get("dtype"), "semantic_type": c.get("semantic_type"), "classification": cls, "nullable": c.get("is_nullable"), "unique_ratio": c.get("unique_ratio"), "business_criticality": c.get("business_criticality"), "needs_owner": needs, "lineage_status": "Unknown", "certification_status": "Uncertified"})
        if needs: missing.append(c["column"])
    findings=[]
    if missing:
        findings.append(Finding("Metadata Agent", "META-CAT-001", "medium", "Important fields lack owner, lineage or certification metadata.", "Add owner, source system, lineage, refresh SLA, retention period and certification status.", dataset, None, .86, {"columns": missing[:20], "affected_records": 0}, "Unclear ownership and lineage slows incident response and governance approvals.", False, True, "Catalog Completeness", "Data Owner Review"))
    return AgentResult("Metadata Agent", "Issues Found" if findings else "Healthy", max(0,100-len(missing)*3), f"Cataloged {len(catalog)} columns.", findings, {"catalog": catalog})
