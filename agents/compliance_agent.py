from core.models import AgentResult, Finding
SENSITIVE = {"email", "phone", "aadhaar", "pan", "passport", "name", "address", "dob", "credential"}
def run(profile, policy_rules=None, pdf_text_profile=None):
    rules = policy_rules or []; findings = []; dataset = profile.get("dataset",{}).get("name","uploaded_dataset"); rows = profile.get("rows",0)
    for c in profile.get("columns_profile", []):
        col = c["column"]; sem = c.get("semantic_type"); hits = c.get("pii_value_hits", [])
        if sem in SENSITIVE or hits:
            sev = "critical" if sem in {"aadhaar", "pan", "passport", "credential"} or any(h["type"] in {"aadhaar", "pan", "api_key"} for h in hits) else "high"
            findings.append(Finding("Compliance Agent", "CMP-PII-001", sev, f"Sensitive or regulated data detected in '{col}'.", "Validate classification, consent, masking/encryption, retention and access control before use.", dataset, col, .95 if hits else .78, {"semantic_type": sem, "value_hits": hits, "affected_records": rows, "affected_pct": 100}, "Privacy, regulatory and trust impact if data is exposed or misused.", False, True, "PII/Sensitive Data", "Compliance Review", True))
    if pdf_text_profile and pdf_text_profile.get("ocr_required"):
        findings.append(Finding("Compliance Agent", "CMP-PDF-001", "medium", "Uploaded policy/issue document may require OCR before full analysis.", "Use a text-native document or OCR pipeline before final scoring.", dataset, None, .9, {"extractable_text": False}, "Scanned documents can hide policy constraints or sensitive data.", False, True, "PDF/OCR", "Human Review"))
    if rules and not findings:
        findings.append(Finding("Compliance Agent", "CMP-POLICY-001", "medium", "Policy context exists but no direct structured compliance hit was found.", "Add purpose, consent, retention, owner and access-control metadata to enable policy-aware checks.", dataset, None, .65, {"rules_loaded": len(rules)}, "Policy cannot be fully enforced without governance metadata.", False, True, "Policy Context", "Human Review"))
    return AgentResult("Compliance Agent", "Issues Found" if findings else "Healthy", max(0,100-len(findings)*15), f"Detected {len(findings)} compliance findings.", findings)
