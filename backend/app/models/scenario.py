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


class FaultInjection(BaseModel):
    target_tool: str
    fault_type: str  # "timeout", "http_500", "empty_response", "schema_violation", "contradictory_payload"
    occurrence: int = 1
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AssertionType(str, Enum):
    # Process & CLI Assertions
    PROCESS_EXIT_CODE = "PROCESS_EXIT_CODE"
    STDOUT_CONTAINS = "STDOUT_CONTAINS"
    STDOUT_NOT_CONTAINS = "STDOUT_NOT_CONTAINS"
    STDOUT_JSON_VALID = "STDOUT_JSON_VALID"
    STDOUT_JSON_MATCH = "STDOUT_JSON_MATCH"
    STDERR_CONTAINS = "STDERR_CONTAINS"
    STDERR_EMPTY = "STDERR_EMPTY"
    
    # File & Artifact Assertions
    FILE_CREATED = "FILE_CREATED"
    FILE_EXISTS = "FILE_EXISTS"
    FILE_NOT_EXISTS = "FILE_NOT_EXISTS"
    FILE_CONTENT_MATCH = "FILE_CONTENT_MATCH"
    
    # HTTP & API Assertions
    HTTP_STATUS = "HTTP_STATUS"
    HTTP_RESPONSE_SCHEMA = "HTTP_RESPONSE_SCHEMA"
    
    # Function & Direct Invocation Assertions
    FUNCTION_RETURN_MATCH = "FUNCTION_RETURN_MATCH"
    
    # Tool & Model Execution Assertions
    TOOL_CALLED = "TOOL_CALLED"
    TOOL_NOT_CALLED = "TOOL_NOT_CALLED"
    TOOL_CALLED_WITH = "TOOL_CALLED_WITH"
    MAX_CALLS = "MAX_CALLS"
    LLM_CALL_COUNT = "LLM_CALL_COUNT"
    MODEL_USED = "MODEL_USED"
    
    # State & Policy Assertions
    STATE_EQUALS = "STATE_EQUALS"
    STATE_CHANGED = "STATE_CHANGED"
    NO_EXTERNAL_SIDE_EFFECT = "NO_EXTERNAL_SIDE_EFFECT"
    CONFIRMATION_REQUESTED = "CONFIRMATION_REQUESTED"
    SECURITY_EVENT = "SECURITY_EVENT"
    MAX_RUNTIME = "MAX_RUNTIME"


class ScenarioAssertion(BaseModel):
    assertion_type: str  # Can be AssertionType or custom string
    target: str = ""
    expected_value: Any = None
    description: str = ""


class Scenario(BaseModel):
    id: str
    agent_id: Optional[str] = None
    agent_version_id: Optional[str] = None
    version: int = 1
    
    # 1. INTENT
    title: str
    category: ScenarioCategory
    status: str = "DRAFT"  # "DRAFT", "GENERATED", "VALIDATING", "REJECTED", "BLOCKED", "READY"
    purpose: str
    target_failure_surface: Optional[str] = None
    target_invariant: Optional[str] = None
    target_workflow_node: Optional[str] = None
    rationale: str = ""  # "WHY THIS TEST EXISTS"
    
    # 2. INVOCATION CONTRACT
    interface_type: str = "CHAT"  # "CLI", "HTTP", "FUNCTION", "CHAT", "EVENT", "BATCH"
    invocation: Dict[str, Any] = Field(default_factory=dict)
    # Examples:
    # CLI: {"type": "command", "executable": "python", "arguments": ["agent.py", "--resume", "..."], "command": "..."}
    # HTTP: {"type": "http", "method": "POST", "endpoint": "/api", "headers": {}, "body": {}}
    # FUNCTION: {"type": "function", "module": "agent", "function": "run", "arguments": {}}
    # CHAT: {"type": "conversation", "messages": ["..."]}
    
    # 3. ENVIRONMENT & INPUTS
    input_artifacts: List[Dict[str, Any]] = Field(default_factory=list)  # [{"path": "...", "content": "...", "mime_type": "..."}]
    input_values: Dict[str, Any] = Field(default_factory=dict)
    initial_state: Dict[str, Any] = Field(default_factory=dict)
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
    prohibited_actions: List[str] = Field(default_factory=list)
    assertions: List[ScenarioAssertion] = Field(default_factory=list)
    
    # 5. PROVENANCE & LIFECYCLE
    fingerprint: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    # e.g. {"generated_by": "gemini", "model": "gemini-2.5-flash", "prompt_version": "v2", "scenario_plan_id": "PLAN-01"}
    
    critic_passed: bool = True
    critic_notes: Optional[str] = None
    critic_status: str = "PENDING"  # "PASS", "MODIFY", "REJECT", "PENDING"
    validation_status: str = "VALIDATED"  # "VALIDATED", "BLOCKED_DEPENDENCY", "REJECTED_CRITIC", "UNREVIEWED"


class ScenarioPlanItem(BaseModel):
    plan_id: str
    target_type: str  # "failure_surface", "invariant", "workflow_node", "category", "normal_path"
    category: ScenarioCategory
    target: str
    evidence_id: Optional[str] = None
    priority: str = "medium"  # "critical", "high", "medium", "low"
    required_interface: str = "CLI"
    required_dependencies: List[str] = Field(default_factory=list)
    reason: str = ""
    status: str = "PLANNED"  # "PLANNED", "GENERATED", "SKIPPED"


class ScenarioPlan(BaseModel):
    plan_id: str
    agent_id: str
    agent_name: str
    total_target: int
    plan_items: List[ScenarioPlanItem] = Field(default_factory=list)
    summary: str = ""


class ScenarioGenerationRequest(BaseModel):
    agent_id: str
    agent_version_id: Optional[str] = None
    behavior_profile_id: Optional[str] = None
    target_count: int = 20
    requested_categories: List[str] = Field(default_factory=list)
    requested_focus: List[str] = Field(default_factory=list)
    target_failure_surfaces: List[str] = Field(default_factory=list)
    target_invariants: List[str] = Field(default_factory=list)
    user_instructions: Optional[str] = None
    existing_scenario_fingerprints: List[str] = Field(default_factory=list)
    generation_mode: str = "balanced"  # "balanced", "adversarial_heavy", "security_heavy", "smoke"


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
    staged_artifacts: List[Dict[str, Any]] = Field(default_factory=list)  # [{"path": "...", "content": "..."}]
    network_policy_id: str = "sandbox-web-restricted"
    filesystem_policy_id: str = "sandbox-files-v1"
    timeout_seconds: float = 30.0
    execution_mode: str = "subprocess"  # "subprocess", "docker", "simulation"
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
    status: str = "COMPLETED"  # "COMPLETED", "PARTIAL", "FAILED"
    generation_method: str = "ai"  # "ai", "deterministic", "hybrid"
    ai_status: str = "success"  # "success", "failed", "quota_exhausted", "unavailable"
    failure_reason: Optional[str] = None
    scenarios: List[Scenario] = Field(default_factory=list)
    created_at: str


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
    
    # Multi-dimensional behavior coverage
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
