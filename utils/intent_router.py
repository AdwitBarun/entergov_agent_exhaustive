"""
utils/intent_router.py
=========================
Cheap regex-based intent classifier for the "AI Governance Copilot" chat tab
in app.py. Decides, per user chat message, whether to:
  - answer using the governance scan context (governance_prompt in llm_client.py)
  - answer using a locally-computed data statistic first (utils/data_query.py)
  - answer as a plain general-knowledge question (general_prompt)

This is NOT an LLM call - it's a keyword regex match, done before any LLM
call, to decide which prompt template to build and whether a local
computation can short-circuit the LLM entirely (see app.py's chat handler).

Called from: app.py -> classify_user_intent(prompt)
"""
import re

# Keyword regex for governance/scan-related questions.
GOV = r"risk|finding|issue|governance|compliance|pii|metadata|schema|drift|remediation|column|null|duplicate|data quality|review queue|policy|evidence|why failed|root cause|recommendation|severity|confidence|affected records|lineage|catalog|mask|retention"
# Keyword regex for raw-data/statistics questions.
DATA = r"show rows|top records|average|count|group by|filter|summarize column|min|max|distribution|unique values|missing values|describe data|top customers|transaction amount|rows|columns|dataset|dataframe|mean|median|sum"


def classify_user_intent(q):
    """
    Returns one of "governance", "data_analysis", or "general".
    Checked in that priority order: a message matching both GOV and DATA
    keywords is classified as "governance" first.
    """
    q=(q or "").lower()
    if re.search(GOV,q): return "governance"
    if re.search(DATA,q): return "data_analysis"
    return "general"
