import re
from core.models import PolicyRule
DEFAULT_POLICY_PATTERNS = [("POL-PII-MASK", "PII must be masked or encrypted", r"pii|personal data|aadhaar|pan|passport|phone|email|mask|encrypt", "high"), ("POL-RETENTION", "Retention period policy", r"retention|retain|delete after|archive|years", "medium"), ("POL-CONSENT", "Consent and purpose limitation", r"consent|purpose limitation|marketing|legal basis|opt[- ]?in", "high"), ("POL-ACCESS", "Access control policy", r"access control|rbac|abac|public access|restricted|privilege", "critical"), ("POL-QUALITY", "Data quality threshold policy", r"quality|completeness|accuracy|validity|sla|freshness", "medium")]
def clean_text(t): return re.sub(r"\s+", " ", t or "").strip()
def parse_policy_text(text):
    rules = []; t = clean_text(text); tl = t.lower()
    for rid, title, pat, sev in DEFAULT_POLICY_PATTERNS:
        if re.search(pat, tl, re.I): rules.append(PolicyRule(rid, title, pat, sev, "Policy", "Human Review"))
    idx = 1
    for sent in re.split(r"(?<=[.!?])\s+", t):
        if re.search(r"must|required|should|shall|not allowed|prohibited|approval|encrypt|mask", sent, re.I):
            sev = "high" if re.search(r"must|shall|prohibited|not allowed|approval", sent, re.I) else "medium"
            rules.append(PolicyRule(f"PDF-CUSTOM-{idx:03d}", sent[:90], re.escape(sent[:40]), sev, "Company Policy", "Human Review", .65)); idx += 1
    return rules[:40]
def policy_summary(rules): return {"total_policy_rules": len(rules), "critical_or_high": sum(1 for r in rules if r.severity in {"high", "critical"}), "categories": sorted(set(r.category for r in rules))}
