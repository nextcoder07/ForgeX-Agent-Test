"""
Evaluation Run, Scorecard, Verdict, 10-Dimension Breakdown, Explainable Evaluation Report, and Regression Test Models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    agent_id: str
    execution_run_id: Optional[str] = None
    scenario_batch_size: int = 25
    categories: Optional[List[str]] = None
    chaos_mode: bool = False
    include_counterfactuals: bool = True
    requested_mode: Optional[str] = None  # "faithful", "compatible", "simulation"


class EvaluationJob(BaseModel):
    id: str
    agent_id: str
    agent_version_id: Optional[str] = None
    agent_name: str
    agent_version: str = "v1.0"

    execution_run_id: Optional[str] = None
    sandbox_specification_id: Optional[str] = None
    behavior_profile_id: Optional[str] = None
    scenario_set_id: Optional[str] = None

    status: str = "pending"  # "pending", "running", "evaluating", "aggregating", "completed", "failed", "blocked", "cancelled", "partial"
    current_step: str = "Job queued..."
    error_message: Optional[str] = None
    total_scenarios: int = 25
    completed_scenarios: int = 0
    total_verdicts: int = 0

    execution_mode: str = "faithful"
    original_model: Optional[str] = None
    executed_model: Optional[str] = None
    model_substitution: bool = False
    confidence: str = "HIGH"
    fidelity: float = 1.0

    evaluator_version: str = "v2.0"
    rule_set_version: str = "reliability-rules-v2"

    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class TenDimensionScoreBreakdown(BaseModel):
    # 10 Core Dimensions (Optional[float] allows None for NOT_APPLICABLE dimensions)
    correctness: Optional[float] = 0.0          # Task correctness (25% default weight)
    goal_adherence: Optional[float] = 0.0       # Goal adherence (15% default weight)
    safety: Optional[float] = 0.0               # Safety policies (15% default weight)
    security: Optional[float] = 0.0             # Prompt injection / PII (10% default weight)
    robustness: Optional[float] = 0.0           # Boundary & chaos resilience (5% default weight)
    tool_discipline: Optional[float] = 0.0      # Tool selection & parameter schema (10% default weight)
    recovery: Optional[float] = 0.0             # Failure & retry recovery (5% default weight)
    output_quality: Optional[float] = 0.0       # Response clarity & structure (5% default weight)
    efficiency: Optional[float] = 0.0           # Token & latency discipline (5% default weight)
    compliance: Optional[float] = 0.0           # Policy & regulatory compliance (5% default weight)

    overall_score: float = 0.0
    applicable_dimensions: List[str] = Field(default_factory=list)


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
    blocked: int = 0
    inconclusive: int = 0
    critical_failures: int
    judge_agreement_rate: Optional[float] = None
    execution_mode: str = "faithful"
    model_substitution: bool = False
    confidence: str = "HIGH"

    score_formula_version: str = "v2.0-weighted"
    weights: Dict[str, float] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    dimension_scores: Optional[TenDimensionScoreBreakdown] = None


class EvaluationReport(BaseModel):
    evaluation_id: str
    agent_id: str
    agent_name: str
    scenario_id: Optional[str] = None
    execution_run_id: Optional[str] = None
    original_model: Optional[str] = "openai/gpt-5"
    executed_model: Optional[str] = "google/gemini-2.5-flash"
    execution_mode: str = "compatible"
    model_substitution: bool = False
    confidence: str = "MEDIUM"
    overall_score: float
    dimension_scores: TenDimensionScoreBreakdown
    score_formula_version: str = "v2.0-weighted"

    explainability: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    root_causes: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    execution_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_summary: List[Dict[str, Any]] = Field(default_factory=list)
    dimension_breakdown: Dict[str, Any] = Field(default_factory=dict)

    evaluator_version: str = "v2.0"
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


class RegressionTest(BaseModel):
    id: str
    source_evaluation_id: str
    source_verdict_id: str
    agent_id: str
    scenario_id: str
    failure_category: str
    severity: str = "high"  # "critical", "high", "medium", "low"
    assertion: Dict[str, Any] = Field(default_factory=dict)
    status: str = "ACTIVE"  # "ACTIVE", "PASSED", "DEPRECATED", "IGNORED"
    created_at: str
    updated_at: str
