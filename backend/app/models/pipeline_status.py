"""
Agent Pipeline Lifecycle Stage Status Models.
Tracks the strict progression and prerequisite state machine across all 10 stages:
Intake -> Scenarios -> Sandbox -> Execution -> Evaluation -> Diagnosis -> Fix Agent / Train Model.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class StageStepStatus(BaseModel):
    stage_id: str
    stage_number: int
    name: str
    status: str  # "COMPLETED", "IN_PROGRESS", "READY_TO_START", "BLOCKED", "OPTIONAL_AVAILABLE"
    is_completed: bool
    is_blocked: bool
    blocker_reason: Optional[str] = None
    next_action_route: str
    next_action_label: str
    metrics_summary: Optional[str] = None


class AgentPipelineStageStatus(BaseModel):
    agent_id: str
    agent_name: str
    current_version: str = "v1.0"
    
    # Counts
    total_scenarios_count: int = 0
    executed_sessions_count: int = 0
    evaluated_verdicts_count: int = 0
    total_failures_count: int = 0
    critical_failures_count: int = 0
    latest_scorecard_score: Optional[float] = None
    training_datasets_count: int = 0
    training_jobs_count: int = 0
    
    # Prerequisite Flags
    intake_completed: bool = False
    scenarios_generated: bool = False
    sandbox_ready: bool = False
    execution_completed: bool = False
    evaluation_completed: bool = False
    diagnosis_completed: bool = False
    ready_for_code_repair: bool = False
    ready_for_model_training: bool = True  # Model training is permitted directly once agent intake exists
    
    stages: List[StageStepStatus] = Field(default_factory=list)
    overall_pipeline_progress: float = 0.0
    recommended_next_stage: str = "scenarios"
    updated_at: str = Field(default_factory=_now)
