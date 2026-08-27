"""
Data Models for ForgeX Platform-AI Meta-Evaluation, Self-Improvement & Benchmark Engine.
Defines the 4 Trainable Stage Roles, Evidence Packs, Reports, Datasets, and Model Bindings.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# 1. Core Platform AI Roles
# ---------------------------------------------------------------------------
class PlatformStageRole(str, Enum):
    INTAKE_ANALYST = "INTAKE_ANALYST"
    SCENARIO_PLANNER = "SCENARIO_PLANNER"
    EXECUTION_OBSERVER = "EXECUTION_OBSERVER"
    IMPROVEMENT_ANALYST = "IMPROVEMENT_ANALYST"
    META_EVALUATOR = "META_EVALUATOR"


class DetectionFactResult(str, Enum):
    CORRECT = "CORRECT"
    MISSED = "MISSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    AMBIGUOUS = "AMBIGUOUS"


class ScenarioQualityClass(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    IRRELEVANT = "IRRELEVANT"
    REDUNDANT = "REDUNDANT"
    MISSING_COVERAGE = "MISSING_COVERAGE"


class DatasetSplitType(str, Enum):
    TRAIN = "TRAIN"          # 70%
    VALIDATION = "VALIDATION" # 15%
    HELD_OUT = "HELD_OUT"    # 15% - Frozen benchmark, never trained upon


# ---------------------------------------------------------------------------
# 2. Stage Model Bindings & Connection Records
# ---------------------------------------------------------------------------
class StageModelBinding(BaseModel):
    id: str
    stage: PlatformStageRole
    stage_name: str
    primary_connection_id: str = "cloud_rotation_pool"
    fallback_connection_id: str
    active_connection_id: str = "primary"
    fallback_enabled: bool = True
    primary_model: str = "gemini-3.6-flash"
    fallback_model: str = "qwen2.5-coder:7b"
    adapter_reference: Optional[str] = None
    health_status: str = "HEALTHY"
    updated_at: str = Field(default_factory=_now)


class PlatformModelVersion(BaseModel):
    id: str
    stage: PlatformStageRole
    base_model: str = "qwen2.5-coder:7b"
    adapter_name: str
    version_label: str  # e.g. "v1.0", "v2.0-lora"
    training_job_id: Optional[str] = None
    parent_version_id: Optional[str] = None
    status: str = "PROMOTED"  # "TRAINING", "CANDIDATE", "BENCHMARKED", "PROMOTED", "REJECTED"
    benchmark_accuracy: float = 0.0
    held_out_score: float = 0.0
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 3. Stage Evaluation Evidence Packs (Grounded against Source & Runtime Truth)
# ---------------------------------------------------------------------------
class IntakeEvidenceFact(BaseModel):
    category: str  # "interface", "model_slot", "tool", "service", "credential", "workflow", "memory", "never_rule"
    fact_key: str
    expected_value: Any
    observed_value: Any
    source_reference: str  # e.g. "agent.py:48"
    result: DetectionFactResult
    severity: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    impact: str = ""


class IntakeEvidencePack(BaseModel):
    agent_id: str
    agent_name: str
    source_files_count: int
    source_summary: str
    facts: List[IntakeEvidenceFact] = Field(default_factory=list)
    behavior_profile_extracted: Dict[str, Any] = Field(default_factory=dict)
    ground_truth_spec: Dict[str, Any] = Field(default_factory=dict)


class ScenarioEvidenceItem(BaseModel):
    scenario_id: str
    title: str
    category: str
    target_surface: str
    quality: ScenarioQualityClass
    executable: bool
    assertions_valid: bool
    relevance_score: float = 1.0
    fault_realistic: bool = True
    evidence_ref: str = ""


class ScenarioEvidencePack(BaseModel):
    agent_id: str
    agent_name: str
    total_planned: int
    total_generated: int
    scenarios: List[ScenarioEvidenceItem] = Field(default_factory=list)
    coverage_gaps: List[str] = Field(default_factory=list)


class ExecutionObserverEvidenceItem(BaseModel):
    trajectory_id: str
    raw_event: str
    ground_truth_interpretation: Dict[str, Any]
    observed_interpretation: Dict[str, Any]
    is_accurate: bool
    event_invented: bool = False
    evidence_ref: str = ""


class ExecutionObserverEvidencePack(BaseModel):
    agent_id: str
    agent_name: str
    total_events_observed: int
    items: List[ExecutionObserverEvidenceItem] = Field(default_factory=list)


class ImprovementEvidenceItem(BaseModel):
    failure_id: str
    failure_category: str
    diagnosed_root_cause: str
    proposed_patch: str
    regression_before: str  # "FAIL"
    regression_after: str   # "PASS" or "FAIL"
    is_successful: bool
    evidence_ref: str = ""


class ImprovementEvidencePack(BaseModel):
    agent_id: str
    agent_name: str
    items: List[ImprovementEvidenceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 4. Stage Performance Reports & Overall Scorecards
# ---------------------------------------------------------------------------
class StagePerformanceReport(BaseModel):
    stage: PlatformStageRole
    stage_name: str
    model_connection_id: str
    model_version_id: str
    agents_tested: int
    cases_evaluated: int
    correct_count: int
    missed_count: int
    false_positive_count: int
    accuracy_pct: float
    precision_pct: float
    recall_pct: float
    coverage_pct: float
    quality_score: int  # 0 to 100 derived deterministically
    failure_categories: List[Dict[str, Any]] = Field(default_factory=list)
    system_prompt_improvements: List[str] = Field(default_factory=list)
    code_remediation_rules: List[str] = Field(default_factory=list)
    training_candidates_count: int = 0
    evidence_references: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class OverallPlatformPerformance(BaseModel):
    id: str
    evaluated_agent_ids: List[str] = Field(default_factory=list)
    evaluated_agents_count: int
    overall_score: int  # Weighted average across all 4 stages
    overall_status: str  # "EXCELLENT", "OPTIMAL", "DEFECT", "DEGRADED"
    stage_reports: Dict[str, StagePerformanceReport] = Field(default_factory=dict)
    meta_judge_model: str
    meta_judge_verdict_summary: str
    evaluated_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 5. Fine-Tuning Training Examples & Datasets (SFT, DPO, Splits)
# ---------------------------------------------------------------------------
class StageTrainingExample(BaseModel):
    id: str
    stage: PlatformStageRole
    agent_id: str
    agent_name: str
    split: DatasetSplitType = DatasetSplitType.TRAIN
    source_reference: str
    system_prompt: str
    user_input: str
    model_output: str          # What the flawed model originally produced
    ground_truth: str          # Real source facts / deterministic reality
    ideal_response: str        # SFT target
    rejected_response: str     # DPO rejected candidate
    reasoning_critique: str
    failure_category: str
    approval_status: str = "APPROVED"  # "PENDING", "APPROVED", "REJECTED"
    created_at: str = Field(default_factory=_now)


class StageDatasetExport(BaseModel):
    stage: PlatformStageRole
    total_examples: int
    train_count: int
    validation_count: int
    held_out_count: int
    target_local_model: str
    examples: List[StageTrainingExample] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. Model Version Comparison Benchmark
# ---------------------------------------------------------------------------
class ModelBenchmarkComparison(BaseModel):
    stage: PlatformStageRole
    benchmark_id: str
    held_out_sample_count: int
    model_v1_version: str
    model_v1_accuracy: float
    model_v1_quality_score: int
    model_v2_version: str
    model_v2_accuracy: float
    model_v2_quality_score: int
    delta_accuracy: float
    improved: bool
    recommendation: str  # "PROMOTE_V2", "REJECT_V2", "RETRAIN_MORE_DATA"
    comparison_timestamp: str = Field(default_factory=_now)
