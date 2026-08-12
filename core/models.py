from dataclasses import dataclass, field, asdict
from typing import Optional, Any, Dict, List
from datetime import datetime
import uuid

SEVERITY_WEIGHT = {"info": .1, "low": .25, "medium": .5, "high": .75, "critical": 1.0}
REVIEW_ROUTES = {"Block Pipeline", "Compliance Review", "Security Review", "Human Review", "Data Owner Review", "Approval Required"}

@dataclass
class Finding:
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
    llm_explanation: str = ""
    possible_root_causes: List[str] = field(default_factory=list)
    recommended_action_plan: List[str] = field(default_factory=list)
    priority_label: str = ""
    review_guidance: str = ""
    suggested_owner_type: str = ""

    def __post_init__(self):
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
        return asdict(self)

@dataclass
class AgentResult:
    agent: str
    status: str
    score: float
    summary: str
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self):
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d

@dataclass
class PolicyRule:
    rule_id: str
    title: str
    pattern: str
    severity: str = "medium"
    category: str = "Policy"
    action: str = "Human Review"
    confidence: float = .75

@dataclass
class AuditEvent:
    timestamp: str
    agent: str
    action: str
    details: Dict[str, Any]

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
