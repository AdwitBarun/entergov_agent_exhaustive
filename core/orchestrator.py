import json
from core.profiling import profile_dataframe
from core.policy_context import parse_policy_text, policy_summary
from core.rule_engine import aggregate_results
from agents import data_quality_agent, compliance_agent, metadata_agent, schema_agent, business_rule_agent, drift_agent, remediation_agent
from agents.reasoning_agents import enrich_governance_result
def run_governance_pipeline(df, file_meta, policy_text="", pdf_text_profile=None, baseline_schema=None, baseline_stats=None, enrich=True):
    profile=profile_dataframe(df, file_meta.get("file_name","uploaded_dataset"), file_meta.get("file_type","uploaded_file")); rules=parse_policy_text(policy_text) if policy_text else []
    results=[data_quality_agent.run(df,profile), compliance_agent.run(profile,rules,pdf_text_profile), metadata_agent.run(profile), schema_agent.run(profile,baseline_schema), business_rule_agent.run(df,profile,rules), drift_agent.run(profile,baseline_stats)]
    base=[]
    for r in results: base.extend(r.findings)
    results.append(remediation_agent.run(base))
    aggregated=aggregate_results(results, profile.get("dataset",{}).get("name","uploaded_dataset"))
    aggregated.update({"profile":profile,"file_meta":file_meta,"policy":policy_summary(rules),"policy_rules":[r.__dict__ for r in rules],"agent_results":[r.to_dict() for r in results]})
    md=[r for r in aggregated["agent_results"] if r.get("agent")=="Metadata Agent"]
    aggregated["metadata_catalog"]=md[0].get("metadata",{}).get("catalog",[]) if md else []
    return enrich_governance_result(aggregated, df) if enrich else aggregated
def to_json_report(result): return json.dumps(result, indent=2, default=str)
