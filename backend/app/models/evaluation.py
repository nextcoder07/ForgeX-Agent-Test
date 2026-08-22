"""
Evaluation Run, Scorecard, Verdict, 10-Dimension Breakdown, and Explainable Evaluation Report Models.
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
    requested_mode: Optional[str] = None # "faithful", "compatible", "simulation"


class EvaluationJob(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    agent_version: str
    status: str = "pending"  # "pending", "running", "completed", "failed"
    total_scenarios: int = 25
    completed_scenarios: int = 0
    execution_mode: str = "faithful"
    original_model: Optional[str] = None
    executed_model: Optional[str] = None
    model_substitution: bool = False
    confidence: str = "HIGH"
    created_at: str
    finished_at: Optional[str] = None


class TenDimensionScoreBreakdown(BaseModel):
    task_correctness: float = 0.0          # 25% weight
    instruction_following: float = 0.0     # 15% weight
    tool_correctness: float = 0.0          # 20% weight
    tool_parameter_correctness: float = 0.0# 10% weight
    workflow_correctness: float = 0.0      # 5% weight
    failure_recovery: float = 0.0          # 10% weight
    safety: float = 0.0                    # 15% weight
    robustness: float = 0.0                # 5% weight
    response_quality: float = 0.0          # 5% weight
    efficiency: float = 0.0                # 5% weight
    overall_score: float = 0.0


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
    judge_agreement_rate: Optional[float] = None
    execution_mode: str = "faithful"
    model_substitution: bool = False
    confidence: str = "HIGH"
    dimension_scores: Optional[TenDimensionScoreBreakdown] = None


class EvaluationReport(BaseModel):
    evaluation_id: str
    agent_id: str
    agent_name: str
    scenario_id: Optional[str] = None
    original_model: Optional[str] = None
    executed_model: Optional[str] = None
    execution_mode: str = "compatible"     # "faithful", "compatible", "simulation"
    model_substitution: bool = False
    confidence: str = "MEDIUM"             # "HIGH", "MEDIUM", "TEST-SPECIFIC"
    overall_score: float
    dimension_scores: TenDimensionScoreBreakdown
    explainability: List[str] = Field(default_factory=list) # "Why: ..." evidence list
    strengths: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    execution_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str


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
