# EnterGov Agent

A Streamlit prototype for enterprise data governance: upload a structured
file (CSV/XLSX), an optional policy/issue PDF, and an optional baseline
JSON, and get back deterministic data-quality/compliance/schema/drift
findings, risk scores, review routing, an audit trail, and an LLM-generated
narrative explaining what was found and why.

**New to this codebase?** Start with [`ARCHITECTURE.md`](./ARCHITECTURE.md)
for the exact file-reading order, a flow diagram, and an honest list of what
this project does and doesn't do (it is **not** built on LangGraph — see
that doc for details).

## Design principle

**Rules detect. LLM explains.** Six deterministic agents compute findings,
scores, routing, and evidence with plain Python/pandas — no LLM involved.
A separate reasoning layer then makes **one** LLM call per scan to add
explanations, root causes, action plans, and review guidance on top of
those deterministic results. The LLM is explicitly instructed not to alter
any deterministic field (severity, risk score, route, evidence).

## LLM provider: Grok (xAI)

This project uses **xAI's Grok API** (OpenAI-SDK-compatible) via the
`openai` Python package pointed at `https://api.x.ai/v1`. All provider code
lives in `utils/llm_client.py` — that is the only file that knows about the
provider; everything else calls its functions.

The app works without an API key: LLM calls fall back to canned
explanatory text instead of crashing.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

## API key setup

1. Get an xAI API key at https://console.x.ai/
2. Copy the template and fill in your key:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
3. Edit `.streamlit/secrets.toml`:
   ```toml
   XAI_API_KEY = "your_key_here"
   ```

`.streamlit/secrets.toml` is git-ignored — never commit real credentials.
Alternatively, set the `XAI_API_KEY` environment variable (or put it in a
local `.env` file, also git-ignored) instead of using Streamlit secrets;
`utils/llm_client.py` checks both.

To use a specific Grok model, set `XAI_MODEL` the same way (defaults to
`grok-4.5` — check https://docs.x.ai/docs/models for the current list, as
xAI ships new model versions periodically).

## Try it with the included sample data

`sample_data/sample_customers.csv` and `sample_data/baseline.json` are
included so you can run a scan immediately without your own data — upload
the CSV as "Structured data" and the JSON as the optional baseline to see
schema/drift checks in action.

## Included capabilities

- CSV, XLSX, XLS ingestion
- Optional policy / issue PDF extraction
- Optional baseline JSON for schema and drift checks
- Deterministic agents: Data Quality, Compliance, Metadata, Schema, Business Rules, Drift, Remediation
- LLM reasoning enrichment: why it failed, root causes, recommended action plan, priority and review guidance
- Intent-routed Copilot chat: general, data-analysis and governance modes
- Executive dashboard, evidence drawer, human review queue, metadata catalog, policy context, audit trail and report download

## Limitations

The app works without an API key using deterministic findings and a quiet
fallback narrative. OCR, IAM/RBAC, database lineage and workflow ticketing
are represented as governance *workflow concepts* in the UI, not live
enterprise integrations. See [`ARCHITECTURE.md`](./ARCHITECTURE.md#known-gaps-things-that-look-implemented-but-arent-fully)
for a fuller list of gaps, including two DQ dimensions that are currently
hardcoded rather than computed, and the absence of automated tests.

## Deployment notes

- **Streamlit Community Cloud** reads `requirements.txt` automatically —
  point it at `app.py` and set `XAI_API_KEY` in the app's Secrets panel
  (paste the same TOML shown in `.streamlit/secrets.toml.example`).
- **Anywhere else (Render, Fly.io, a VM, Docker):** run
  `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` and
  set `XAI_API_KEY` as an environment variable — no `secrets.toml` needed
  in that case since `utils/llm_client.py` also checks `os.environ`.
- There is no `Dockerfile` in this repo. If you need one, `python:3.12-slim`
  base image + `pip install -r requirements.txt` + the run command above is
  sufficient; it isn't included here because it wasn't part of the original
  project and templates vary a lot by hosting target.
