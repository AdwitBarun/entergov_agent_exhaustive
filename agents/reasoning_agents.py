from __future__ import annotations

import json
from typing import Dict, Any, List

from utils.llm_client import complete_text, compact_context


OWNER_MAP = {
    "CMP": "Compliance",
    "META": "Metadata Steward",
    "SCH": "Data Engineering",
    "DQ": "Data Engineering",
    "DRIFT": "Data Engineering",
    "BUS": "Data Owner",
    "REM": "Data Owner",
}


def priority_label(severity: str) -> str:
    return {
        "critical": "P1",
        "high": "P2",
        "medium": "P3",
        "low": "P4",
        "info": "P4",
    }.get(severity, "P3")


def fallback_for_finding(
    finding: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic fallback enrichment.
    Used when LLM is unavailable or response parsing fails.
    """

    rule_id = finding.get("rule_id") or ""
    agent_prefix = (
        rule_id.split("-")[0]
        if rule_id
        else "GEN"
    )

    severity = finding.get(
        "severity",
        "medium"
    )

    return {
        "finding_id": finding.get("finding_id"),

        "llm_explanation": (
            "This finding was raised because deterministic "
            f"check {finding.get('rule_id')} flagged: "
            f"{finding.get('issue')}. "
            "The evidence section contains the exact signals "
            "used for this decision."
        ),

        "possible_root_causes": [
            "Source-system data entry issue",
            "ETL mapping or transformation issue",
            "Late, partial, or duplicate upstream feed",
            "Missing governance metadata or policy mapping",
        ],

        "recommended_action_plan": [
            finding.get(
                "recommendation",
                "Review with the data owner."
            ),
            "Validate source records and ingestion logs.",
            "Check field mapping, data contract, and lineage.",
            "Assign the finding to the suggested owner.",
            "Rerun the governance scan after remediation.",
        ],

        "priority_label": priority_label(
            severity
        ),

        "review_guidance": (
            "Human review is recommended before "
            "publishing or applying remediation."
            if finding.get("requires_human_review")
            else
            "This can be logged or auto-fixed if "
            "approved by the data owner."
        ),

        "suggested_owner_type": OWNER_MAP.get(
            agent_prefix,
            "Data Owner"
        ),
    }


def fallback_bulk_result(
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Full deterministic fallback for the entire scan.

    This avoids extra API calls and keeps the app usable
    without a key.
    """

    findings = result.get(
        "findings",
        []
    )

    enriched_findings = []

    for finding in findings:
        enriched = finding.copy()

        enriched.update(
            fallback_for_finding(
                finding
            )
        )

        enriched_findings.append(
            enriched
        )

    overall = result.get(
        "overall",
        {}
    )

    executive_narrative = (
        f"Aggregate risk is "
        f"{overall.get('aggregate_risk', 0)} "
        f"with "
        f"{overall.get('review_queue', 0)} "
        f"items requiring review. "
        "Prioritize critical and high-severity findings "
        "routed to Block Pipeline, Compliance Review, "
        "Human Review, or Approval Required."
    )

    root_cause_summary = (
        "Likely root causes include source-system data gaps, "
        "ETL mapping issues, schema or data contract drift, "
        "missing metadata ownership, and incomplete "
        "policy-to-rule mapping."
    )

    recommendation_plan = (
        "1. Resolve P1 and P2 findings first.\n"
        "2. Validate deterministic evidence for affected "
        "columns and records.\n"
        "3. Assign findings to the suggested owner type.\n"
        "4. Quarantine or block critical issues before "
        "downstream use.\n"
        "5. Rerun the scan after remediation."
    )

    return {
        "executive_narrative": executive_narrative,
        "root_cause_summary": root_cause_summary,
        "recommendation_plan": recommendation_plan,
        "supervisor_summary": executive_narrative,
        "findings": enriched_findings,
    }


def generate_scan_narrative(
    result: Dict[str, Any],
    df=None
) -> Dict[str, Any] | None:
    """
    Single-call LLM enrichment for the entire scan.

    This replaces the old per-finding LLM call pattern.

    Old:
        N findings = N API calls

        - executive summary call
        - root cause call
        - recommendation call

    New:
        Entire scan = 1 API call
    """

    context = compact_context(
        result,
        df
    )

    findings = result.get(
        "findings",
        []
    )

    prompt = f"""
You are an enterprise data governance reasoning layer.

The deterministic agents have already computed all findings,
risk scores, severity, affected rows, affected percentages,
evidence, routes, rule IDs, and finding IDs.

Your task:
Add explanations and recommendations only.

You MUST NOT change:

- finding_id
- rule_id
- severity
- confidence
- risk_score
- route
- affected_rows
- affected_pct
- deterministic evidence
- dataset
- column
- issue

Return STRICT JSON only.

Required JSON structure:

{{
    "executive_narrative": "...",
    "root_cause_summary": "...",
    "recommendation_plan": "...",
    "supervisor_summary": "...",
    "findings": [
        {{
            "finding_id": "same finding_id from input",
            "llm_explanation": "...",
            "possible_root_causes": [
                "...",
                "..."
            ],
            "recommended_action_plan": [
                "...",
                "..."
            ],
            "priority_label": "P1/P2/P3/P4",
            "review_guidance": "...",
            "suggested_owner_type":
                "Data Owner / Data Engineering / "
                "Compliance / Security / Metadata Steward"
        }}
    ]
}}

Priority mapping:

- critical = P1
- high = P2
- medium = P3
- low/info = P4

Use concise, business-friendly explanations.

Be specific to the evidence wherever possible.

Do not mention API keys, providers, models, quotas,
tokens, SDKs, or implementation details.

SCAN CONTEXT:
{context}

FINDINGS TO ENRICH:
{json.dumps(findings, default=str)}
"""

    try:
        response = complete_text(
            prompt
        )

        if not response:
            return None

        response = response.strip()

        # Handle accidental markdown JSON fences
        if response.startswith("```json"):
            response = response[
                len("```json"):
            ].strip()

        if response.endswith("```"):
            response = response[
                :-len("```")
            ].strip()

        parsed = json.loads(
            response
        )

        if not isinstance(
            parsed,
            dict
        ):
            return None

        return parsed

    except Exception:
        return None
    
def merge_bulk_narrative(
    result: Dict[str, Any],
    bulk: Dict[str, Any] | None
) -> Dict[str, Any]:
    """
    Merge the single LLM response back into the deterministic
    governance result.

    IMPORTANT:
    Deterministic fields always remain authoritative.

    The LLM is only allowed to enrich findings with:
        - explanations
        - root causes
        - action plans
        - priority labels
        - review guidance
        - suggested owner

    If the LLM response is missing or invalid, use the
    deterministic fallback without making another API call.
    """

    # ---------------------------------------------------------
    # 1. If LLM failed, use deterministic fallback
    # ---------------------------------------------------------

    if not bulk or not isinstance(bulk, dict):
        fallback = fallback_bulk_result(result)

        merged_result = result.copy()

        merged_result.update({
            "executive_narrative": fallback.get(
                "executive_narrative",
                ""
            ),
            "root_cause_summary": fallback.get(
                "root_cause_summary",
                ""
            ),
            "recommendation_plan": fallback.get(
                "recommendation_plan",
                ""
            ),
            "supervisor_summary": fallback.get(
                "supervisor_summary",
                ""
            ),
        })

        merged_result["findings"] = fallback.get(
            "findings",
            result.get("findings", [])
        )

        merged_result["llm_enriched"] = False
        merged_result["llm_enrichment_status"] = "fallback"

        return merged_result

    # ---------------------------------------------------------
    # 2. Build lookup table for LLM enrichments
    # ---------------------------------------------------------

    llm_findings = bulk.get(
        "findings",
        []
    )

    if not isinstance(llm_findings, list):
        llm_findings = []

    enrichment_map = {}

    for item in llm_findings:

        if not isinstance(item, dict):
            continue

        finding_id = item.get(
            "finding_id"
        )

        if finding_id:
            enrichment_map[str(finding_id)] = item

    # ---------------------------------------------------------
    # 3. Merge enrichment into deterministic findings
    # ---------------------------------------------------------

    deterministic_findings = result.get(
        "findings",
        []
    )

    merged_findings = []

    allowed_llm_fields = {
        "llm_explanation",
        "possible_root_causes",
        "recommended_action_plan",
        "priority_label",
        "review_guidance",
        "suggested_owner_type",
    }

    for finding in deterministic_findings:

        # Start with deterministic finding.
        merged = finding.copy()

        finding_id = finding.get(
            "finding_id"
        )

        llm_data = enrichment_map.get(
            str(finding_id)
        )

        if llm_data:

            # Only copy explicitly allowed enrichment fields.
            for field in allowed_llm_fields:

                if field in llm_data:
                    merged[field] = llm_data[field]

        else:

            # If the LLM forgot to return a finding,
            # enrich that finding deterministically.
            fallback = fallback_for_finding(
                finding
            )

            for field in allowed_llm_fields:

                if field in fallback:
                    merged[field] = fallback[field]

        merged_findings.append(
            merged
        )

    # ---------------------------------------------------------
    # 4. Preserve the original deterministic result
    # ---------------------------------------------------------

    merged_result = result.copy()

    # Only these are generated by the LLM.
    merged_result["executive_narrative"] = bulk.get(
        "executive_narrative",
        ""
    )

    merged_result["root_cause_summary"] = bulk.get(
        "root_cause_summary",
        ""
    )

    merged_result["recommendation_plan"] = bulk.get(
        "recommendation_plan",
        ""
    )

    merged_result["supervisor_summary"] = bulk.get(
        "supervisor_summary",
        ""
    )

    merged_result["findings"] = merged_findings

    merged_result["llm_enriched"] = True
    merged_result["llm_enrichment_status"] = "success"

    return merged_result

def enrich_governance_result(
    result,
    df=None
):
    """
    Main entry point used by orchestrator.py.

    Makes ONE LLM call for the whole scan and
    merges the generated narratives back into
    deterministic findings.
    """

    bulk = generate_scan_narrative(
        result,
        df
    )

    return merge_bulk_narrative(
        result,
        bulk
    )