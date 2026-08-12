import re, pandas as pd
def summarize_dataframe(df):
    if df is None: return {"available":False}
    return {"available":True,"rows":len(df),"columns":len(df.columns),"column_names":list(df.columns),"dtypes":{c:str(t) for c,t in df.dtypes.items()},"null_counts":df.isna().sum().to_dict(),"duplicate_rows":int(df.duplicated().sum()),"numeric_summary":df.describe(include="number").to_dict() if len(df.select_dtypes(include="number").columns) else {}}
def answer_simple_data_question(q,df):
    if df is None: return None
    q=q.lower(); s=summarize_dataframe(df)
    if "row" in q and any(x in q for x in ["how many","number","count"]): return f"The uploaded dataset has {s['rows']} rows."
    if "column" in q and any(x in q for x in ["how many","number","list"]): return f"The dataset has {s['columns']} columns: {', '.join(s['column_names'])}."
    if "duplicate" in q: return f"The dataset has {s['duplicate_rows']} exact duplicate rows."
    if "missing" in q or "null" in q: return "Missing values by column:\n" + "\n".join([f"- {k}: {v}" for k,v in s['null_counts'].items()])
    m=re.search(r"(mean|average|min|max|sum)\s+(?:of\s+)?([a-zA-Z0-9_]+)",q)
    if m:
        op,col=m.group(1),m.group(2); match=[c for c in df.columns if c.lower()==col.lower()]
        if match and pd.api.types.is_numeric_dtype(df[match[0]]):
            ss=df[match[0]]; val={"mean":ss.mean(),"average":ss.mean(),"min":ss.min(),"max":ss.max(),"sum":ss.sum()}[op]
            return f"{op.title()} of {match[0]} is {val:.4g}."
    return None
def dataframe_context(df): return {"summary":summarize_dataframe(df),"sample_rows":df.head(20).to_dict(orient="records") if df is not None else []}
