"""
Pydantic Data Models for Stage Agent Testers and Judges.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class StageAuditRequest(BaseModel):
    agent_id: str
    stage_name: str  # "analysis", "scenarios", "sandbox_execution", "evaluation", "repair", "training"
    input_data: Dict[str, Any] = Field(default_factory=dict)
    result_data: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    requested_model: Optional[str] = None
    custom_criteria: Optional[List[str]] = None


class StageAuditVerdict(BaseModel):
    id: str
    agent_id: str
    stage_name: str
    tester_session_id: str
    model_used: str
    provider_used: str
    status: str  # "PASS", "WARNING", "DEFECT"
    score: int  # 0 to 100
    fidelity_score: float  # 0.0 to 1.0
    summary: str
    input_summary: str
    output_summary: str
    strengths: List[str] = Field(default_factory=list)
    findings_and_discrepancies: List[str] = Field(default_factory=list)
    hallucination_detected: bool = False
    recommendations: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    created_at: str = Field(default_factory=_now)


class StageTesterHealth(BaseModel):
    active_cloud_keys: int
    configured_model: str
    local_model_endpoint: str
    local_model_name: str
    local_model_connected: bool
    local_model_status: str
    available_sessions_count: int
    stage_fallback_models: Dict[str, str] = Field(default_factory=dict)
    tester_fallback_model: str = "qwen2.5-coder:7b"
    status: str  # "healthy", "degraded", "offline"


class MultiAgentAuditRequest(BaseModel):
    agent_ids: List[str] = Field(default_factory=list)
    stage_name: str  # "analysis", "scenarios", "sandbox_execution", "evaluation", "repair", "training"
    requested_model: Optional[str] = None
    custom_criteria: Optional[List[str]] = None


class AgentAuditItem(BaseModel):
    agent_id: str
    agent_name: str
    status: str  # "PASS", "WARNING", "DEFECT"
    score: int
    input_summary: str
    output_summary: str
    strengths: List[str] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class TrainingRecord(BaseModel):
    stage: str
    system_prompt: str
    user_input: str
    ideal_response: str
    rejected_response: Optional[str] = None
    reasoning_critique: str = ""
    agent_id: str = ""


class MultiAgentAuditVerdict(BaseModel):
    id: str
    stage_name: str
    agent_count: int
    overall_status: str  # "PASS", "WARNING", "DEFECT"
    overall_score: int  # 0 to 100
    overall_improvement_needed: str
    system_prompt_recommendations: List[str] = Field(default_factory=list)
    code_remediation_recommendations: List[str] = Field(default_factory=list)
    agent_results: List[AgentAuditItem] = Field(default_factory=list)
    training_dataset: List[TrainingRecord] = Field(default_factory=list)
    local_fallback_model: str = "qwen2.5-coder:7b"
    tester_fallback_model: str = "qwen2.5-coder:7b"
    latency_ms: float = 0.0
    created_at: str = Field(default_factory=_now)

