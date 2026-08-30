"""
Agent Configuration, Encrypted Credentials, and Setup State Models.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class AgentConfigurationRecord(BaseModel):
    id: str
    user_id: str
    agent_id: str
    execution_mode: str = "faithful"
    selected_provider: str = "openai"
    selected_model: str = "default"
    configuration_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class AgentCredentialRecord(BaseModel):
    id: str
    user_id: str
    agent_id: str
    credential_name: str
    credential_type: str = "api_key"
    provider: str = "custom"
    encrypted_value: str
    masked_value: str
    validation_status: str = "SAVED"  # "SAVED", "VALID", "INVALID", "UNAVAILABLE"
    last_validated_at: Optional[str] = None
    is_active: bool = True
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class AgentSetupStateRecord(BaseModel):
    id: str
    user_id: str
    agent_id: str
    setup_status: str = "NOT_READY"  # "READY", "NOT_READY", "CHECKING", "BLOCKED", "STALE"
    preflight_status: str = "NOT_READY"
    requirements_json: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_dependencies_json: List[Dict[str, Any]] = Field(default_factory=list)
    blockers_json: List[str] = Field(default_factory=list)
    last_checked_at: str = Field(default_factory=_now)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class CredentialStatusItem(BaseModel):
    credential_name: str
    credential_type: str = "api_key"
    provider: str = "custom"
    configured: bool = False
    validation_status: str = "UNCONFIGURED"  # "VALID", "INVALID", "SAVED", "UNCONFIGURED"
    source: str = "MISSING"  # "USER_SAVED", "PLATFORM_DEFAULT", "COMPATIBLE_ADAPTER", "MISSING"
    masked: Optional[str] = None
    last_validated_at: Optional[str] = None
    is_required: bool = True
    hint: Optional[str] = None


class SaveAgentCredentialRequest(BaseModel):
    credential_name: str
    credential_value: str
    credential_type: str = "api_key"
    provider: Optional[str] = None


class ValidateCredentialRequest(BaseModel):
    credential_name: str
    credential_value: Optional[str] = None  # If empty, tests currently stored encrypted key


class ValidateCredentialResponse(BaseModel):
    credential_name: str
    status: str  # "VALID", "INVALID", "UNAVAILABLE"
    message: str
    latency_ms: float = 0.0
    tested_at: str = Field(default_factory=_now)


class UpdateAgentConfigurationRequest(BaseModel):
    execution_mode: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_model: Optional[str] = None
    slot_configs: Optional[Dict[str, Any]] = None
    configuration_json: Optional[Dict[str, Any]] = None
