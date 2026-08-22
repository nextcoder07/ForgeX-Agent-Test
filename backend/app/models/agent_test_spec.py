"""
Stable contract models for Agent Intelligence & Scenario Intelligence.
Includes AgentTestSpecification, Capability, ScenarioDefinition, and CoverageReport.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.agent import ToolDefinition, DependencyDefinition

class Capability(BaseModel):
    """
    Extracted capability block representing a meaningful function the agent can execute.
    """
    capability_id: str = Field(..., description="Unique code identifier, e.g., CUSTOMER_LOOKUP")
    name: str = Field(..., description="Human-friendly capability name")
    description: str = Field(..., description="Brief summary of what the capability accomplishes")
    related_tools: List[str] = Field(default_factory=list, description="List of tool names supporting this capability")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Parameter schema or input structure")
    outputs: List[str] = Field(default_factory=list, description="Expected outputs or actions")
    risks: List[str] = Field(default_factory=list, description="Identified risks associated with this capability")


class AgentTestSpecification(BaseModel):
    """
    Stable representation of an analyzed agent, containing all info needed for scenario planning.
    """
    agent_id: str = Field(..., description="Unique ID of the agent record")
    name: str = Field(..., description="Clean display name of the agent")
    purpose: str = Field(..., description="Semantic purpose statement extracted from files/README")
    instructions_summary: str = Field(..., description="Summarized developer/system instructions")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Global user inputs or command interfaces")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="Global response structure or output interfaces")
    tools: List[ToolDefinition] = Field(default_factory=list, description="Discovered tool signatures")
    dependencies: List[DependencyDefinition] = Field(default_factory=list, description="Detected dependencies")
    capabilities: List[Capability] = Field(default_factory=list, description="Extracted semantic capabilities")
    risks: List[str] = Field(default_factory=list, description="High-level potential risks")
    workflow_summary: str = Field(..., description="Summary of how the agent coordinates goals and tools")


class ScenarioDefinition(BaseModel):
    """
    Stable scenario specification format consumed by the Sandbox Executor (Member 2).
    """
    scenario_id: str = Field(..., description="Unique scenario ID, e.g., SC-EDG-01")
    capability_id: str = Field(..., description="Associated capability ID")
    category: str = Field(..., description="Category, e.g. NORMAL, EDGE_CASE, BOUNDARY, INVALID_INPUT, etc.")
    description: str = Field(..., description="Test scenario description")
    input: Dict[str, Any] = Field(default_factory=dict, description="Inputs to feed to the agent")
    expected_behavior: str = Field(..., description="Expected behavior/assertions describing success")
    risk_level: str = Field("low", description="Risk level, e.g. LOW, MEDIUM, HIGH, CRITICAL")
    failure_mode_to_test: Optional[str] = Field(None, description="Fault/failure mode target, e.g. TIMEOUT, HTTP_500")
    required_tools: List[str] = Field(default_factory=list, description="List of tools needed during execution")
    environment_requirements: Optional[Dict[str, Any]] = Field(None, description="External sandbox environment dependencies")
    critic_status: str = Field("PASS", description="Status from Scenario Critic: PASS, MODIFY, REJECT")
    critic_feedback: Optional[str] = Field(None, description="Explanation of critique rating")
    critic_confidence: float = Field(1.0, description="Confidence of the critic score (0.0 to 1.0)")


class CoverageReport(BaseModel):
    """
    Quality report mapping capability testing rate, tool utilization, and risk coverage.
    """
    capability_coverage: float = Field(..., description="Percentage of capabilities covered by test cases")
    category_coverage: float = Field(..., description="Percentage of scenario categories covered")
    tool_coverage: float = Field(..., description="Percentage of tools exercised by test cases")
    risk_coverage: float = Field(..., description="Percentage of agent risks tested")
    failure_mode_coverage: float = Field(..., description="Percentage of fault/failure modes covered")
    untested_capabilities: List[str] = Field(default_factory=list)
    untested_tools: List[str] = Field(default_factory=list)
    untested_risks: List[str] = Field(default_factory=list)
    untested_failure_modes: List[str] = Field(default_factory=list)
    missing_categories: List[str] = Field(default_factory=list)
    scenarios_per_capability: Dict[str, int] = Field(default_factory=dict)
    scenarios_per_category: Dict[str, int] = Field(default_factory=dict)
