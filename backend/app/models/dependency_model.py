"""
Dependency Resolution, Execution Model Binding, and Agent Category Data Models.
Enforces transparent dependency recording and execution fidelity tracking.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentCategory(str, Enum):
    LLM_POWERED = "llm_powered"          # Type 1: OpenAI, Gemini, Anthropic, etc.
    LOCAL_MODEL = "local_model"          # Type 2: Ollama, HuggingFace, vLLM (no API key assumed)
    RULE_BASED = "rule_based"            # Type 3: Pure code/logic (LLM=False, ExtAPI=False)
    TOOL_HEAVY = "tool_heavy"            # Type 4: Agent connecting to DB, Email, Search, FileSystem


class ExecutionMode(str, Enum):
    FAITHFUL = "faithful"                # Mode 1: Uses original model/credentials. Fidelity=HIGH
    COMPATIBLE = "compatible"            # Mode 2: Model substitution (e.g., Gemini). Fidelity=MEDIUM
    SIMULATION = "simulation"            # Mode 3: MockLLM / deterministic scenario testing. Fidelity=TEST-SPECIFIC


class EvaluationFidelity(str, Enum):
    HIGH = "HIGH"                        # Faithful mode
    MEDIUM = "MEDIUM"                    # Compatible mode
    TEST_SPECIFIC = "TEST-SPECIFIC"      # Simulation mode


class DetectedSecret(BaseModel):
    name: str
    type: str = "secret"                # "secret", "config", "endpoint"
    required: bool = True
    masked_sample: str = "********"


class AgentModelDependency(BaseModel):
    id: str
    agent_id: str
    provider: str                        # "openai", "google", "anthropic", "ollama", "huggingface", "vllm", etc.
    model_name: str                      # "gpt-5", "gemini-2.5-flash", "llama3", etc.
    dependency_type: str = "llm"         # "llm", "local_model", "rule_based", "external_service"
    required: bool = True
    original_provider: str
    original_endpoint: Optional[str] = None
    detected_from: str                   # "ast_analysis", "env_var", "source_code", "config"
    created_at: str


class DependencyResolverRequest(BaseModel):
    agent_id: str
    requested_mode: Optional[ExecutionMode] = None
    provided_secrets: Dict[str, str] = Field(default_factory=dict)


class ExecutionModelBinding(BaseModel):
    id: str
    execution_id: str
    original_model: str
    executed_model: str
    original_provider: str
    executed_provider: str
    mode: ExecutionMode
    model_substitution: bool
    reason: str
    confidence: str                      # "high", "medium", "test-specific"
    fidelity: EvaluationFidelity
    created_at: str


class DependencyResolverResult(BaseModel):
    agent_id: str
    agent_category: AgentCategory
    detected_model_dependencies: List[AgentModelDependency] = Field(default_factory=list)
    detected_secrets: List[DetectedSecret] = Field(default_factory=list)
    recommended_mode: ExecutionMode
    mode_options: List[Dict[str, Any]] = Field(default_factory=list) # Options for UI selection
    active_binding: Optional[ExecutionModelBinding] = None


class SystemCredentialItem(BaseModel):
    key_name: str                        # e.g., "GEMINI_API_KEY", "OPENAI_API_KEY", "DATABASE_URL"
    provider: str                        # "google", "openai", "database", "serper", etc.
    description: str
    is_configured: bool
    source: str                          # "system_env" | "user_custom" | "missing"
    masked_value: Optional[str] = None   # e.g., "AIzaSy...4xQ"


class CredentialRequirement(BaseModel):
    key_name: str                        # e.g., "DB_API_KEY", "OPENAI_API_KEY"
    provider: str
    description: str
    is_fulfilled: bool
    is_optional: bool = False
    provided_by_system: bool = False
    masked_value: Optional[str] = None


class SessionCredentialPrompt(BaseModel):
    session_id: str
    agent_id: str
    all_fulfilled: bool
    status: str                          # "CREDS_REQUIRED" | "CLEARED"
    requirements: List[CredentialRequirement] = Field(default_factory=list)
    message: str


class ProvideCredentialsRequest(BaseModel):
    credentials: Dict[str, str] = Field(default_factory=dict) # e.g. {"DB_API_KEY": "secret_val"}
    save_to_system_default: bool = False
