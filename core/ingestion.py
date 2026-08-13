"""
core/ingestion.py
===================
File-loading layer: turns Streamlit-uploaded files (CSV/XLSX/XLS/PDF) into
a pandas DataFrame + metadata dict, or into extracted PDF text.

This is the very first thing app.py calls when the user clicks
"Run Governance Scan" - before any agent or profiling logic runs.

Called from: app.py -> load_tabular(data_file), extract_pdf_text(policy_pdf)
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import pandas as pd
try:
    from pypdf import PdfReader
except Exception:
    # pypdf is an optional dependency for PDF policy-document parsing; if it's
    # not installed, extract_pdf_text() below degrades gracefully instead of
    # crashing the whole app.
    PdfReader = None

# String values that should be treated as "missing" even though pandas
# wouldn't automatically parse them as NaN (e.g. the literal text "N/A").
MISSING_TOKENS = {"", " ", "na", "n/a", "null", "none", "nan", "unknown", "not available", "-", "--", "?", "9999", "000000"}


def normalize_missing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace common "fake null" string tokens (e.g. "N/A", "unknown", "9999")
    with actual None, for every object/string column. This makes the
    Data Quality Agent's null-detection logic more accurate than relying on
    pandas' default NaN detection alone.
    """
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].apply(lambda x: None if str(x).strip().lower() in MISSING_TOKENS else x)
    return out


def load_tabular(uploaded_file) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load a Streamlit UploadedFile (CSV, XLSX or XLS) into a DataFrame.

    - CSV: tries UTF-8 first, falls back to latin1 on decode errors.
    - Excel: reads ALL sheets and concatenates them into one DataFrame,
      tagging each row with a `__sheet_name` column so multi-sheet workbooks
      don't silently lose data.
    - Applies normalize_missing() before returning.

    Returns (df, meta) where meta includes file_name, file_type, sheet names
    (for Excel), row count and column count.

    Raises ValueError for any other file extension.
    """
    name = uploaded_file.name.lower(); meta = {"file_name": uploaded_file.name, "file_type": name.split(".")[-1]}
    if name.endswith(".csv"):
        try: df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0); df = pd.read_csv(uploaded_file, encoding="latin1")
    elif name.endswith((".xlsx", ".xls")):
        sheets = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl" if name.endswith(".xlsx") else None)
        meta["sheets"] = list(sheets.keys()); df = pd.concat([v.assign(__sheet_name=k) for k, v in sheets.items()], ignore_index=True)
    else: raise ValueError("Unsupported structured file. Upload CSV, XLSX or XLS.")
    df = normalize_missing(df); meta["rows"] = len(df); meta["columns"] = len(df.columns); return df, meta


def extract_pdf_text(uploaded_file) -> Dict[str, Any]:
    """
    Extract text from an uploaded policy/issue PDF, page by page.

    Returns a dict with:
      text          - concatenated text of all pages that had extractable text
      pages         - total page count
      extractable   - True if any text was found
      ocr_required  - True if the PDF appears to be scanned/image-only
                      (no extractable text layer) - flagged as a Compliance
                      Agent finding (CMP-PDF-001) so the user knows results
                      may be incomplete.
      error         - present only if extraction failed outright.

    If pypdf isn't installed, returns ocr_required=True immediately so the
    rest of the pipeline can proceed without a hard crash.
    """
    if PdfReader is None: return {"text": "", "extractable": False, "ocr_required": True, "error": "PDF parser unavailable"}
    try:
        r = PdfReader(uploaded_file); pages = []
        for i, p in enumerate(r.pages):
            t = p.extract_text() or ""
            if t.strip(): pages.append(f"[page {i+1}]\n{t}")
        text = "\n".join(pages); return {"text": text, "pages": len(r.pages), "extractable": bool(text.strip()), "ocr_required": not bool(text.strip())}
    except Exception as e: return {"text": "", "extractable": False, "ocr_required": True, "error": str(e)}
