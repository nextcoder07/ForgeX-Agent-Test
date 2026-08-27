"""
Agent, Tool, Constitution, and Component Models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Optional[Dict[str, Any]] = None
    risk: ToolRisk = ToolRisk.LOW
    is_destructive: bool = False
    requires_confirmation: bool = False
    requires_authorization: bool = False
    max_amount: Optional[float] = None
    canonical_capability: Optional[str] = None
    side_effect_type: Optional[str] = None  # "READ", "WRITE", "DELETE", "PAYOUT", "EMAIL"


class DependencyDefinition(BaseModel):
    id: str
    name: str
    type: str  # "database", "email", "browser", "payment", "filesystem", "http"
    required: bool = True
    detected_from: str  # "AST_IMPORT", "DOC_STRING", "CONFIG"
    status: str = "READY_PLATFORM_SANDBOX"  # "READY_PLATFORM_SANDBOX", "USER_SUPPLIED", "BLOCKED"


class AgentConstitution(BaseModel):
    goals: List[str] = Field(default_factory=list)
    never_rules: List[str] = Field(default_factory=list)
    always_rules: List[str] = Field(default_factory=list)
    escalation_rules: List[str] = Field(default_factory=list)
    data_policies: List[str] = Field(default_factory=list)


class AgentComponent(BaseModel):
    id: str
    path: str
    component_type: str  # "FUNCTION", "CLASS", "PROMPT", "TOOL", "CONFIG"
    hash: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


import datetime as dt

def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class AgentVersion(BaseModel):
    id: str
    agent_id: str
    version_label: str
    artifact_hash: str
    framework: str = "custom"
    language: str = "python"
    entrypoint: str = "agent.py"
    tools: List[ToolDefinition] = Field(default_factory=list)
    dependencies: List[DependencyDefinition] = Field(default_factory=list)
    constitution: AgentConstitution = Field(default_factory=AgentConstitution)
    created_at: str = Field(default_factory=_now)


class AgentRecord(BaseModel):
    id: str
    name: str  # unique registered name used by the platform
    description: str
    display_name: Optional[str] = None
    source_name: Optional[str] = None  # name inferred from uploaded/demo source
    domain: str = "general"
    system_prompt: str = ""
    tools: List[ToolDefinition] = Field(default_factory=list)
    dependencies: List[DependencyDefinition] = Field(default_factory=list)
    constitution: AgentConstitution = Field(default_factory=AgentConstitution)
    endpoint: Optional[str] = None
    version_label: str = "v1.0"
    current_version_id: Optional[str] = None
    artifact_id: Optional[str] = None
    artifact_hash: Optional[str] = None
    source_files: Dict[str, str] = Field(default_factory=dict)
    runtime_manifest: Dict[str, Any] = Field(default_factory=dict)
    canonical_agent: Optional[Any] = None
    execution_status: str = "EXECUTION_BLOCKED"
    input_type: str = "package"
    created_at: str = Field(default_factory=_now)
