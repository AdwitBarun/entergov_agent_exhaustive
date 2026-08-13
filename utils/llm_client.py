"""
utils/llm_client.py
======================
THE ONLY FILE THAT TALKS TO AN LLM PROVIDER. Every other file in this
project treats the LLM purely through this module's functions - so if you
ever want to swap providers again (e.g. to Anthropic or OpenAI directly),
this is the one file you need to touch.

PROVIDER: xAI's Grok API (formerly Google Gemini in earlier versions of
this project - see git history/README "Migration notes" if you kept it).
Grok's API is OpenAI-SDK-compatible: same request/response shape as
OpenAI's Chat Completions API, just a different base_url and API key. That
means we reuse the official `openai` Python package instead of writing raw
HTTP calls; the api_key and base_url are the only things that change.

Docs: https://docs.x.ai/docs/guides/chat-completions
Base URL: https://api.x.ai/v1
Auth: Bearer token via the XAI_API_KEY environment variable / Streamlit secret.

Design principle carried over from the original version of this file:
"Rules detect, LLM explains." Every function here is called AT MOST ONCE
per governance scan or per chat message (see agents/reasoning_agents.py -
generate_scan_narrative() makes exactly one call for the WHOLE scan, not
one call per finding) to control cost and latency.

If no API key is configured, every function below degrades gracefully to a
canned fallback response rather than raising - so the rest of the app keeps
working without Grok configured (see _quiet_fallback()).
"""

from __future__ import annotations

import os
import json
from typing import Generator, Dict, Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# The Grok model to use. Override via the XAI_MODEL environment variable if
# you want a different model without touching code. xAI ships new model
# versions periodically (as of this writing: grok-4.5 / grok-4.6 are current
# flagship models) - check https://docs.x.ai/docs/models for the latest list
# before assuming this default is still current.
DEFAULT_MODEL = os.getenv(
    "XAI_MODEL",
    "grok-4.5"
)


def _get_api_key() -> str | None:
    """
    Reads the xAI (Grok) API key from:

    1. Streamlit secrets (.streamlit/secrets.toml, key: XAI_API_KEY)
    2. Environment variable XAI_API_KEY

    Uses XAI_API_KEY as the single supported
    application configuration variable.
    """

    try:
        import streamlit as st

        key = st.secrets.get(
            "XAI_API_KEY"
        )

        if key:
            return str(key).strip()

    except Exception:
        pass

    key = os.getenv(
        "XAI_API_KEY"
    )

    return key.strip() if key else None


def available() -> bool:
    """Return whether an API key is available."""
    return bool(_get_api_key())


def _get_client():
    """
    Build an OpenAI-SDK client pointed at xAI's OpenAI-compatible endpoint.

    Requires the `openai` package (see requirements.txt). The ONLY
    difference from a normal OpenAI client is the `base_url` and the API
    key coming from XAI_API_KEY instead of OPENAI_API_KEY.
    """
    from openai import OpenAI

    return OpenAI(
        api_key=_get_api_key(),
        base_url="https://api.x.ai/v1",
    )


def _quiet_fallback() -> Generator[str, None, None]:
    """
    User-facing fallback.

    Do not mention provider, SDK, API key, quota, tokens,
    model name, or internal implementation details.
    """

    fallback = (
        "I reviewed the available governance context. "
        "Prioritize critical and high-risk findings first, "
        "inspect the deterministic evidence, and use the review "
        "queue to approve remediation steps before publishing "
        "or applying changes."
    )

    for token in fallback.split(" "):
        yield token + " "


def stream_answer(
    prompt: str,
    model_name: str | None = None
) -> Generator[str, None, None]:
    """
    Streaming response wrapper.

    One call only:

    - Uses the configured model.
    - If it fails, falls back quietly.
    - Does NOT retry across multiple models to avoid extra API calls.
    """

    api_key = _get_api_key()

    if not api_key:
        yield from _quiet_fallback()
        return

    try:
        client = _get_client()

        model = model_name or DEFAULT_MODEL

        # xAI's chat.completions endpoint follows the OpenAI streaming
        # shape: each chunk has choices[0].delta.content (may be None for
        # chunks that carry no new text, e.g. the final chunk).
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            text = getattr(delta, "content", None) if delta else None

            if text:
                yield text
    except Exception as e:
        print("LLM ERROR:", repr(e))
        yield from _quiet_fallback()


def complete_text(
    prompt: str,
    model_name: str | None = None
) -> str:
    """
    Non-streaming helper built from the streaming wrapper.

    Still only makes one API call.
    """

    return "".join(
        list(
            stream_answer(
                prompt=prompt,
                model_name=model_name
            )
        )
    )


def compact_context(
    result: Dict[str, Any] | None,
    df_preview=None
) -> str:
    """
    Compact context for governance reasoning.

    Important:
    Do not send entire datasets.
    Send only summaries, top findings, metadata samples
    and small previews.
    """

    if not result:
        return "No governance scan has been run yet."

    ctx = {
        "overall": result.get("overall"),
        "top_findings": result.get(
            "findings",
            []
        )[:20],

        "policy": result.get("policy"),

        "policy_rules": result.get(
            "policy_rules",
            []
        )[:10],

        "metadata_catalog_sample": result.get(
            "metadata_catalog",
            []
        )[:20],

        "profile_dataset": result.get(
            "profile",
            {}
        ).get("dataset"),

        "profile_columns": result.get(
            "profile",
            {}
        ).get(
            "columns",
            []
        )[:30],
    }

    if df_preview is not None:
        try:
            ctx["data_preview"] = (
                df_preview
                .head(20)
                .to_dict(
                    orient="records"
                )
            )
        except Exception:
            pass

    return json.dumps(
        ctx,
        default=str,
        indent=2
    )[:70000]


def governance_prompt(
    question: str,
    result: Dict[str, Any] | None,
    df_preview=None
) -> str:
    """Build the prompt used for the Copilot chat when intent_router classifies the question as 'governance'."""
    return f"""
You are an enterprise data governance copilot.

Answer from the supplied governance scan context and data preview.

If the information is missing, say what is missing and suggest
the next validation step.

Do not mention API keys, providers, models, quotas, tokens,
SDKs, or implementation details.

SCAN CONTEXT:
{compact_context(result, df_preview)}

USER QUESTION:
{question}

Answer professionally with:

- direct answer
- evidence
- business impact
- recommended next action
"""


def general_prompt(question: str) -> str:
    """Build the prompt used for the Copilot chat when intent_router classifies the question as 'general' (not data/governance related)."""
    return f"""
Answer the user's general question directly and concisely.

Do not reference any uploaded dataset, governance scan,
findings, risks, or metadata unless the user explicitly asks.

Do not mention API keys, providers, models, quotas, tokens,
SDKs, or implementation details.

Question:
{question}
"""


def executive_summary_prompt(
    result: Dict[str, Any]
) -> str:
    """Prompt template for an executive summary. NOTE: not currently called anywhere in the codebase (agents/reasoning_agents.py builds its own inline prompt instead) - kept for reuse/future use."""
    return f"""
Create an executive governance summary from this scan.

Do not change deterministic facts, risk scores, severity,
rule IDs, finding IDs, evidence, affected rows, or affected
percentages.

Do not mention API keys, providers, models, quotas, tokens,
SDKs, or implementation details.

SCAN CONTEXT:
{compact_context(result)}
"""
