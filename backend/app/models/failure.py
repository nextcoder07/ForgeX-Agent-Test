"""
Failure Finding, Root-Cause Cluster, and Judge Calibration Models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FailureFinding(BaseModel):
    category: str
    severity: str  # "critical", "high", "medium", "low"
    source: str  # "RULE_ENGINE", "LLM_JUDGE", "SANDBOX_SECURITY", "STATE_DIFF"
    explanation: str
    evidence: str
    confidence: float = 1.0


class RunVerdict(BaseModel):
    trace_id: str
    scenario_id: str
    passed: bool
    findings: List[FailureFinding] = Field(default_factory=list)
    expected_behavior_met: bool = True
    counterfactual_trace_id: Optional[str] = None
    counterfactual_passed: Optional[bool] = None
    attack_causation_proven: bool = False


class FailureCluster(BaseModel):
    id: str
    label: str
    category: str
    member_verdict_ids: List[str] = Field(default_factory=list)
    representative_evidence: str
    count: int
    severity: str = "high"
    recommended_fix: str


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
