"""
core/orchestrator.py
======================
THE PIPELINE ENTRY POINT. This is the file to read after core/models.py to
understand the end-to-end flow of a governance scan.

IMPORTANT HONESTY NOTE: despite the "agents" naming throughout this project,
run_governance_pipeline() below is a plain, linear Python function that
calls each agent's run() in a fixed, hardcoded sequence and concatenates
their outputs. There is no LangGraph StateGraph, no conditional routing
between agents, no shared mutable state object passed through nodes, and no
inter-agent messaging. If you came here expecting a LangGraph graph
definition (nodes/edges/state schema), it does not exist in this codebase.
See ARCHITECTURE.md in the project root for a full breakdown of what this
project actually is vs. what "multi-agent" might imply, and for suggestions
on how to port this to a real LangGraph StateGraph if you want one.

Pipeline steps, in order:
  1. profile_dataframe()          - core/profiling.py:      build column/dataset profile
  2. parse_policy_text()          - core/policy_context.py: extract policy rules from PDF text (if any)
  3. Run 6 deterministic agents in this fixed order:
       data_quality_agent, compliance_agent, metadata_agent,
       schema_agent, business_rule_agent, drift_agent
  4. remediation_agent.run(...)   - runs LAST, fed the combined findings of
                                     steps above (so remediation suggestions
                                     can reference already-computed findings).
  5. aggregate_results()          - core/rule_engine.py: merge all AgentResults,
                                     compute risk scores, routes, audit trail.
  6. enrich_governance_result()   - agents/reasoning_agents.py: ONE LLM call
                                     (Grok, via utils/llm_client.py) to add
                                     human-readable explanations, root causes
                                     and action plans on top of the
                                     deterministic findings above. Falls back
                                     to canned text if no API key is set.

Called from: app.py, when the user clicks "Run Governance Scan".
"""
import json
from core.profiling import profile_dataframe
from core.policy_context import parse_policy_text, policy_summary
from core.rule_engine import aggregate_results
from agents import data_quality_agent, compliance_agent, metadata_agent, schema_agent, business_rule_agent, drift_agent, remediation_agent
from agents.reasoning_agents import enrich_governance_result


def run_governance_pipeline(df, file_meta, policy_text="", pdf_text_profile=None, baseline_schema=None, baseline_stats=None, enrich=True):
    """
    Run the full governance scan on an uploaded DataFrame and return the
    aggregated result dict consumed by app.py's Streamlit tabs.

    Args:
        df: the uploaded/parsed pandas DataFrame (see core/ingestion.py).
        file_meta: metadata dict from core.ingestion.load_tabular().
        policy_text: raw text extracted from an optional policy PDF.
        pdf_text_profile: dict from core.ingestion.extract_pdf_text() (used
            by the Compliance Agent to flag OCR-required documents).
        baseline_schema / baseline_stats: optional dicts from a previously
            saved baseline JSON, used by the Schema Agent (drift in columns)
            and Drift Agent (drift in row volume/statistics).
        enrich: if True (default), makes the single LLM call to add
            human-readable narratives. Set False to skip the LLM entirely
            and get pure deterministic output (e.g. for testing).

    Returns:
        The aggregated result dict, with keys including "findings",
        "overall", "agent_cards", "audit", "profile", "policy",
        "metadata_catalog", "agent_results", and (if enrich=True)
        "executive_narrative", "root_cause_summary", "recommendation_plan".
    """
    profile=profile_dataframe(df, file_meta.get("file_name","uploaded_dataset"), file_meta.get("file_type","uploaded_file")); rules=parse_policy_text(policy_text) if policy_text else []

    # Run all 6 primary agents. Order does not currently affect their output
    # (each agent only reads `df`/`profile`/`rules`, none read each other's
    # results at this stage) but IS the order they render in the UI's
    # "Agent Health" cards.
    results=[data_quality_agent.run(df,profile), compliance_agent.run(profile,rules,pdf_text_profile), metadata_agent.run(profile), schema_agent.run(profile,baseline_schema), business_rule_agent.run(df,profile,rules), drift_agent.run(profile,baseline_stats)]

    # Remediation Agent runs last because it needs the combined findings
    # from every other agent to suggest fixes.
    base=[]
    for r in results: base.extend(r.findings)
    results.append(remediation_agent.run(base))

    aggregated=aggregate_results(results, profile.get("dataset",{}).get("name","uploaded_dataset"))
    aggregated.update({"profile":profile,"file_meta":file_meta,"policy":policy_summary(rules),"policy_rules":[r.__dict__ for r in rules],"agent_results":[r.to_dict() for r in results]})

    # Pull the Metadata Agent's catalog out separately since app.py's
    # "Policy & Metadata" tab reads it directly (rather than digging through
    # agent_results each time).
    md=[r for r in aggregated["agent_results"] if r.get("agent")=="Metadata Agent"]
    aggregated["metadata_catalog"]=md[0].get("metadata",{}).get("catalog",[]) if md else []

    # Step 6: single LLM call to enrich everything above with explanations.
    # Falls back to deterministic canned text if no LLM key is configured
    # or the call/parse fails - see agents/reasoning_agents.py.
    return enrich_governance_result(aggregated, df) if enrich else aggregated


def to_json_report(result):
    """Serialize the aggregated result dict to a pretty-printed JSON string, for the 'Download Governance Report' button."""
    return json.dumps(result, indent=2, default=str)
