import streamlit as st, pandas as pd
def findings_table(findings):
    if not findings: st.success("No findings detected."); return
    df=pd.DataFrame(findings); cols=["risk_score","priority_label","severity","finding_id","rule_id","agent","dataset","column","issue","confidence","route","suggested_owner_type"]
    st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
def evidence_drawer(findings, limit=80):
    for i,f in enumerate(findings[:limit],1):
        with st.expander(f"{i}. [{str(f.get('priority_label') or f.get('severity')).upper()}] {f.get('issue')} | Risk {f.get('risk_score')}"):
            c1,c2,c3,c4=st.columns(4); c1.metric("Finding ID",f.get("finding_id","-")); c2.metric("Rule",f.get("rule_id","-")); c3.metric("Confidence",f"{float(f.get('confidence',0))*100:.0f}%"); c4.metric("Route",f.get("route","-"))
            st.markdown("**Why it failed**"); st.write(f.get("llm_explanation") or f.get("description"))
            st.markdown("**Possible root causes**"); st.write("\n".join([f"- {x}" for x in f.get("possible_root_causes",[])]) or "-")
            st.markdown("**Deterministic evidence**"); st.json(f.get("evidence",{}))
            st.markdown("**Business impact**"); st.write(f.get("business_impact"))
            st.markdown("**Recommended action plan**"); st.write("\n".join([f"- {x}" for x in f.get("recommended_action_plan",[])]) or f.get("recommendation"))
            st.markdown("**Review guidance**"); st.write(f.get("review_guidance") or "-")
def agent_cards(cards):
    cols=st.columns(3)
    for i,c in enumerate(cards):
        with cols[i%3]: st.markdown(f"<div class='card'><div class='card-title'>{c['agent']}</div><div class='muted'>{c['status']}</div><div class='score'>{c['score']}</div><div class='muted'>{c['summary']}</div></div>", unsafe_allow_html=True)
