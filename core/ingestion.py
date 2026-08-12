from __future__ import annotations
from typing import Dict, Any, Tuple
import pandas as pd
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
MISSING_TOKENS = {"", " ", "na", "n/a", "null", "none", "nan", "unknown", "not available", "-", "--", "?", "9999", "000000"}
def normalize_missing(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].apply(lambda x: None if str(x).strip().lower() in MISSING_TOKENS else x)
    return out
def load_tabular(uploaded_file) -> Tuple[pd.DataFrame, Dict[str, Any]]:
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
    if PdfReader is None: return {"text": "", "extractable": False, "ocr_required": True, "error": "PDF parser unavailable"}
    try:
        r = PdfReader(uploaded_file); pages = []
        for i, p in enumerate(r.pages):
            t = p.extract_text() or ""
            if t.strip(): pages.append(f"[page {i+1}]\n{t}")
        text = "\n".join(pages); return {"text": text, "pages": len(r.pages), "extractable": bool(text.strip()), "ocr_required": not bool(text.strip())}
    except Exception as e: return {"text": "", "extractable": False, "ocr_required": True, "error": str(e)}
