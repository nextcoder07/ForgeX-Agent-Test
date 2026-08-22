"""
Runtime Ephemeral Execution, Tool Call, State Change, and Security Event Models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    id: str
    sequence: int
    tool_name: str
    canonical_capability: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Any = Field(default_factory=dict)
    latency_ms: float = 0.0
    status: str = "SUCCESS"  # "SUCCESS", "TIMEOUT", "INJECTED_ERROR", "BLOCKED_POLICY"
    routing_decision: str = "SIMULATED_SANDBOX"  # "SIMULATED_SANDBOX", "REDIRECTED", "BLOCKED"
    injected_fault: Optional[str] = None



class StateChange(BaseModel):
    resource_type: str  # "ORDER", "CUSTOMER", "INVENTORY", "SESSION"
    resource_id: str
    field: str
    before_value: Any = None
    after_value: Any = None


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


class SandboxInstance(BaseModel):
    id: str
    agent_id: str
    scenario_id: str
    status: str = "INITIALIZED"  # "INITIALIZED", "RUNNING", "COMPLETED", "CLEANED_UP"
    virtual_fs: Dict[str, str] = Field(default_factory=dict)
    mock_db: Dict[str, Any] = Field(default_factory=dict)
    redirected_emails: List[Dict[str, Any]] = Field(default_factory=list)
    active_policy_gates: List[str] = Field(default_factory=list)
    created_at: str


class ExecutionJob(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    status: str = "pending"  # "pending", "running", "completed", "failed"
    total_scenarios: int = 0
    completed_scenarios: int = 0
    scenario_ids: List[str] = Field(default_factory=list)
    created_at: str
    finished_at: Optional[str] = None


class ExecutionSession(BaseModel):
    id: str
    evaluation_run_id: Optional[str] = None
    agent_version_id: Optional[str] = None
    scenario_id: Optional[str] = None
    sandbox_session_id: Optional[str] = None
    status: str = "active"  # "active", "completed", "failed"
    started_at: str
    completed_at: Optional[str] = None


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
    
    # Sandbox Lifecycle
    SANDBOX_STARTED = "SANDBOX_STARTED"
    SANDBOX_TERMINATED = "SANDBOX_TERMINATED"


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

