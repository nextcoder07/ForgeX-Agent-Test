"""
Canonical Agent Subsystem Representation for ForgeX.
Provides evidence-backed models for Planning, Memory, Context/RAG, Tools,
External Services, Model Slots, and Governance.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class PlanningType(str, Enum):
    DIRECT_SHOT = "DIRECT_SHOT"
    REACT = "REACT"
    PLANNER_EXECUTOR = "PLANNER_EXECUTOR"
    ROUTER = "ROUTER"
    WORKFLOW_STATE_MACHINE = "WORKFLOW_STATE_MACHINE"
    MULTI_AGENT_DELEGATION = "MULTI_AGENT_DELEGATION"
    ITERATIVE_LOOP = "ITERATIVE_LOOP"
    CUSTOM = "CUSTOM"


class PlanningProfile(BaseModel):
    planning_present: bool = False
    planning_type: PlanningType = PlanningType.DIRECT_SHOT
    planner_component: Optional[str] = None
    planner_model_slot: Optional[str] = None
    goal_representation: Optional[str] = None
    plan_representation: Optional[str] = None
    plan_steps: List[str] = Field(default_factory=list)
    dynamic_replanning: bool = False
    reflection_present: bool = False
    loop_present: bool = False
    termination_condition: Optional[str] = None
    max_iterations: Optional[int] = None
    branching_conditions: List[str] = Field(default_factory=list)
    delegation_present: bool = False
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class MemoryType(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PROCEDURAL = "PROCEDURAL"
    CONVERSATION_HISTORY = "CONVERSATION_HISTORY"
    VECTOR_STORE = "VECTOR_STORE"
    DATABASE_MEMORY = "DATABASE_MEMORY"
    FILE_MEMORY = "FILE_MEMORY"
    SESSION_STATE = "SESSION_STATE"
    WORKFLOW_STATE = "WORKFLOW_STATE"


class MemoryProfile(BaseModel):
    memory_present: bool = False
    memory_types: List[MemoryType] = Field(default_factory=list)
    storage_backend: Optional[str] = None
    retrieval_mechanism: Optional[str] = None
    write_points: List[str] = Field(default_factory=list)
    read_points: List[str] = Field(default_factory=list)
    persistence_scope: str = "SESSION"  # "EPHEMERAL", "SESSION", "PERSISTENT_CROSS_SESSION"
    session_scope: Optional[str] = None
    expiration: Optional[str] = None
    mutation_behavior: str = "APPEND_ONLY"  # "APPEND_ONLY", "MUTABLE_OVERWRITE", "LRU_EVICTION"
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class ContextProfile(BaseModel):
    retrieval_present: bool = False
    retrieval_backend: Optional[str] = None
    retriever: Optional[str] = None
    reranker: Optional[str] = None
    chunking: Optional[str] = None
    max_context_tokens: Optional[int] = None
    truncation_rules: List[str] = Field(default_factory=list)
    grounding_rules: List[str] = Field(default_factory=list)
    citation_rules: List[str] = Field(default_factory=list)
    context_sources: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class ToolSideEffectType(str, Enum):
    NONE = "NONE"
    FILESYSTEM = "FILESYSTEM"
    DATABASE_WRITE = "DATABASE_WRITE"
    NETWORK_MUTATION = "NETWORK_MUTATION"
    PAYMENT_FINANCIAL = "PAYMENT_FINANCIAL"
    EMAIL_COMMUNICATION = "EMAIL_COMMUNICATION"
    PROCESS_EXECUTION = "PROCESS_EXECUTION"


class ToolProfile(BaseModel):
    tool_id: str
    name: str
    description: str
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)
    side_effect_type: ToolSideEffectType = ToolSideEffectType.NONE
    is_read_only: bool = True
    destructive: bool = False
    authorization_required: bool = False
    confirmation_required: bool = False
    idempotency: bool = True
    target_service: Optional[str] = None
    source_evidence: str = ""
    policy_constraints: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class ExternalServiceProfile(BaseModel):
    service_id: str
    provider: str
    endpoint: Optional[str] = None
    required_credentials: List[str] = Field(default_factory=list)
    availability: str = "ACTIVE"
    timeout_seconds: float = 10.0
    retry_policy: Optional[str] = None
    mock_adapter: Optional[str] = None
    sandbox_adapter: Optional[str] = None
    evidence: str = ""


class ModelSlotRole(str, Enum):
    PRIMARY = "PRIMARY"
    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    EXECUTOR = "EXECUTOR"
    REVIEWER_CRITIC = "REVIEWER_CRITIC"
    ROUTER = "ROUTER"
    VISION = "VISION"
    EMBEDDING = "EMBEDDING"


class AgentModelSlot(BaseModel):
    slot_id: str
    agent_id: str
    role: ModelSlotRole = ModelSlotRole.PRIMARY
    name: str = "Primary Model"
    code_variable: str = "llm"
    source_location: str = ""
    detected_provider: str = "openai"
    detected_model: str = "gpt-4o-mini"
    model_usage: str = "INFERENCE"  # "INFERENCE", "EMBEDDING", "CLASSIFICATION"
    required: bool = True
    bound_connection_id: str = "system_default"
    owner_type: str = "FORGEX"  # "FORGEX", "USER"
    is_trainable: bool = False


class LearningProfile(BaseModel):
    learning_present: bool = False
    reflection_enabled: bool = False
    in_context_feedback: bool = False
    self_correction_present: bool = False
    feedback_sources: List[str] = Field(default_factory=list)
    adaptation_mechanisms: List[str] = Field(default_factory=list)
    fine_tuning_eligible: bool = True
    evidence: List[str] = Field(default_factory=list)


class GovernanceProfile(BaseModel):
    guardrails_present: bool = True
    never_rules: List[str] = Field(default_factory=list)
    always_rules: List[str] = Field(default_factory=list)
    escalation_triggers: List[str] = Field(default_factory=list)
    hallucination_safeguards: List[str] = Field(default_factory=list)
    confirmation_policies: List[str] = Field(default_factory=list)
    prompt_injection_defense: bool = True
    evidence: List[str] = Field(default_factory=list)


class CommunicationProfile(BaseModel):
    interface_type: str = "CHAT"  # "CHAT", "CLI", "HTTP", "EVENT", "AGENT_TO_AGENT"
    multi_turn_dialogue: bool = True
    intent_classification_present: bool = True
    emotional_tone_constraints: List[str] = Field(default_factory=list)
    output_formatting_rules: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class DataFlowEdge(BaseModel):
    source: str
    target: str
    data_type: str
    description: str = ""


class CanonicalAgentRepresentation(BaseModel):
    agent_id: str
    name: str
    domain: str
    archetype: str
    planning: PlanningProfile = Field(default_factory=PlanningProfile)
    memory: MemoryProfile = Field(default_factory=MemoryProfile)
    context: ContextProfile = Field(default_factory=ContextProfile)
    tools: List[ToolProfile] = Field(default_factory=list)
    external_services: List[ExternalServiceProfile] = Field(default_factory=list)
    model_slots: List[AgentModelSlot] = Field(default_factory=list)
    learning: LearningProfile = Field(default_factory=LearningProfile)
    governance: GovernanceProfile = Field(default_factory=GovernanceProfile)
    communication: CommunicationProfile = Field(default_factory=CommunicationProfile)
    data_flows: List[DataFlowEdge] = Field(default_factory=list)
    policies: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)

