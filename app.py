"""
app.py
========
Streamlit UI entry point - this is the file you run:  streamlit run app.py

If you are new to this codebase, the recommended reading order is:
  1. README.md              - what this project does, how to run it
  2. ARCHITECTURE.md         - the real (non-LangGraph) pipeline flow, file map
  3. core/models.py          - the shared Finding/AgentResult data contract
  4. core/orchestrator.py    - the pipeline entry point (run_governance_pipeline)
  5. agents/*.py             - the six deterministic agents + remediation agent
  6. agents/reasoning_agents.py - the single LLM enrichment call
  7. utils/llm_client.py     - the Grok (xAI) API wrapper
  8. app.py (this file)      - ties ingestion + orchestrator + UI together

This file itself just wires Streamlit widgets to the functions defined
elsewhere; there is intentionally very little logic here.

Layout: a sidebar for file uploads + "Run Governance Scan" button, and six
tabs: Executive Dashboard, Agent Findings, Human Review Queue,
Policy & Metadata, Data Explorer, AI Governance Copilot (chat).
"""
from __future__ import annotations
import json, pandas as pd, streamlit as st
from core.ingestion import load_tabular, extract_pdf_text
from core.orchestrator import run_governance_pipeline, to_json_report
from ui.components import findings_table, evidence_drawer, agent_cards
from utils.intent_router import classify_user_intent
from utils.data_query import answer_simple_data_question, dataframe_context
from utils.llm_client import stream_answer, governance_prompt, general_prompt

# --- Page config & custom CSS for the hero banner / metric cards ---
st.set_page_config(page_title="EnterGov Agent", layout="wide", page_icon="🛡️")
st.markdown("""<style>.block-container{padding-top:1.2rem}.card{border:1px solid #E5E7EB;border-radius:18px;padding:18px;background:white;box-shadow:0 8px 24px rgba(15,23,42,.06);min-height:175px;margin-bottom:14px}.card-title{font-weight:800;font-size:16px;color:#0F172A}.muted{color:#64748B;font-size:13px}.score{font-size:34px;font-weight:900;color:#2563EB;margin:8px 0}.hero{padding:18px 22px;border-radius:22px;background:linear-gradient(135deg,#0F172A,#1D4ED8);color:white;margin-bottom:18px}.hero h1{margin:0;font-size:30px}.hero p{margin:6px 0 0;color:#DBEAFE}</style>""", unsafe_allow_html=True)
st.markdown("<div class='hero'><h1>EnterGov Agent</h1><p>Enterprise data quality, governance, compliance, policy context, risk routing, root cause narratives and interactive data Q&A.</p></div>", unsafe_allow_html=True)

# --- Sidebar: file uploads and scan trigger ---
with st.sidebar:
    st.header("Inputs")
    data_file=st.file_uploader("Structured data", type=["csv","xlsx","xls"])
    policy_pdf=st.file_uploader("Company issue / policy document", type=["pdf"])
    baseline_json=st.file_uploader("Optional baseline/data contract JSON", type=["json"])
    scan=st.button("Run Governance Scan", type="primary", use_container_width=True)
    st.caption("Upload a baseline JSON to enable stronger schema and drift checks.")

# --- Session state: scan result, dataframe, and chat history persist across reruns within a browser session ---
if "result" not in st.session_state: st.session_state.result=None
if "df" not in st.session_state: st.session_state.df=None
if "messages" not in st.session_state: st.session_state.messages=[]

# --- Handle "Run Governance Scan" click: ingest files, run the full pipeline (core/orchestrator.py) ---
if scan:
    if not data_file: st.error("Please upload a CSV or Excel file.")
    else:
        try:
            df,meta=load_tabular(data_file); policy_text=""; pdf_profile=None
            if policy_pdf: pdf_profile=extract_pdf_text(policy_pdf); policy_text=pdf_profile.get("text","")
            schema_base=stats_base=None
            if baseline_json:
                b=json.load(baseline_json); schema_base=b.get("schema_baseline") or b; stats_base=b.get("stats_baseline") or b
            with st.spinner("Running governance scan and preparing explanations..."):
                st.session_state.result=run_governance_pipeline(df,meta,policy_text,pdf_profile,schema_base,stats_base,enrich=True); st.session_state.df=df
            st.success("Governance scan completed.")
        except Exception as e: st.exception(e)

result=st.session_state.result; df=st.session_state.df
tabs=st.tabs(["Executive Dashboard","Agent Findings","Human Review Queue","Policy & Metadata","Data Explorer","AI Governance Copilot"])

# --- Tab 1: Executive Dashboard - top-line metrics, LLM narratives, agent health cards, charts ---
with tabs[0]:
    if not result: st.info("Upload data and run a governance scan to start.")
    else:
        o=result["overall"]; m=st.columns(6)
        for col,label,key in zip(m,["Aggregate Risk","Max Risk","Findings","Review Queue","Low Confidence","Policy Rules"],["aggregate_risk","max_risk","total_findings","review_queue","low_confidence",None]): col.metric(label, result["policy"]["total_policy_rules"] if key is None else o[key])
        st.subheader("Supervisor Summary"); st.info(result.get("supervisor_summary",""))
        st.subheader("Executive Narrative"); st.write(result.get("executive_narrative",""))
        c1,c2=st.columns(2)
        with c1: st.subheader("Top Root Causes"); st.write(result.get("root_cause_summary",""))
        with c2: st.subheader("Recommended Plan"); st.write(result.get("recommendation_plan",""))
        st.subheader("Agent Health"); agent_cards(result["agent_cards"])
        c1,c2=st.columns(2)
        with c1: st.subheader("Severity Distribution"); st.bar_chart(pd.DataFrame([{"severity":k,"count":v} for k,v in o["severity_counts"].items()]).set_index("severity"))
        with c2: st.subheader("Routing Distribution"); st.bar_chart(pd.DataFrame([{"route":k,"count":v} for k,v in o["routes"].items() if v>0]).set_index("route"))

# --- Tab 2: Agent Findings - full findings table + evidence drawer + JSON report download ---
with tabs[1]:
    if not result: st.info("Run a scan to view findings.")
    else: findings_table(result["findings"]); st.subheader("Evidence & Explanation Drawer"); evidence_drawer(result["findings"]); st.download_button("Download Governance Report", to_json_report(result), "entergov_report.json", "application/json")

# --- Tab 3: Human Review Queue - findings routed to any of the "needs a human" routes, plus the full audit trail ---
with tabs[2]:
    if not result: st.info("Run a scan to populate the queue.")
    else:
        q=[f for f in result["findings"] if f.get("route") in {"Block Pipeline","Compliance Review","Security Review","Human Review","Data Owner Review","Approval Required"}]
        st.subheader(f"Review Queue: {len(q)} items"); evidence_drawer(q); st.subheader("Audit Trail"); st.dataframe(pd.DataFrame(result["audit"]), use_container_width=True, hide_index=True)

# --- Tab 4: Policy & Metadata - extracted policy rules table + metadata catalog + DQ dimension scores ---
with tabs[3]:
    if not result: st.info("Run a scan to view policy and metadata.")
    else:
        c1,c2,c3=st.columns(3); c1.metric("Rules Detected",result["policy"]["total_policy_rules"]); c2.metric("High/Critical Rules",result["policy"]["critical_or_high"]); c3.metric("Metadata Columns",len(result.get("metadata_catalog",[])))
        st.subheader("Policy Rules"); st.dataframe(pd.DataFrame(result["policy_rules"]), use_container_width=True, hide_index=True)
        st.subheader("Metadata Catalog"); st.dataframe(pd.DataFrame(result.get("metadata_catalog",[])), use_container_width=True, hide_index=True)
        dq=[r for r in result.get("agent_results",[]) if r.get("agent")=="Data Quality Agent"]
        if dq: st.subheader("Quality Dimension Scores"); st.bar_chart(pd.DataFrame([{"dimension":k,"score":v} for k,v in dq[0].get("metadata",{}).get("dimension_scores",{}).items()]).set_index("dimension"))

# --- Tab 5: Data Explorer - raw data preview + per-column profile summary ---
with tabs[4]:
    if df is None: st.info("Run a scan to explore the uploaded data.")
    else: st.subheader("Data Preview"); st.dataframe(df.head(200), use_container_width=True, hide_index=True); st.subheader("Column Summary"); st.dataframe(pd.DataFrame(result.get("profile",{}).get("columns",[])), use_container_width=True, hide_index=True)

# --- Tab 6: AI Governance Copilot - free-form chat, routed by utils/intent_router.py to one of three prompt strategies ---
with tabs[5]:
    st.subheader("AI Governance Copilot"); st.caption("Ask general questions, data questions, or governance questions. The assistant routes each question appropriately.")
    for role,msg in st.session_state.messages:
        with st.chat_message(role): st.write(msg)
    prompt=st.chat_input("Ask about this data, governance scan, or anything else...")
    if prompt:
        st.session_state.messages.append(("user",prompt))
        with st.chat_message("user"): st.write(prompt)
        intent=classify_user_intent(prompt)
        if intent=="data_analysis":
            # Try a local, LLM-free pandas answer first (utils/data_query.py);
            # only fall back to sending a dataframe summary to the LLM if that returns None.
            local=answer_simple_data_question(prompt,df)
            question=f"Local computed answer: {local}\nExplain this clearly." if local else f"Use this dataframe summary and sample to answer:\n{dataframe_context(df)}\nQuestion: {prompt}"
        elif intent=="governance": question=governance_prompt(prompt,result,df)
        else: question=general_prompt(prompt)
        with st.chat_message("assistant"):
            parts=[]
            def gen():
                # Wraps utils.llm_client.stream_answer() so Streamlit's
                # write_stream can render tokens as they arrive while we
                # also accumulate them into `parts` for chat history.
                for chunk in stream_answer(question): parts.append(chunk); yield chunk
            st.write_stream(gen)
        st.session_state.messages.append(("assistant","".join(parts)))
