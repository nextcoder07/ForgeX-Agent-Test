"""
Fix My Agent — Data Models for Agent Repair Sessions and Iterations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.evaluation import ReliabilityScorecard


class RepairStatus(str, Enum):
    IDLE_AWAITING_USER_APPROVAL = "IDLE_AWAITING_USER_APPROVAL"
    RUNNING = "RUNNING"
    COMPLETED_FIXED = "COMPLETED_FIXED"
    COMPLETED_PARTIAL = "COMPLETED_PARTIAL"
    STOPPED_BY_USER = "STOPPED_BY_USER"
    MAX_ITERATIONS_REACHED = "MAX_ITERATIONS_REACHED"
    FAILED = "FAILED"


class RepairIterationResult(BaseModel):
    iteration: int
    agent_id: str
    agent_version: str
    previous_version: str
    eval_scorecard: ReliabilityScorecard
    fixing_agent_reasoning: str
    changes_made: List[str] = Field(default_factory=list)
    diff_summary: str = ""
    passed_count: int
    failed_count: int
    critical_failures: int
    status: str  # "IMPROVED", "REGRESSED", "PASSED", "FAILED"
    created_at: str


class RepairSession(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    original_version: str
    current_version: str
    status: RepairStatus = RepairStatus.IDLE_AWAITING_USER_APPROVAL
    max_iterations: int = 5
    current_iteration: int = 0
    current_step: str = ""
    baseline_evaluation_id: Optional[str] = None
    latest_evaluation_id: Optional[str] = None
    baseline_agent_version_id: Optional[str] = None
    current_agent_version_id: Optional[str] = None
    baseline_scorecard: Optional[ReliabilityScorecard] = None
    latest_scorecard: Optional[ReliabilityScorecard] = None
    baseline_score: float = 0.0
    repaired_score: float = 0.0
    remaining_failures: int = 0
    critical_failures: int = 0
    iterations: List[RepairIterationResult] = Field(default_factory=list)
    final_status: str = "Not Repaired"  # "Fixed", "Partially Fixed", "Failed", "Not Repaired"
    final_verdict: str = "Not Repaired"  # "REPAIRED", "NOT_REPAIRED", "PARTIALLY_REPAIRED", "FAILED"
    error_message: Optional[str] = None
    user_approved_repair: bool = False
    stop_requested: bool = False
    created_at: str
    started_at: Optional[str] = None
    updated_at: str
    finished_at: Optional[str] = None

