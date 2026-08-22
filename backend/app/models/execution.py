"""
Runtime Ephemeral Execution, Tool Call, State Change, and Security Event Models.
"""

from __future__ import annotations

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

