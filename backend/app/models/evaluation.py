"""
Evaluation Run, Scorecard, Verdict, and Regression Comparison Models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    agent_id: str
    scenario_batch_size: int = 25
    categories: Optional[List[str]] = None
    chaos_mode: bool = False
    include_counterfactuals: bool = True


class EvaluationJob(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    agent_version: str
    status: str = "pending"  # "pending", "running", "completed", "failed"
    total_scenarios: int = 25
    completed_scenarios: int = 0
    created_at: str
    finished_at: Optional[str] = None


class ReliabilityScorecard(BaseModel):
    evaluation_id: str
    agent_id: str
    agent_name: str
    agent_version: str
    correctness: float
    safety: float
    robustness: float
    tool_discipline: float
    goal_adherence: float
    composite: float
    safety_axis: float  # 0 - 100 for 2D quadrant
    capability_axis: float  # 0 - 100 for 2D quadrant
    total_scenarios: int
    passed: int
    failed: int
    critical_failures: int
    judge_agreement_rate: float = 94.5


class RegressionComparison(BaseModel):
    from_agent_id: str
    from_version: str
    to_agent_id: str
    to_version: str
    safety_delta: float
    capability_delta: float
    composite_delta: float
    resolved_failures: List[str] = Field(default_factory=list)
    new_regressions: List[str] = Field(default_factory=list)
    summary_verdict: str
