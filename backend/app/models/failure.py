"""
Failure Finding, Root-Cause Cluster, and Judge Calibration Models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FailureFinding(BaseModel):
    finding_id: str = ""
    category: str
    severity: str  # "critical", "high", "medium", "low"
    title: str = ""
    description: str = ""
    source: str = "DETERMINISTIC_ASSERTION_ENGINE"  # "DETERMINISTIC_RULE_ENGINE", "SEMANTIC_LLM_JUDGE", "SECURITY_GATEWAY_POLICY"
    explanation: str = ""
    evidence: str = ""

    expected: Optional[str] = None
    observed: Optional[str] = None
    remediation: Optional[str] = None

    execution_step_id: Optional[str] = None
    event_ids: List[str] = Field(default_factory=list)
    evidence_type: str = "tool_call"  # "tool_call", "security_event", "state_change", "output_text"
    source_location: Optional[str] = None

    attempted_action: bool = False
    policy_blocked: bool = False
    actual_side_effect: bool = False

    confidence: float = 1.0


class RunVerdict(BaseModel):
    id: Optional[str] = None
    evaluation_run_id: Optional[str] = None
    trace_id: str
    execution_session_id: Optional[str] = None
    scenario_id: str
    scenario_version_id: Optional[str] = None

    status: str = "PASS"  # "PASS", "FAIL", "BLOCKED", "INCONCLUSIVE", "ERROR", "NOT_APPLICABLE"
    passed: bool = True
    expected_behavior_met: bool = True

    deterministic_score: float = 100.0
    semantic_score: Optional[float] = None
    final_score: float = 100.0
    semantic_judge_status: str = "AVAILABLE"
    semantic_judge_reason: Optional[str] = None

    findings: List[FailureFinding] = Field(default_factory=list)
    evaluation_method: str = "DETERMINISTIC_AND_SEMANTIC"

    counterfactual_trace_id: Optional[str] = None
    counterfactual_passed: Optional[bool] = None
    attack_causation_proven: bool = False


class FailureCluster(BaseModel):
    id: str
    evaluation_id: str = ""
    label: str
    title: str = ""
    category: str
    root_cause_pattern: str = ""

    member_verdict_ids: List[str] = Field(default_factory=list)
    verdict_ids: List[str] = Field(default_factory=list)
    affected_scenarios: List[str] = Field(default_factory=list)
    representative_evidence: str = ""
    count: int = 0
    occurrences: int = 0

    severity: str = "high"
    recommended_fix: str = ""
    remediation_suggestion: str = ""

    failure_surface: Optional[str] = None
    workflow_node: Optional[str] = None
    dependency: Optional[str] = None


class CalibrationSample(BaseModel):
    id: str
    scenario_title: str
    trace_snippet: str
    gold_label_passed: bool
    gold_failure_category: str
    judge_label_passed: bool
    judge_failure_category: str
    agreed: bool


class CalibrationReport(BaseModel):
    total_samples: int
    agreed_samples: int
    agreement_rate: float
    false_positives: int
    false_negatives: int
    samples: List[CalibrationSample] = Field(default_factory=list)
