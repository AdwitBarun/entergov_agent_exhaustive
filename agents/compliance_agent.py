"""
agents/compliance_agent.py
=============================
Deterministic Compliance Agent. Flags columns whose semantic type or
detected value patterns (from core/profiling.py) indicate sensitive/regulated
data (PII, credentials), flags PDF policy documents that need OCR, and
raises a low-confidence "no direct hit" finding if policy context was
loaded but nothing concrete was found (so the gap doesn't go silently unnoticed).

Called from: core/orchestrator.py -> compliance_agent.run(profile, rules, pdf_text_profile)
"""
from core.models import AgentResult, Finding

# Semantic types (from core/profiling.py::infer_semantic_type) considered
# sensitive enough to always raise a compliance finding.
SENSITIVE = {"email", "phone", "aadhaar", "pan", "passport", "name", "address", "dob", "credential"}


def run(profile, policy_rules=None, pdf_text_profile=None):
    """
    Args:
        profile: dict from core.profiling.profile_dataframe().
        policy_rules: list of PolicyRule from core.policy_context.parse_policy_text().
        pdf_text_profile: dict from core.ingestion.extract_pdf_text(), used to
            detect scanned/non-extractable policy PDFs.

    Findings raised:
      CMP-PII-001    - a column's semantic type or value pattern indicates
                       sensitive/regulated data (critical if it's a
                       high-confidence pattern hit like Aadhaar/PAN/API key,
                       high severity otherwise).
      CMP-PDF-001    - the uploaded policy PDF appears to need OCR (no
                       extractable text layer was found).
      CMP-POLICY-001 - policy rules were loaded but no PII/OCR finding was
                       otherwise raised; flags that the policy can't be
                       fully enforced without more governance metadata.
    """
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
