"""
Runtime Ephemeral Execution, Tool Call, State Change, and Security Event Models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionLifecycleState(str, Enum):
    SCENARIO_SELECTED = "SCENARIO_SELECTED"
    PREFLIGHT = "PREFLIGHT"
    VARIABLE_RESOLUTION = "VARIABLE_RESOLUTION"
    DEPENDENCY_RESOLUTION = "DEPENDENCY_RESOLUTION"
    SANDBOX_BUILDING = "SANDBOX_BUILDING"
    SANDBOX_READY = "SANDBOX_READY"
    EXECUTION_STARTING = "EXECUTION_STARTING"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    FINALIZING = "FINALIZING"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EVIDENCE_SEALED = "EVIDENCE_SEALED"
    READY_FOR_EVALUATION = "READY_FOR_EVALUATION"


class ExecutionFailureState(str, Enum):
    BLOCKED = "BLOCKED"
    FAILED_SETUP = "FAILED_SETUP"
    FAILED_EXECUTION = "FAILED_EXECUTION"
    TIMEOUT = "TIMEOUT"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CRASHED = "CRASHED"
    CANCELLED = "CANCELLED"
    INCONCLUSIVE = "INCONCLUSIVE"


class VariableSource(str, Enum):
    SCENARIO = "SCENARIO"
    USER = "USER"
    PLATFORM = "PLATFORM"
    SAFE_DEFAULT = "SAFE_DEFAULT"
    MISSING = "MISSING"


class VariableBinding(BaseModel):
    name: str
    type: str = "string"  # "string", "number", "boolean", "secret", "json"
    required: bool = True
    source: VariableSource = VariableSource.USER
    value_status: str = "BOUND"  # "BOUND", "UNBOUND", "MISSING", "DEFAULT_APPLIED"
    value: Optional[Any] = None
    masked_value: Optional[str] = None
    credential_reference: Optional[str] = None


class ExecutionPreflight(BaseModel):
    id: str
    execution_run_id: str
    scenario_id: str
    agent_id: str
    agent_version_id: str
    interface_status: str = "READY"
    runtime_status: str = "READY"
    dependency_status: str = "READY"
    credential_status: str = "READY"
    sandbox_status: str = "READY"
    policy_status: str = "READY"
    mode_status: str = "READY"
    overall_status: str = "READY"  # "READY" or "BLOCKED"
    blockers: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_variables: List[VariableBinding] = Field(default_factory=list)
    created_at: str = ""


class ToolCallRecord(BaseModel):
    id: str
    sequence: int
    tool_name: str
    canonical_capability: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Any = Field(default_factory=dict)
    latency_ms: float = 0.0
    status: str = "SUCCESS"  # "SUCCESS", "TIMEOUT", "INJECTED_ERROR", "BLOCKED_POLICY"
    routing_decision: str = "SIMULATED_SANDBOX"  # "SIMULATED_SANDBOX", "REDIRECTED", "BLOCKED", "ALLOW"
    policy_reason: Optional[str] = None
    actual_side_effect_occurred: bool = False
    injected_fault: Optional[str] = None


class ActionAttemptRecord(BaseModel):
    id: str
    sequence: int
    action_type: str  # "TOOL_CALL", "FILE_WRITE", "FILE_DELETE", "HTTP_REQUEST", "PROCESS_SPAWN"
    target: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    policy_decision: str = "ALLOW"  # "ALLOW", "BLOCK", "REDIRECT", "MOCK"
    policy_reason: Optional[str] = None
    actual_side_effect: bool = False
    state_before: Optional[Dict[str, Any]] = None
    state_after: Optional[Dict[str, Any]] = None
    timestamp: str = ""


class ExecutionAction(BaseModel):
    """4-Layer Action Evidence Record: ATTEMPT -> POLICY -> EXECUTION -> SIDE_EFFECT."""
    id: str
    action_id: Optional[str] = None
    execution_session_id: str
    sequence: int
    action_type: str  # "TOOL_CALL", "LLM_CALL", "FILE_OPERATION", "NETWORK_REQUEST", "PROCESS_SPAWN"
    target: str
    
    # Nested 4-Layer Structures
    action_attempt: Dict[str, Any] = Field(default_factory=dict)  # {"payload": {...}}
    policy_decision: Dict[str, Any] = Field(default_factory=dict)  # {"decision": "ALLOW"|"BLOCK"|"REDIRECT", "reason": "..."}
    execution_result: Dict[str, Any] = Field(default_factory=dict)  # {"status": "SUCCESS"|"BLOCKED_POLICY"|"ERROR", "executed": bool}
    side_effect: Dict[str, Any] = Field(default_factory=dict)  # {"detected": bool, "details": {...}}

    # Flat properties for backward compatibility
    attempt_payload: Dict[str, Any] = Field(default_factory=dict)
    policy_reason: Optional[str] = None
    executed: bool = True
    result_status: str = "SUCCESS"
    side_effect_detected: bool = False
    side_effect_details: Optional[Dict[str, Any]] = None
    timestamp: str = ""


class PreExecutionSnapshot(BaseModel):
    filesystem_state: Dict[str, str] = Field(default_factory=dict)
    environment_metadata: Dict[str, str] = Field(default_factory=dict)
    database_fixture_state: Dict[str, Any] = Field(default_factory=dict)
    network_policy: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


class PostExecutionSnapshot(BaseModel):
    filesystem_state: Dict[str, str] = Field(default_factory=dict)
    modified_files: List[str] = Field(default_factory=list)
    database_state: Dict[str, Any] = Field(default_factory=dict)
    state_diffs: List[Dict[str, Any]] = Field(default_factory=list)
    process_exit_code: Optional[int] = 0
    runtime_errors: List[str] = Field(default_factory=list)
    network_activity_summary: Dict[str, Any] = Field(default_factory=dict)
    execution_duration_ms: float = 0.0
    timestamp: str = ""


class ObservationSummary(BaseModel):
    """Compact deterministic summary derived at the end of execution for evaluation. ZERO pass/fail scores."""
    action_count: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    network_requests: int = 0
    file_reads: int = 0
    file_writes: int = 0
    database_operations: int = 0
    retries: int = 0
    timeouts: int = 0
    errors: int = 0
    blocked_actions: int = 0
    policy_blocks: int = 0
    network_blocks: int = 0
    unexpected_tool_calls: int = 0
    state_changes: int = 0
    external_side_effects: int = 0
    max_retry_streak: int = 0
    execution_duration_ms: float = 0.0
    exit_code: int = 0


class EvidencePackage(BaseModel):
    """Sealed evidence container passed to Evaluation."""
    session_id: str
    scenario_id: str
    agent_version_id: str
    observation_summary: ObservationSummary
    evidence_references: List[str] = Field(default_factory=list)
    trajectory_hash: str
    sealing_timestamp: str


class StateChange(BaseModel):
    resource_type: str  # "ORDER", "CUSTOMER", "INVENTORY", "SESSION", "FILE"
    resource_id: str
    field: str
    before_value: Any = None
    after_value: Any = None
    actor: str = "agent"
    event_id: Optional[str] = None


class SecurityEvent(BaseModel):
    event_type: str  # "PROMPT_INJECTION_DETECTED", "UNAUTHORIZED_PAYOUT", "DESTRUCTIVE_ACTION_NO_CONFIRM", "PII_LEAK"
    severity: str  # "critical", "high", "medium", "low"
    target: str
    action_taken: str  # "BLOCKED", "LOGGED", "FLAGGED"
    evidence: str


class TraceEvent(BaseModel):
    timestamp: str
    role: str  # "user", "agent_thought", "agent_message", "tool_call", "tool_result", "security_alert", "fault_injected"
    content: str
    tool_call: Optional[ToolCallRecord] = None


class ExecutionTrace(BaseModel):
    id: str
    scenario_id: str
    agent_id: str
    agent_version: str
    events: List[TraceEvent] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    state_changes: List[StateChange] = Field(default_factory=list)
    security_events: List[SecurityEvent] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    is_counterfactual: bool = False
    counterfactual_of: Optional[str] = None
    observation_summary: Optional[ObservationSummary] = None
    trajectory_hash: Optional[str] = None


class SandboxInstance(BaseModel):
    id: str
    agent_id: str
    scenario_id: str
    status: str = "INITIALIZED"  # "INITIALIZED", "BUILDING", "RUNNING", "COMPLETED", "CLEANED_UP", "FAILED_SETUP"
    virtual_fs: Dict[str, str] = Field(default_factory=dict)
    mock_db: Dict[str, Any] = Field(default_factory=dict)
    redirected_emails: List[Dict[str, Any]] = Field(default_factory=list)
    active_policy_gates: List[str] = Field(default_factory=list)
    created_at: str


class ExecutionRun(BaseModel):
    """User-launched batch execution run."""
    id: str
    agent_id: str
    agent_version_id: Optional[str] = None
    scenario_ids: List[str] = Field(default_factory=list)
    execution_mode: str = "faithful"
    status: str = "SCENARIO_SELECTED"  # Uses ExecutionLifecycleState or ExecutionFailureState
    failure_reason: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None
    requested_count: int = 0
    ready_count: int = 0
    completed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0


class ExecutionSession(BaseModel):
    """One scenario execution session."""
    id: str
    execution_run_id: str
    agent_version_id: str
    scenario_id: str
    status: str = "SCENARIO_SELECTED"  # Uses ExecutionLifecycleState or ExecutionFailureState
    failure_state: Optional[str] = None  # Uses ExecutionFailureState if failed
    started_at: str
    finished_at: Optional[str] = None
    exit_code: int = 0
    error_code: Optional[str] = None
    trajectory_hash: Optional[str] = None
    preflight: Optional[ExecutionPreflight] = None
    pre_snapshot: Optional[PreExecutionSnapshot] = None
    post_snapshot: Optional[PostExecutionSnapshot] = None
    observation_summary: Optional[ObservationSummary] = None
    evidence_package: Optional[EvidencePackage] = None
    actions: List[ExecutionAction] = Field(default_factory=list)


class ExecutionEventType(str, Enum):
    # Process & CLI
    PROCESS_STARTED = "PROCESS_STARTED"
    PROCESS_EXITED = "PROCESS_EXITED"
    CLI_ARGUMENTS = "CLI_ARGUMENTS"
    STDIN_INPUT = "STDIN_INPUT"
    STDOUT_CHUNK = "STDOUT_CHUNK"
    STDERR_CHUNK = "STDERR_CHUNK"
    
    # File & I/O
    FILE_CREATED = "FILE_CREATED"
    FILE_READ = "FILE_READ"
    FILE_WRITTEN = "FILE_WRITTEN"
    FILE_DELETED = "FILE_DELETED"
    
    # Network & Model
    NETWORK_REQUEST = "NETWORK_REQUEST"
    NETWORK_RESPONSE = "NETWORK_RESPONSE"
    LLM_CALL = "LLM_CALL"
    LLM_RESPONSE = "LLM_RESPONSE"
    
    # Tool & Agent Actions
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESPONSE = "TOOL_RESPONSE"
    TOOL_INVOCATION = "TOOL_INVOCATION"
    USER_INPUT = "USER_INPUT"
    AGENT_ACTION = "AGENT_ACTION"
    OBSERVATION = "OBSERVATION"
    MEMORY_ACCESS = "MEMORY_ACCESS"
    STATE_CHANGE = "STATE_CHANGE"
    ERROR = "ERROR"
    FINAL_RESPONSE = "FINAL_RESPONSE"
    
    # Observable Sandbox Lifecycle & Build Steps
    SANDBOX_BUILD_STARTED = "SANDBOX_BUILD_STARTED"
    RUNTIME_PREPARED = "RUNTIME_PREPARED"
    DEPENDENCIES_INSTALL_STARTED = "DEPENDENCIES_INSTALL_STARTED"
    DEPENDENCIES_INSTALL_COMPLETED = "DEPENDENCIES_INSTALL_COMPLETED"
    DEPENDENCY_INSTALL_FAILED = "DEPENDENCY_INSTALL_FAILED"
    FILES_MOUNTED = "FILES_MOUNTED"
    ENV_BOUND = "ENV_BOUND"
    NETWORK_POLICY_APPLIED = "NETWORK_POLICY_APPLIED"
    TOOL_GATEWAY_READY = "TOOL_GATEWAY_READY"
    POLICY_READY = "POLICY_READY"
    SANDBOX_STARTED = "SANDBOX_STARTED"
    SANDBOX_READY = "SANDBOX_READY"
    SANDBOX_TERMINATED = "SANDBOX_TERMINATED"
    
    # 4-Layer Action Evidence Events
    ACTION_ATTEMPT = "ACTION_ATTEMPT"
    POLICY_DECISION = "POLICY_DECISION"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    SIDE_EFFECT_DETECTED = "SIDE_EFFECT_DETECTED"
    
    # Snapshots & Sealing
    PRE_EXECUTION_SNAPSHOT = "PRE_EXECUTION_SNAPSHOT"
    POST_EXECUTION_SNAPSHOT = "POST_EXECUTION_SNAPSHOT"
    EXECUTION_FINALIZED = "EXECUTION_FINALIZED"
    EVIDENCE_SEALED = "EVIDENCE_SEALED"


class ExecutionStep(BaseModel):
    id: str
    execution_session_id: str
    step_number: int
    event_type: str  # Can be ExecutionEventType or custom string
    actor: str = "agent"  # "user", "agent", "tool", "environment", "evaluator", "system", "sandbox"
    parent_event_id: Optional[str] = None  # Causal lineage link
    payload: Dict[str, Any] = Field(default_factory=dict)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ExecutionMetrics(BaseModel):
    id: str
    execution_session_id: str
    steps_count: int = 0
    tool_calls_count: int = 0
    failed_tools: int = 0
    tokens_used: int = 0
    latency_ms: float = 0.0
    cost: float = 0.0
    created_at: Optional[str] = None


class ExecutionArtifact(BaseModel):
    id: str
    execution_session_id: str
    artifact_type: str  # "LLM_RESPONSE", "HTML", "SCREENSHOT", "PAYLOAD_JSON", "LOGS"
    content_hash: str
    storage_path: str
    mime_type: str = "application/json"
    size_bytes: int = 0
    created_at: str = ""


class ExecutionJob(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    status: str = "pending"  # "pending", "running", "completed", "failed"
    total_scenarios: int = 0
    completed_scenarios: int = 0
    scenario_ids: List[str] = Field(default_factory=list)
    execution_mode: Optional[str] = "faithful"
    original_model: Optional[str] = None
    executed_model: Optional[str] = None
    model_substitution: Optional[bool] = False
    confidence: Optional[str] = "HIGH"
    created_at: str
    finished_at: Optional[str] = None


class RuleEvaluationEvidence(BaseModel):
    id: str
    rule_name: str
    rule_type: str  # "STATE_VALIDATOR", "ACTION_ORDER_VALIDATOR", "TOOL_PARAM_VALIDATOR", "GOAL_ASSERTION", "SAFETY_ASSERTION"
    expected: Any
    actual: Any
    passed: bool
    failure_reason: Optional[str] = None


class BenchmarkRecord(BaseModel):
    id: str
    agent_version_id: Optional[str] = None
    scenario_id: Optional[str] = None
    execution_session_id: str
    trajectory: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation: Dict[str, Any] = Field(default_factory=dict)
    human_feedback: Optional[Dict[str, Any]] = None
    quality_score: float = 0.0
    created_at: str


