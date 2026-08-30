"""
Scenario, Strategy Plan, Fault Injection, and Coverage Models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScenarioCategory(str, Enum):
    NORMAL = "normal"
    EDGE = "edge"
    RECOVERY = "recovery"
    ADVERSARIAL = "adversarial"
    SAFETY = "safety"
    SECURITY = "security"
    STRESS = "stress"
    CHAOS = "chaos"
    DESTRUCTIVE_GUARDRAIL = "destructive_guardrail"


class TargetSubsystem(str, Enum):
    # Legacy / generic (backward compat)
    REASONING_PLANNING = "reasoning_planning"
    MEMORY_CONTEXT = "memory_context"
    TOOL_EXECUTION = "tool_execution"
    LEARNING_ADAPTATION = "learning_adaptation"
    GOVERNANCE_SECURITY = "governance_security"
    COMMUNICATION_INTERFACE = "communication_interface"
    MULTI_AGENT_ORCHESTRATION = "multi_agent_orchestration"

    # Stage 2 expanded subsystems (spec §3)
    INPUT_HANDLING = "input_handling"
    FUNCTIONAL_EXECUTION = "functional_execution"
    OUTPUT_VALIDATION = "output_validation"
    TOOL_USAGE = "tool_usage"
    TOOL_AUTHORIZATION = "tool_authorization"
    EXTERNAL_SERVICE_RESILIENCE = "external_service_resilience"
    SECURITY = "security"
    PROMPT_INJECTION = "prompt_injection"
    DATA_HANDLING = "data_handling"
    STATE_MEMORY = "state_memory"
    DECISION_MAKING = "decision_making"
    ERROR_RECOVERY = "error_recovery"
    PERFORMANCE_STRESS = "performance_stress"
    ENVIRONMENT_CHAOS = "environment_chaos"


class ScenarioLifecycle(str, Enum):
    GENERATED = "GENERATED"
    PREVALIDATION = "PREVALIDATION"
    REJECTED_INTERFACE = "REJECTED_INTERFACE"
    REJECTED_QUALITY = "REJECTED_QUALITY"
    VALIDATED = "VALIDATED"
    CRITIC_REJECTED = "CRITIC_REJECTED"
    CRITIC_APPROVED = "CRITIC_APPROVED"
    EXECUTABLE = "EXECUTABLE"


class FaultInjection(BaseModel):
    target_tool: str
    fault_type: str
    occurrence: int = 1
    parameters: Dict[str, Any] = Field(default_factory=dict)
    injection_mechanism: str = "mock_override"


class AssertionType(str, Enum):
    # Process & CLI
    PROCESS_EXIT_CODE = "PROCESS_EXIT_CODE"
    STDOUT_CONTAINS = "STDOUT_CONTAINS"
    STDOUT_NOT_CONTAINS = "STDOUT_NOT_CONTAINS"
    STDOUT_JSON_VALID = "STDOUT_JSON_VALID"
    STDOUT_JSON_MATCH = "STDOUT_JSON_MATCH"
    STDERR_CONTAINS = "STDERR_CONTAINS"
    STDERR_EMPTY = "STDERR_EMPTY"

    # File & Artifact
    FILE_CREATED = "FILE_CREATED"
    FILE_EXISTS = "FILE_EXISTS"
    FILE_NOT_EXISTS = "FILE_NOT_EXISTS"
    FILE_CONTENT_MATCH = "FILE_CONTENT_MATCH"

    # HTTP & API
    HTTP_STATUS = "HTTP_STATUS"
    HTTP_RESPONSE_SCHEMA = "HTTP_RESPONSE_SCHEMA"

    # Function
    FUNCTION_RETURN_MATCH = "FUNCTION_RETURN_MATCH"

    # Tool & Model
    TOOL_CALLED = "TOOL_CALLED"
    TOOL_NOT_CALLED = "TOOL_NOT_CALLED"
    TOOL_CALLED_WITH = "TOOL_CALLED_WITH"
    MAX_CALLS = "MAX_CALLS"
    LLM_CALL_COUNT = "LLM_CALL_COUNT"
    MODEL_USED = "MODEL_USED"

    # State & Policy
    STATE_EQUALS = "STATE_EQUALS"
    STATE_CHANGED = "STATE_CHANGED"
    NO_EXTERNAL_SIDE_EFFECT = "NO_EXTERNAL_SIDE_EFFECT"
    CONFIRMATION_REQUESTED = "CONFIRMATION_REQUESTED"
    SECURITY_EVENT = "SECURITY_EVENT"
    MAX_RUNTIME = "MAX_RUNTIME"

    # Semantic / Structural Output
    EMAIL_SECTION_PRESENT = "EMAIL_SECTION_PRESENT"
    OUTPUT_SEMANTIC = "OUTPUT_SEMANTIC"
    OUTPUT_NOT_CONTAINS = "OUTPUT_NOT_CONTAINS"
    WORD_COUNT_LTE = "WORD_COUNT_LTE"
    WORD_COUNT_GTE = "WORD_COUNT_GTE"
    JSON_SCHEMA_VALID = "JSON_SCHEMA_VALID"
    LIST_PRESENT = "LIST_PRESENT"
    REQUIRED_FIELD_PRESENT = "REQUIRED_FIELD_PRESENT"
    FIELD_TYPE_MATCH = "FIELD_TYPE_MATCH"
    SEMANTIC_MATCH = "SEMANTIC_MATCH"

    # Recovery & Resilience (spec §8)
    NO_UNHANDLED_EXCEPTIONS = "NO_UNHANDLED_EXCEPTIONS"
    PROCESS_TERMINATES_WITHIN_TIMEOUT = "PROCESS_TERMINATES_WITHIN_TIMEOUT"
    TRACE_CONTAINS_EXCEPTION_TYPE = "TRACE_CONTAINS_EXCEPTION_TYPE"
    DEPENDENCY_CALL_FAILED = "DEPENDENCY_CALL_FAILED"
    FALLBACK_PATH_TAKEN = "FALLBACK_PATH_TAKEN"
    RETRY_COUNT = "RETRY_COUNT"
    CIRCUIT_BREAKER_TRIGGERED = "CIRCUIT_BREAKER_TRIGGERED"


class ScenarioAssertion(BaseModel):
    assertion_type: str
    target: str = ""
    expected_value: Any = None
    description: str = ""


class Scenario(BaseModel):
    id: str
    agent_id: Optional[str] = None
    agent_version_id: Optional[str] = None
    version: int = 1

    # 1. INTENT & TARGET SUBSYSTEM
    title: str
    category: ScenarioCategory
    target_subsystem: TargetSubsystem = TargetSubsystem.FUNCTIONAL_EXECUTION
    subsystem_evaluation_criteria: List[str] = Field(default_factory=list)
    status: str = "GENERATED"
    purpose: str
    target_failure_surface: Optional[str] = None
    target_invariant: Optional[str] = None
    target_workflow_node: Optional[str] = None
    target_workflow_node_rationale: Optional[str] = None
    rationale: str = ""

    # 2. INVOCATION CONTRACT
    interface_type: str = "CHAT"
    invocation: Dict[str, Any] = Field(default_factory=dict)

    # 3. ENVIRONMENT, CONTEXT & PRECONDITIONS
    input_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    input_values: Dict[str, Any] = Field(default_factory=dict)
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    context_preconditions: Dict[str, Any] = Field(default_factory=dict)
    user_input: Optional[str] = None
    user_messages: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    required_services: List[str] = Field(default_factory=list)
    environment_conditions: Dict[str, Any] = Field(default_factory=dict)
    fault_injections: List[FaultInjection] = Field(default_factory=list)
    safety_constraints: List[str] = Field(default_factory=list)
    execution_limits: Dict[str, Any] = Field(default_factory=dict)

    # 4. EXPECTED BEHAVIOR & ASSERTIONS
    expected_behavior: Any = Field(default_factory=dict)
    expected_outcome: Dict[str, Any] = Field(default_factory=dict)
    expected_state: Dict[str, Any] = Field(default_factory=dict)
    expected_subsystem_transitions: List[str] = Field(default_factory=list)
    prohibited_actions: List[str] = Field(default_factory=list)
    assertions: List[ScenarioAssertion] = Field(default_factory=list)
    failure_conditions: List[str] = Field(default_factory=list)
    risk_level: str = "medium"

    # 5. QUALITY & PROVENANCE
    scenario_quality_score: Optional[float] = None
    fingerprint: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)

    # 6. LIFECYCLE (strict state machine)
    validation_status: str = "GENERATED"
    critic_status: str = "NOT_RUN"
    critic_passed: bool = False
    critic_notes: Optional[str] = None

    # 7. BROAD AGENT COVERAGE & BEHAVIORAL CONTRACTS
    agent_type: Optional[str] = "tool_agent"  # chatbot, tool_agent, workflow, RAG, multi_agent, coding, browser, autonomous
    interaction_mode: Optional[str] = "single_turn"  # single_turn, multi_turn, streaming, event_driven, scheduled
    input_type: Optional[str] = "text"  # text, json, file, image, audio, mixed
    statefulness: Optional[str] = "stateless"  # stateless, session, persistent
    behavioral_objective: Optional[str] = "COMPLETE_USER_GOAL"  # PREVENT_UNAUTHORIZED_DESTRUCTIVE_ACTION, COMPLETE_USER_GOAL, SELECT_CORRECT_TOOL, VALIDATE_TOOL_ARGUMENT, RECOVER_FROM_FAILURE, RESIST_PROMPT_INJECTION, PROTECT_SECRET, MAINTAIN_STATE, FOLLOW_WORKFLOW, AVOID_LOOP, PRODUCE_GROUNDED_OUTPUT, REQUEST_CLARIFICATION, REQUEST_CONFIRMATION
    required_tools: List[str] = Field(default_factory=list)
    forbidden_tools: List[str] = Field(default_factory=list)
    expected_call_sequence: List[str] = Field(default_factory=list)
    side_effect_policy: Optional[str] = "none"  # none, read_only, reversible, destructive
    confirmation_required: Optional[bool] = False
    external_services: List[str] = Field(default_factory=list)
    expected_output_constraints: Dict[str, Any] = Field(default_factory=dict)
    security_constraints: List[str] = Field(default_factory=list)
    state_invariants: List[str] = Field(default_factory=list)
    max_actions: Optional[int] = 10
    evaluation_dimensions: List[str] = Field(default_factory=list)
    severity_if_violated: Optional[str] = "HIGH"
    evidence_requirements: List[str] = Field(default_factory=list)
    execution_mode: Optional[str] = "faithful"


class ScenarioPlanItem(BaseModel):
    plan_id: str
    plan_item_id: Optional[str] = None
    target_type: str
    category: ScenarioCategory
    target: str
    evidence_id: Optional[str] = None
    priority: str = "medium"
    required_interface: str = "CLI"
    required_dependencies: List[str] = Field(default_factory=list)
    reason: str = ""
    status: str = "PLANNED"

    # Pre-assigned by NAS vector selector
    assigned_subsystem: Optional[str] = None
    assigned_workflow_node: Optional[str] = None
    assigned_capabilities: List[str] = Field(default_factory=list)
    assigned_services: List[str] = Field(default_factory=list)
    fault_target: Optional[str] = None
    fault_type: Optional[str] = None


class ScenarioPlan(BaseModel):
    plan_id: str
    agent_id: str
    agent_name: str
    total_target: int
    plan_items: List[ScenarioPlanItem] = Field(default_factory=list)
    summary: str = ""
    activated_vectors: List[str] = Field(default_factory=list)
    suppressed_vectors: List[str] = Field(default_factory=list)


class ScenarioGenerationRequest(BaseModel):
    agent_id: str
    agent_version_id: Optional[str] = None
    behavior_profile_id: Optional[str] = None
    target_count: int = 20
    category_counts: Optional[Dict[str, int]] = None
    requested_categories: List[str] = Field(default_factory=list)
    requested_focus: List[str] = Field(default_factory=list)
    target_failure_surfaces: List[str] = Field(default_factory=list)
    target_invariants: List[str] = Field(default_factory=list)
    user_instructions: Optional[str] = None
    existing_scenario_fingerprints: List[str] = Field(default_factory=list)
    generation_mode: str = "balanced"


class ScenarioFeasibility(BaseModel):
    interface_compatible: bool = True
    inputs_available: bool = True
    dependencies_available: bool = True
    sandbox_supported: bool = True
    assertions_valid: bool = True
    fault_injection_supported: bool = True
    executable: bool = True
    blockers: List[str] = Field(default_factory=list)


class ScenarioExecutionContract(BaseModel):
    scenario_id: str
    agent_id: str
    working_directory: str = "/workspace"
    command: List[str] = Field(default_factory=list)
    env_bindings: Dict[str, str] = Field(default_factory=dict)
    staged_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    network_policy_id: str = "sandbox-web-restricted"
    filesystem_policy_id: str = "sandbox-files-v1"
    timeout_seconds: float = 30.0
    execution_mode: str = "subprocess"
    model_binding: Optional[Dict[str, Any]] = None


class ScenarioGenerationRun(BaseModel):
    id: str
    agent_id: str
    agent_version_id: Optional[str] = None
    behavior_profile_id: Optional[str] = None
    requested_count: int
    planned_count: int
    generated_count: int
    ready_count: int
    rejected_count: int
    blocked_count: int
    provider: str = "gemini"
    model: Optional[str] = None
    prompt_version: str = "v2"
    status: str = "COMPLETED"
    generation_method: str = "ai"
    ai_status: str = "success"
    failure_reason: Optional[str] = None
    scenarios: List[Scenario] = Field(default_factory=list)
    created_at: str

    # Quality report (spec §20, §24)
    rejection_reasons: Dict[str, int] = Field(default_factory=dict)
    hallucination_count: int = 0
    interface_mismatch_count: int = 0
    assertion_mismatch_count: int = 0
    duplicate_count: int = 0
    quality_score_avg: float = 0.0
    capability_coverage: Dict[str, int] = Field(default_factory=dict)
    subsystem_coverage: Dict[str, int] = Field(default_factory=dict)
    workflow_node_coverage: Dict[str, int] = Field(default_factory=dict)
    risk_vector_coverage: Dict[str, int] = Field(default_factory=dict)


class StrategyCategoryTarget(BaseModel):
    category: ScenarioCategory
    target_count: int
    focus_risk: str
    rationale: str


class StrategyPlan(BaseModel):
    agent_id: str
    agent_name: str
    total_target: int
    category_distribution: List[StrategyCategoryTarget]
    summary: str


class CoverageGapReport(BaseModel):
    total_tools: int = 0
    exercised_tools: int = 0
    unexercised_tools: List[str] = Field(default_factory=list)

    interface_coverage_pct: float = 100.0
    workflow_node_coverage_pct: float = 100.0
    capability_coverage_pct: float = 100.0
    service_coverage_pct: float = 100.0
    failure_surface_coverage_pct: float = 100.0
    invariant_coverage_pct: float = 100.0
    category_coverage: Dict[str, float] = Field(default_factory=dict)

    overall_coverage_pct: float
    gaps_detected: List[str] = Field(default_factory=list)
    recommended_plan: Optional[StrategyPlan] = None
