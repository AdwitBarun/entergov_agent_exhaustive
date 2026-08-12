# EnterGov Agent

End-to-end Streamlit enterprise governance prototype for structured files and policy documents.

## Design principle

**Rules detect. LLM explains.** Deterministic agents compute findings, scores, routing, evidence and risk. The reasoning layer adds explanations, root causes, action plans, review guidance and conversational assistance.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## API key setup

Create `.streamlit/secrets.toml` locally:

```toml
GOOGLE_API_KEY = "your_key_here"
```

Do not commit real credentials. `.streamlit/secrets.toml.example` is included as a template.

## Included capabilities

- CSV, XLSX, XLS ingestion
- Optional policy / issue PDF extraction
- Optional baseline JSON for schema and drift checks
- Deterministic agents: Data Quality, Compliance, Metadata, Schema, Business Rules, Drift, Remediation
- LLM reasoning enrichment: why it failed, root causes, recommended action plan, priority and review guidance
- Intent-routed Copilot: general, data-analysis and governance modes
- Executive dashboard, evidence drawer, human review queue, metadata catalog, policy context, audit trail and report download

## Notes

The app still works without an API key using deterministic findings and quiet fallback narratives. OCR, IAM/RBAC, database lineage and workflow ticketing are represented as governance workflows, not live enterprise integrations.
