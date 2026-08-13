"""
agents/business_rule_agent.py
================================
Deterministic Business Rule Agent. Runs generic format checks that apply to
ANY dataset regardless of domain: email format validity (matched by column
NAME containing "email") and date parseability / future-date checks
(matched by column NAME containing date/created/updated/start/end).

Also logs (does not yet execute) that policy rules were loaded, as a
reminder that policy clauses need to be turned into real executable checks
- see ARCHITECTURE.md "Known Gaps": policy_rules from core/policy_context.py
are currently NOT compiled into runnable validation logic anywhere in this
codebase; BUS-POLICY-MAP-001 just reports the count.

Called from: core/orchestrator.py -> business_rule_agent.run(df, profile, rules)
"""
import re, pandas as pd
from core.models import AgentResult, Finding


def run(df, profile, policy_rules=None):
    """
    Findings raised:
      BUS-FORMAT-EMAIL-001 - invalid email format in any column whose name
                              contains "email" (auto_remediable=True).
      BUS-DATE-001          - unparsable date values in date-like columns
                              (auto_remediable=True).
      BUS-DATE-002          - dates parsed but land in the future, in
                              columns NOT named like a scheduling field
                              (excludes "expiry"/"future"/"scheduled").
      BUS-POLICY-MAP-001    - informational: policy rules were loaded (see
                              module docstring for the caveat that these
                              aren't yet compiled into executable checks).
    """
    dataset = profile.get("dataset",{}).get("name","uploaded_dataset"); rules = policy_rules or []; findings=[]
    for col in df.columns:
        low=col.lower()
        if "email" in low:
            bad = int((~df[col].dropna().astype(str).str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", na=False)).sum())
            if bad: findings.append(Finding("Business Rule Agent", "BUS-FORMAT-EMAIL-001", "medium", f"Column '{col}' contains invalid email formats.", "Standardize and validate email format at ingestion.", dataset, col, .9, {"invalid_records": bad, "affected_records": bad, "affected_pct": round(bad/max(len(df),1)*100,2)}, "Invalid contact data reduces campaign, CRM and identity matching accuracy.", True, False, "Format", "Auto-fix"))
        if re.search(r"date|created|updated|start|end", low):
            parsed = pd.to_datetime(df[col], errors="coerce"); invalid = int(parsed.isna().sum() - df[col].isna().sum()); future = int((parsed > pd.Timestamp.now()).sum())
            if invalid > 0: findings.append(Finding("Business Rule Agent", "BUS-DATE-001", "medium", f"Column '{col}' contains unparsable date values.", "Normalize date formats and reject unparsable values.", dataset, col, .86, {"invalid_records": invalid, "affected_records": invalid}, "Invalid dates reduce temporal analysis and SLA reliability.", True, False, "Format", "Auto-fix"))
            if future > 0 and not re.search(r"expiry|future|scheduled", low): findings.append(Finding("Business Rule Agent", "BUS-DATE-002", "high", f"Column '{col}' contains future dates outside expected scheduling fields.", "Check timezone conversion, source mapping or invalid data entry.", dataset, col, .8, {"future_dates": future, "affected_records": future, "affected_pct": round(future/max(len(df),1)*100,2)}, "Future-dated business events can distort operational reporting.", False, True, "Temporal", "Human Review"))
    if rules: findings.append(Finding("Business Rule Agent", "BUS-POLICY-MAP-001", "info", "Company policy context was loaded for rule mapping.", "Convert extracted policy clauses into executable validation rules with owners and thresholds.", dataset, None, .7, {"policy_rules": len(rules)}, "Policy rules are more valuable when converted into executable data contracts.", False, False, "Policy-Aware Rules", "Auto-log"))
    return AgentResult("Business Rule Agent", "Issues Found" if findings else "Healthy", max(0,100-len(findings)*8), f"Ran generic business checks and mapped {len(rules)} policy clauses.", findings)
