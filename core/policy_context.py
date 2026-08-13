"""
core/policy_context.py
========================
Turns free-text policy content (extracted from an uploaded PDF) into a list
of PolicyRule objects, using two strategies:

1. Keyword matching against a small set of built-in DEFAULT_POLICY_PATTERNS
   (e.g. "does this document mention PII masking / retention / consent /
   access control / quality thresholds?").
2. Sentence-level scanning for imperative language ("must", "shall",
   "required", "prohibited", ...) to capture custom, document-specific rules
   that aren't covered by the built-in patterns.

Called from: core/orchestrator.py -> parse_policy_text(policy_text), which
then feeds the resulting rules into the Compliance Agent and Business Rule Agent.

LIMITATION (worth knowing): this is regex/keyword-based, not an LLM parse
of the policy document. It's fast and free, but it will miss nuanced or
implicitly-stated obligations, and rule.pattern for PDF-derived rules is
just the escaped sentence text (not a reusable pattern).
"""
import re
from core.models import PolicyRule

# (rule_id, title, keyword regex, default severity) for the built-in policy
# categories this app always checks for regardless of document phrasing.
DEFAULT_POLICY_PATTERNS = [("POL-PII-MASK", "PII must be masked or encrypted", r"pii|personal data|aadhaar|pan|passport|phone|email|mask|encrypt", "high"), ("POL-RETENTION", "Retention period policy", r"retention|retain|delete after|archive|years", "medium"), ("POL-CONSENT", "Consent and purpose limitation", r"consent|purpose limitation|marketing|legal basis|opt[- ]?in", "high"), ("POL-ACCESS", "Access control policy", r"access control|rbac|abac|public access|restricted|privilege", "critical"), ("POL-QUALITY", "Data quality threshold policy", r"quality|completeness|accuracy|validity|sla|freshness", "medium")]


def clean_text(t):
    """Collapse all whitespace runs (newlines, tabs, multiple spaces) into single spaces and strip the ends."""
    return re.sub(r"\s+", " ", t or "").strip()


def parse_policy_text(text):
    """
    Parse raw policy/issue-document text into a list of PolicyRule objects.

    Step 1: check the whole document against each DEFAULT_POLICY_PATTERNS
            keyword regex; add a rule for each category that matches.
    Step 2: split into sentences and flag any sentence containing imperative
            language (must/required/shall/prohibited/etc.) as a custom rule,
            with severity escalated to "high" for stronger imperative words
            (must/shall/prohibited/not allowed/approval) vs "medium" for
            softer ones (should).

    Capped at 40 rules total to avoid overwhelming the UI/LLM context on
    very long policy documents.
    """
    rules = []; t = clean_text(text); tl = t.lower()
    for rid, title, pat, sev in DEFAULT_POLICY_PATTERNS:
        if re.search(pat, tl, re.I): rules.append(PolicyRule(rid, title, pat, sev, "Policy", "Human Review"))
    idx = 1
    for sent in re.split(r"(?<=[.!?])\s+", t):
        if re.search(r"must|required|should|shall|not allowed|prohibited|approval|encrypt|mask", sent, re.I):
            sev = "high" if re.search(r"must|shall|prohibited|not allowed|approval", sent, re.I) else "medium"
            rules.append(PolicyRule(f"PDF-CUSTOM-{idx:03d}", sent[:90], re.escape(sent[:40]), sev, "Company Policy", "Human Review", .65)); idx += 1
    return rules[:40]


def policy_summary(rules):
    """Small summary dict (total rule count, high/critical count, category list) shown in the 'Policy & Metadata' tab."""
    return {"total_policy_rules": len(rules), "critical_or_high": sum(1 for r in rules if r.severity in {"high", "critical"}), "categories": sorted(set(r.category for r in rules))}
