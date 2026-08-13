"""
agents/data_quality_agent.py
==============================
Deterministic Data Quality Agent - the most detailed of the six primary
agents. Checks six DQ dimensions against the raw DataFrame and the profile:

  completeness  - % semantic-null values per column (config/dq_config.py thresholds)
  uniqueness    - exact duplicate rows + near-constant columns
  validity      - numeric values outside expected ranges (age, price, etc.)
  consistency   - date-pair logic (e.g. updated_at earlier than created_at)
  integrity     - hardcoded to 100 in this version (not actually computed;
                  see ARCHITECTURE.md "Known Gaps")
  timeliness    - hardcoded to 100 in this version (same gap)

Called from: core/orchestrator.py -> data_quality_agent.run(df, profile)
"""
import re, pandas as pd
from core.models import AgentResult, Finding
from config.dq_config import DQ_CONFIG


def semantic_null_mask(s, config=None):
    """Boolean mask of values that are either a true NaN or a string matching config['semantic_nulls'] (e.g. 'n/a', 'unknown')."""
    config = config or DQ_CONFIG
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
        return s.isna() | s.astype("string").str.strip().str.lower().isin(config.get("semantic_nulls", set()))
    return s.isna()


def null_severity(pct, config):
    """Map a null-percentage to a severity label using config['null_thresholds'], or None if below the lowest threshold."""
    t = config.get("null_thresholds", {})
    if pct >= t.get("high", 40): return "high"
    if pct >= t.get("medium", 20): return "medium"
    if pct >= t.get("low", 5): return "low"
    return None


def is_likely_categorical(s):
    """True if a column looks categorical (bool dtype, or few unique values relative to row count) - used to skip the 'constant column' check for genuinely categorical fields like status/gender."""
    if len(s) == 0: return False
    if pd.api.types.is_bool_dtype(s): return True
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s) or pd.api.types.is_categorical_dtype(s):
        return s.nunique(dropna=True) <= max(50, int(len(s) * .05))
    return False


def make(rule, sev, issue, rec, dataset, column=None, conf=1.0, evidence=None, impact=None, auto=False, route=None):
    """Small factory to build a Finding with agent="Data Quality Agent" and a sensible default route based on severity/auto-remediability."""
    route = route or ("Block Pipeline" if sev == "critical" else "Human Review" if sev == "high" else "Auto-fix" if auto else "Auto-log")
    return Finding("Data Quality Agent", rule, sev, issue, rec, dataset, column, conf, evidence or {}, impact or "Data quality issue may reduce reliability.", auto, None, rule.split("-")[1] if "-" in rule else "Quality", route)


def numeric_validity(df, dataset, config):
    """Check every numeric column against config['generic_numeric_rules'] (matched by substring on column name) and flag out-of-range values."""
    out = []
    for col in df.select_dtypes(include="number").columns:
        matched = None; key_name = None
        for k, rule in config.get("generic_numeric_rules", {}).items():
            if k in col.lower(): matched = rule; key_name = k; break
        if not matched: continue
        s = df[col]; bad = pd.Series(False, index=s.index)
        if matched.get("min") is not None: bad = bad | (s < matched["min"])
        if matched.get("max") is not None: bad = bad | (s > matched["max"])
        invalid = int(bad.fillna(False).sum())
        if invalid:
            out.append(make(f"DQ-VALID-{key_name.upper()}-001", matched.get("severity", "medium"), f"Column '{col}' contains {invalid} values outside the expected range.", "Validate source constraints and transformation logic.", dataset, col, .95, {"invalid_records": invalid, "affected_records": invalid, "affected_pct": round(invalid/max(len(df),1)*100,2), "valid_range": [matched.get("min"), matched.get("max")]}, "Invalid numeric values can distort reporting and decision rules."))
    return out


def date_consistency(df, dataset):
    """Check known date-pair columns (created_at/updated_at, start_date/end_date) for logical inconsistency (end earlier than start)."""
    out = []; lower = {c.lower(): c for c in df.columns}
    for left, right in [("created_at", "updated_at"), ("start_date", "end_date")]:
        if left in lower and right in lower:
            a = pd.to_datetime(df[lower[left]], errors="coerce"); b = pd.to_datetime(df[lower[right]], errors="coerce")
            invalid = int((b < a).fillna(False).sum())
            if invalid:
                out.append(make("DQ-CONS-001", "high", f"{invalid} records have {right} earlier than {left}.", "Investigate timestamp generation, timezone conversion and ETL mapping.", dataset, None, .96, {"invalid_records": invalid, "affected_records": invalid, "affected_pct": round(invalid/max(len(df),1)*100,2), "date_pair": [left, right]}, "Temporal inconsistency can break lifecycle reporting and audit trails."))
    return out


def run(df, profile=None, config=None):
    """
    Entry point called by core/orchestrator.py. Returns an AgentResult with:
      - findings for: missing dataset/empty dataset, per-column completeness,
        exact duplicate rows, near-constant columns, out-of-range numerics,
        inconsistent date pairs.
      - metadata['dimension_scores']: the six DQ dimension scores (0-100 each),
        combined via config['dimension_weights'] into the overall `score`.
    """
    config = config or DQ_CONFIG; dataset = ((profile or {}).get("dataset") or {}).get("name", "uploaded_dataset"); findings = []
    if df is None:
        return AgentResult("Data Quality Agent", "Critical", 0, "Input dataset is missing.", [make("DQ-INPUT-001", "critical", "Input dataset is None.", "Validate upstream ingestion.", dataset, evidence={"dataset_present": False})], {"dimension_scores": {}})
    if df.empty:
        dims = {k: 0 for k in ["completeness", "uniqueness", "validity", "consistency", "integrity", "timeliness"]}
        return AgentResult("Data Quality Agent", "Critical", 0, "Dataset is empty.", [make("DQ-EMPTY-001", "critical", "Dataset contains zero records.", "Investigate upstream ingestion or source availability.", dataset, evidence={"row_count": 0})], {"dimension_scores": dims, "critical_findings": 1})
    rows = len(df); comp = []; critical = {c.lower() for c in config.get("critical_columns", set())}
    for col in df.columns:
        null_count = int(semantic_null_mask(df[col], config).sum()); pct = null_count / rows * 100; comp.append(max(0, 100-pct)); sev = null_severity(pct, config)
        optional = any(re.search(pat, col.lower()) for pat in config.get("optional_column_name_patterns", []))
        if optional and col.lower() not in critical: sev = None
        if col.lower() in critical and pct > 0: sev = "critical"
        if sev:
            findings.append(make("DQ-COMP-001", sev, f"Column '{col}' has {pct:.2f}% missing or semantic-null values.", "Investigate upstream data generation, mapping, or mandatory-field validation.", dataset, col, .99, {"null_count": null_count, "null_pct": round(pct,2), "row_count": rows, "affected_records": null_count, "affected_pct": round(pct,2), "semantic_nulls_applied": True}, "Missing values may reduce analytical reliability and downstream processing quality."))
    dup = int(df.duplicated().sum())
    if dup:
        pct=dup/rows*100; sev="high" if pct>=5 else "medium"
        findings.append(make("DQ-UNIQ-001", sev, f"{dup} exact duplicate rows detected ({pct:.2f}%).", "Deduplicate using appropriate business keys and survivorship rules.", dataset, None, .99, {"duplicate_rows": dup, "duplicate_pct": round(pct,2), "affected_records": dup, "affected_pct": round(pct,2)}, "Duplicates may inflate metrics and downstream aggregations."))
    for col in df.columns:
        if is_likely_categorical(df[col]): continue
        uniq = int(df[col].nunique(dropna=True))
        if uniq <= 1:
            findings.append(make("DQ-UNIQ-002", "medium", f"Column '{col}' contains only {uniq} unique non-null value.", "Confirm whether this is valid constant field or failed mapping/default value.", dataset, col, .82, {"unique_count": uniq, "row_count": rows}, "Constant fields may indicate failed mapping or information loss."))
    findings += numeric_validity(df, dataset, config) + date_consistency(df, dataset)
    # integrity and timeliness are placeholders fixed at 100 - see ARCHITECTURE.md "Known Gaps".
    dims = {"completeness": round(sum(comp)/len(comp),2), "uniqueness": round(max(0,100-dup/rows*100),2), "validity": round(max(0,100-sum(int(x.evidence.get("invalid_records",0)) for x in findings if x.rule_id.startswith("DQ-VALID"))/rows*100),2), "consistency": round(max(0,100-sum(int(x.evidence.get("invalid_records",0)) for x in findings if x.rule_id.startswith("DQ-CONS"))/rows*100),2), "integrity": 100, "timeliness": 100}
    score = round(sum(dims[k]*v for k,v in config.get("dimension_weights", {}).items()),2); counts={}
    for x in findings: counts[x.severity] = counts.get(x.severity,0)+1
    return AgentResult("Data Quality Agent", "Healthy" if not findings else "Critical" if counts.get("critical") else "Issues Found", score, f"Quality score {score}. Findings: {len(findings)} across DQ dimensions.", findings, {"dimension_scores": dims, "finding_summary": counts, "total_findings": len(findings), "critical_findings": counts.get("critical",0)})
