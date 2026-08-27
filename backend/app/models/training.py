"""
Training Dataset Models for Future Model Improvement.
Stores SFT, DPO (Preference Pairs), and Failure-Recovery datasets generated
from truthful execution traces and human corrections.
"""

from __future__ import annotations
import uuid
import datetime as dt
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class SFTMessage(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class SFTExample(BaseModel):
    id: str = Field(default_factory=lambda: f"sft-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_version_id: Optional[str] = "v1.0"
    scenario_id: str
    scenario_title: Optional[str] = None
    category: str = "NORMAL"
    messages: List[SFTMessage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class PreferencePair(BaseModel):
    id: str = Field(default_factory=lambda: f"dpo-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_version_id: Optional[str] = "v1.0"
    scenario_id: str
    prompt: str
    chosen: str  # Successful / Safe action or response
    rejected: str  # Unsafe / Erroneous action or response
    reason: str  # Why chosen is better than rejected
    category: str = "SAFETY"
    margin: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class FailureRecoveryExample(BaseModel):
    id: str = Field(default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_version_id: Optional[str] = "v1.0"
    scenario_id: str
    error_state: str  # Description or code traceback of the failure
    attempted_action: str
    corrected_action: str
    recovery_strategy: str  # e.g., circuit_breaker, fallback_validation, human_confirmation
    created_at: str = Field(default_factory=_now)


class TrainingDataset(BaseModel):
    id: str = Field(default_factory=lambda: f"dataset-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    dataset_type: str = "SFT"  # SFT, DPO_PREFERENCE, FAILURE_RECOVERY, HYBRID
    format: str = "JSONL"  # JSONL, HUGGINGFACE_JSON, CSV
    example_count: int = 0
    sft_examples: List[SFTExample] = Field(default_factory=list)
    preference_pairs: List[PreferencePair] = Field(default_factory=list)
    recovery_examples: List[FailureRecoveryExample] = Field(default_factory=list)
    source_scenarios: List[str] = Field(default_factory=list)
    source_execution_runs: List[str] = Field(default_factory=list)
    export_ready: bool = True
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
