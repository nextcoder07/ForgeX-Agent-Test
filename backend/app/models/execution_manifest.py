"""
Canonical ExecutionManifest Model.
Immutable snapshot of agent, interface, dependencies, models, credentials,
services, targeted behavior, and scenario assertions before sandbox provisioning.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class AgentExecutionSpec(BaseModel):
    agent_id: str
    agent_version_id: str = "v1.0"
    artifact_hash: str = ""
    entrypoint: str = "agent.py"
    working_directory: str = "/workspace"
    language: str = "python"
    runtime_version: str = "3.12"


class InterfaceExecutionSpec(BaseModel):
    interface_type: str = "CHAT"  # "CLI", "HTTP", "CHAT", "FUNCTION"
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    endpoint: Optional[str] = None
    method: str = "POST"
    user_messages: List[str] = Field(default_factory=list)
    input_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    environment_variables: Dict[str, str] = Field(default_factory=dict)


class DependencyExecutionSpec(BaseModel):
    package_name: str
    import_name: str
    requested_version: Optional[str] = None
    required: bool = True
    resolution_state: str = "BOUND"  # "DETECTED", "RESOLVED", "BOUND", "PROVISIONING", "INSTALLED", "VERIFIED"


class ModelExecutionSpec(BaseModel):
    provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    credential_key: str = "OPENAI_API_KEY"
    is_local: bool = False


class CredentialExecutionSpec(BaseModel):
    key_name: str
    provider: str = "UNKNOWN"
    required: bool = True
    status: str = "AVAILABLE"  # "AVAILABLE", "USER_REQUIRED", "MISSING", "PLATFORM_PROVIDED"
    masked_value: str = "***"


class ScenarioExecutionSpec(BaseModel):
    scenario_id: str
    title: str
    category: str = "NORMAL"
    target_tool: Optional[str] = None
    target_function: Optional[str] = None
    target_workflow_node: Optional[str] = None
    target_service: Optional[str] = None
    fault_injections: List[Dict[str, Any]] = Field(default_factory=list)
    assertions: List[Dict[str, Any]] = Field(default_factory=list)


class ExecutionManifest(BaseModel):
    id: str
    agent: AgentExecutionSpec
    interface: InterfaceExecutionSpec
    dependencies: List[DependencyExecutionSpec] = Field(default_factory=list)
    models: List[ModelExecutionSpec] = Field(default_factory=list)
    credentials: List[CredentialExecutionSpec] = Field(default_factory=list)
    scenario: ScenarioExecutionSpec
    created_at: str = Field(default_factory=_now)
