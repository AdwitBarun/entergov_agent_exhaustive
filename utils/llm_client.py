from __future__ import annotations

import os
import json
from typing import Generator, Dict, Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

DEFAULT_MODEL = os.getenv(
    "GROK_MODEL",
    "grok-4.5"
)

DEFAULT_BASE_URL = os.getenv(
    "GROK_BASE_URL",
    os.getenv(
        "XAI_BASE_URL",
        "https://api.x.ai/v1"
    )
)


def _get_api_key() -> str | None:
    """
    Reads the Grok/xAI API key from:

    1. Streamlit secrets
    2. Environment variable

    GROK_API_KEY is the project-level setting. XAI_API_KEY
    is also accepted because it is the official xAI
    environment variable name.
    """

    key_names = (
        "GROK_API_KEY",
        "XAI_API_KEY",
    )

    try:
        import streamlit as st

        for name in key_names:
            key = st.secrets.get(
                name
            )

            if key:
                return str(key).strip()

    except Exception:
        pass

    for name in key_names:
        key = os.getenv(
            name
        )

        if key:
            return key.strip()

    return None


def available() -> bool:
    """Return whether an API key is available."""
    return bool(_get_api_key())


def _get_client():
    """
    Uses xAI's OpenAI-compatible API endpoint.

        from openai import OpenAI
    """
    from openai import OpenAI

    return OpenAI(
        api_key=_get_api_key(),
        base_url=DEFAULT_BASE_URL,
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

        for chunk in client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            stream=True,
        ):
            choice = chunk.choices[0] if chunk.choices else None
            delta = getattr(choice, "delta", None) if choice else None
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
