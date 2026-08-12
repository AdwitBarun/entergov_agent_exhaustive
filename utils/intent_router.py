import re
GOV = r"risk|finding|issue|governance|compliance|pii|metadata|schema|drift|remediation|column|null|duplicate|data quality|review queue|policy|evidence|why failed|root cause|recommendation|severity|confidence|affected records|lineage|catalog|mask|retention"
DATA = r"show rows|top records|average|count|group by|filter|summarize column|min|max|distribution|unique values|missing values|describe data|top customers|transaction amount|rows|columns|dataset|dataframe|mean|median|sum"
def classify_user_intent(q):
    q=(q or "").lower()
    if re.search(GOV,q): return "governance"
    if re.search(DATA,q): return "data_analysis"
    return "general"
