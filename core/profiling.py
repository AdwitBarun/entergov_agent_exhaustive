from __future__ import annotations
import re
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd, numpy as np
PII_NAME_HINTS = {"email": r"email|e_mail|mail", "phone": r"phone|mobile|contact|msisdn|telephone", "aadhaar": r"aadhaar|aadhar|uidai", "pan": r"\bpan\b|tax_id", "passport": r"passport", "name": r"name|fullname|customer_name|employee_name", "address": r"address|street|city|state|pincode|pin_code|zip", "dob": r"dob|birth|date_of_birth", "credential": r"password|secret|token|api_key|apikey|access_key"}
PII_VALUE_PATTERNS = {"email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "phone": r"(?:\+?91[-\s]?)?[6-9]\d{9}", "aadhaar": r"\b\d{4}\s?\d{4}\s?\d{4}\b", "pan": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "api_key": r"(?i)(api[_-]?key|secret|token)[=: ]+[A-Za-z0-9_\-]{12,}"}
def infer_semantic_type(s, col):
    low = col.lower()
    for label, pat in PII_NAME_HINTS.items():
        if re.search(pat, low): return label
    if pd.api.types.is_datetime64_any_dtype(s): return "date"
    if pd.api.types.is_numeric_dtype(s): return "numeric"
    return "categorical" if s.nunique(dropna=True) / max(len(s.dropna()), 1) < .1 else "text"
def criticality(col, sem):
    if re.search(r"(^id$|customer_id|employee_id|order_id|transaction_id|account_id|invoice_id|primary|key)", col.lower()): return "critical"
    if sem in {"aadhaar", "pan", "passport", "credential"}: return "critical"
    if sem in {"email", "phone", "dob", "address", "name"}: return "high"
    return "medium"
def profile_dataframe(df: pd.DataFrame, dataset_name: Optional[str] = None, source="uploaded_file") -> Dict[str, Any]:
    rows = len(df); cols = []
    for col in df.columns:
        s = df[col]; non = s.dropna(); unique = int(non.nunique()); sem = infer_semantic_type(s, col); sample = " ".join(non.astype(str).head(250).tolist())
        hits = []
        for typ, pat in PII_VALUE_PATTERNS.items():
            found = re.findall(pat, sample, flags=re.I)
            if found: hits.append({"type": typ, "count_in_sample": len(found)})
        stats = {}
        if pd.api.types.is_numeric_dtype(s):
            stats = {"min": float(np.nanmin(s)) if len(non) else None, "max": float(np.nanmax(s)) if len(non) else None, "mean": float(np.nanmean(s)) if len(non) else None, "std": float(np.nanstd(s)) if len(non) else None, "negative_count": int((s < 0).sum()), "zero_count": int((s == 0).sum())}
        null = int(s.isna().sum()); card = round(unique / max(rows, 1), 4)
        cols.append({"name": col, "column": col, "dtype": str(s.dtype), "semantic_type": sem, "potential_pii": sem in PII_NAME_HINTS or bool(hits), "null_count": null, "null_pct": round(null/max(rows,1)*100,2), "unique_count": unique, "unique_ratio": card, "cardinality_ratio": card, "duplicate_value_count": max(0, rows-unique-null), "top_values": s.value_counts(dropna=True).head(5).to_dict(), "examples": [str(x)[:80] for x in non.head(5).tolist()], "pii_name_hint": sem in PII_NAME_HINTS, "pii_value_hits": hits, "numeric_stats": stats, "is_nullable": null > 0, "business_criticality": criticality(col, sem), "min": stats.get("min"), "max": stats.get("max")})
    return {"dataset": {"name": dataset_name or "uploaded_dataset", "source": source, "row_count": rows, "column_count": len(df.columns), "snapshot_time": datetime.utcnow().isoformat(timespec="seconds") + "Z", "last_updated": None}, "columns": cols, "columns_profile": cols, "relationships": [], "schema_version": None, "duplicate_rows": int(df.duplicated().sum()) if rows else 0, "historical_profiles": [], "rows": rows, "columns_count": len(df.columns)}
