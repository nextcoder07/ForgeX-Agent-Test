"""
Observable Pipeline Run, Stage Telemetry, and Real Metric Models.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PipelineStage(BaseModel):
    id: str
    stage_name: str
    display_title: str
    status: str = "queued"  # "queued", "running", "completed", "failed", "skipped"
    progress_pct: int = 0
    duration_ms: float = 0.0
    model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.6-flash"))
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class TelemetryEvent(BaseModel):
    id: str
    stage_id: str
    timestamp: str
    event_type: str  # "STAGE_START", "STAGE_PROGRESS", "STAGE_FINISH", "METRIC_CAPTURED"
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PipelineRun(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    status: str = "running"  # "running", "completed", "failed"
    total_stages: int = 10
    completed_stages: int = 0
    overall_duration_ms: float = 0.0
    stages: List[PipelineStage] = Field(default_factory=list)
    events: List[TelemetryEvent] = Field(default_factory=list)
    started_at: str
    completed_at: Optional[str] = None


class AIGenerationRun(BaseModel):
    id: str
    stage: str
    provider: str
    model: str
    status: str  # "SUCCESS", "FAILED", "FALLBACK", "BLOCKED"
    input_tokens: int = 0
    output_tokens: int = 0
    error_message: Optional[str] = None
    prompt_version: str = "v1"
    input_reference: Optional[Dict[str, Any]] = None
    output_reference: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class AIGenerationRun(BaseModel):
    id: str
    stage: str
    provider: str
    model: str
    status: str  # "SUCCESS", "FAILED", "FALLBACK", "BLOCKED"
    input_tokens: int = 0
    output_tokens: int = 0
    error_message: Optional[str] = None
    prompt_version: str = "v1"
    input_reference: Optional[Dict[str, Any]] = None
    output_reference: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
