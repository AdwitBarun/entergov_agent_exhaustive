"""
core/models.py
================
Central data model definitions for the EnterGov Agent pipeline.

Every agent in `agents/` returns an `AgentResult`, which wraps zero or more
`Finding` objects. These dataclasses are the single shared "contract" between
all agents, the rule engine (`core/rule_engine.py`), the LLM reasoning layer
(`agents/reasoning_agents.py`) and the Streamlit UI (`app.py`, `ui/components.py`).

READ THIS FILE FIRST when exploring the codebase — everything downstream
depends on the shape of `Finding` and `AgentResult`.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
import uuid

# Numeric weight used by core/rule_engine.py to turn a qualitative severity
# label into a quantitative contribution to the 0-100 risk_score.
SEVERITY_WEIGHT = {"info": .1, "low": .25, "medium": .5, "high": .75, "critical": 1.0}

# The set of "route" values that count as requiring a human/approval step
# before the affected data or pipeline can proceed. Used both to build the
# "Human Review Queue" tab in app.py and to decide Finding.requires_human_review.
REVIEW_ROUTES = {"Block Pipeline", "Compliance Review", "Security Review", "Human Review", "Data Owner Review", "Approval Required"}


@dataclass
class Finding:
    """
    A single governance/data-quality issue raised by one agent.

    Instances are created by the deterministic agents (agents/*.py) with the
    "core" fields (agent, rule_id, severity, issue, recommendation, evidence, ...).
    The remaining fields (llm_explanation, possible_root_causes,
    recommended_action_plan, priority_label, review_guidance,
    suggested_owner_type) start empty and are filled in later by
    agents/reasoning_agents.py, either from an LLM response or from the
    deterministic fallback if no LLM key is configured.

    __post_init__ below fills in derived/defaulted fields automatically so
    that every agent doesn't have to repeat that logic.
    """
    agent: str
    rule_id: str
    severity: str
    issue: str
    recommendation: str
    dataset: str = "uploaded_dataset"
    column: Optional[str] = None
    confidence: float = .85
    evidence: Any = field(default_factory=dict)
    business_impact: str = "Operational impact requires review."
    auto_remediable: bool = False
    requires_human_review: Optional[bool] = None
    category: str = "Governance"
    route: str = "Auto-log"
    regulatory_impact: bool = False
    affected_rows: int = 0
    affected_pct: float = 0.0
    finding_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    risk_score: Optional[int] = None
    # --- Fields populated later by the LLM reasoning layer (or its fallback) ---
    llm_explanation: str = ""
    possible_root_causes: List[str] = field(default_factory=list)
    recommended_action_plan: List[str] = field(default_factory=list)
    priority_label: str = ""
    review_guidance: str = ""
    suggested_owner_type: str = ""

    def __post_init__(self):
        """
        Derive fields that shouldn't have to be set manually by every agent:
        - finding_id: a stable, human-readable unique ID (e.g. "DQCOMP-A1B2C3D4").
        - confidence: rounded to 3 decimal places for consistent display.
        - requires_human_review: inferred from severity/route/confidence if
          the caller didn't explicitly set it.
        - title/description: default to the `issue` text if not provided.
        - affected_rows / affected_pct: pulled out of the `evidence` dict
          using whichever key each agent happened to use (different agents
          use different evidence key names, e.g. "null_count" vs "invalid_records").
        """
        if not self.finding_id:
            prefix = (self.rule_id or self.agent).split("-")[0].upper()[:6]
            self.finding_id = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        self.confidence = round(float(self.confidence or 0), 3)
        if self.requires_human_review is None:
            self.requires_human_review = self.severity in {"high", "critical"} or self.route in REVIEW_ROUTES or self.confidence < .85
        self.title = self.title or self.issue
        self.description = self.description or self.issue
        if isinstance(self.evidence, dict):
            self.affected_rows = int(self.evidence.get("affected_records", self.evidence.get("invalid_records", self.evidence.get("null_count", self.affected_rows))) or 0)
            self.affected_pct = float(self.evidence.get("affected_pct", self.evidence.get("null_pct", self.evidence.get("duplicate_pct", self.affected_pct))) or 0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this Finding to a plain dict (used for JSON export and Streamlit dataframes)."""
        return asdict(self)


@dataclass
class AgentResult:
    """
    The return type of every agent's `run(...)` function.

    `score` is a 0-100 health score for that agent's domain (not the same as
    a Finding's risk_score). `metadata` is a free-form dict each agent uses
    to stash extra structured output (e.g. Data Quality Agent's
    `dimension_scores`, Metadata Agent's `catalog`).
    """
    agent: str
    status: str
    score: float
    summary: str
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        """Serialize this AgentResult (and all nested Findings) to a plain dict."""
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d


@dataclass
class PolicyRule:
    """
    A policy rule extracted from either the built-in default policy patterns
    or from free text parsed out of an uploaded policy/issue PDF.
    See core/policy_context.py for how these get created.
    """
    rule_id: str
    title: str
    pattern: str
    severity: str = "medium"
    category: str = "Policy"
    action: str = "Human Review"
    confidence: float = .75


@dataclass
class AuditEvent:
    """A single audit-log entry recorded whenever a Finding is generated (see core/rule_engine.py)."""
    timestamp: str
    agent: str
    action: str
    details: Dict[str, Any]


def now_iso():
    """
    Return the current UTC time as an ISO-8601 string, e.g. '2026-08-13T07:00:00Z'.

    Uses timezone-aware datetime.now(timezone.utc) rather than the deprecated
    datetime.utcnow() (utcnow() is deprecated as of Python 3.12 and emits a
    DeprecationWarning; this project targets 3.12, so we avoid it).
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
