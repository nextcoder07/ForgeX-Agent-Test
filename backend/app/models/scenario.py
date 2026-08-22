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


class ScenarioAssertion(BaseModel):
    assertion_type: str  # "TOOL_NOT_CALLED", "TOOL_CALLED_WITH", "MAX_CALLS", "STATE_EQUALS", "CONFIRMATION_REQUESTED"
    target: str
    expected_value: Any = None
    description: str = ""


class Scenario(BaseModel):
    id: str
    agent_id: Optional[str] = None
    version: int = 1
    category: ScenarioCategory
    title: str
    purpose: str
    user_input: Optional[str] = None
    user_messages: List[str] = Field(default_factory=list)
    initial_state: Dict[str, Any] = Field(default_factory=dict)
    required_capabilities: List[str] = Field(default_factory=list)
    required_services: List[str] = Field(default_factory=list)
    fault_injections: List[FaultInjection] = Field(default_factory=list)
    environment_conditions: Dict[str, Any] = Field(default_factory=dict)
    expected_behavior: Optional[str] = None
    expected_state: Dict[str, Any] = Field(default_factory=dict)
    assertions: List[ScenarioAssertion] = Field(default_factory=list)
    safety_constraints: List[str] = Field(default_factory=list)
    execution_limits: Dict[str, Any] = Field(default_factory=dict) # e.g. {"max_turns": 5, "timeout_seconds": 30}
    critic_passed: bool = True
    critic_notes: Optional[str] = None
    validation_status: str = "VALIDATED"  # "VALIDATED", "BLOCKED_DEPENDENCY", "REJECTED_CRITIC"
    rationale: str = ""  # "WHY THIS TEST EXISTS"


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
    total_tools: int
    exercised_tools: int
    unexercised_tools: List[str] = Field(default_factory=list)
    category_coverage: Dict[str, float] = Field(default_factory=dict)
    overall_coverage_pct: float
    gaps_detected: List[str] = Field(default_factory=list)
    recommended_plan: Optional[StrategyPlan] = None
