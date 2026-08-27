"""
Execution Requirement & Automatic Resolution Data Models.
Provides fine-grained tracking of dependency requirements, resolution methods,
fidelity levels, and user-input blocking states.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RequirementType(str, Enum):
    AI_MODEL = "AI_MODEL"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    CREDENTIAL = "CREDENTIAL"
    DATABASE = "DATABASE"
    PACKAGE = "PACKAGE"
    RUNTIME = "RUNTIME"
    BROWSER = "BROWSER"
    DATASET = "DATASET"
    FILESYSTEM = "FILESYSTEM"


class ResolutionMethod(str, Enum):
    AGENT_CODE = "AGENT_CODE"
    PLATFORM_MANAGED = "PLATFORM_MANAGED"
    SANDBOX_MOCK = "SANDBOX_MOCK"
    SYNTHETIC_CORPUS = "SYNTHETIC_CORPUS"
    USER_SUPPLIED = "USER_SUPPLIED"
    SAFE_DEFAULT = "SAFE_DEFAULT"
    UNRESOLVED = "UNRESOLVED"


class RequirementFidelity(str, Enum):
    FAITHFUL = "FAITHFUL"
    SIMULATED = "SIMULATED"
    MODEL_SUBSTITUTED = "MODEL_SUBSTITUTED"
    MOCKED = "MOCKED"


class RequirementStatus(str, Enum):
    RESOLVED_PLATFORM = "RESOLVED_PLATFORM"
    RESOLVED_USER = "RESOLVED_USER"
    RESOLVED_SANDBOX = "RESOLVED_SANDBOX"
    OPTIONAL = "OPTIONAL"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    BLOCKED = "BLOCKED"


class ExecutionRequirement(BaseModel):
    id: str
    agent_id: str
    type: RequirementType
    name: str  # e.g. "NewsAPI", "PostgreSQL", "Researcher Model", "Python 3.12", "STRIPE_API_KEY"
    detected_from: str  # e.g. "requirements.txt", "ast_import", "os.getenv", "decorator"
    required: bool = True
    optional: bool = False
    default_available: bool = True
    platform_provider: Optional[str] = None
    user_value_available: bool = False
    sandbox_adapter_available: bool = False
    resolved_value: Optional[str] = None
    resolution_method: ResolutionMethod = ResolutionMethod.PLATFORM_MANAGED
    fidelity: RequirementFidelity = RequirementFidelity.SIMULATED
    blocking: bool = False
    status: RequirementStatus = RequirementStatus.RESOLVED_SANDBOX
    description: str = ""
    action_label: Optional[str] = None


class AgentRequirementsReport(BaseModel):
    agent_id: str
    agent_name: str
    overall_status: str = "READY"  # "READY", "NEEDS_INPUT", "BLOCKED"
    needs_user_input_count: int = 0
    total_requirements_count: int = 0
    ai_models: List[ExecutionRequirement] = Field(default_factory=list)
    external_services: List[ExecutionRequirement] = Field(default_factory=list)
    environment: List[ExecutionRequirement] = Field(default_factory=list)
    active_fidelity: str = "SIMULATED"
    generated_at: str = Field(default_factory=_now)
