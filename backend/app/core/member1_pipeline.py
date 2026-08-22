"""
Member 1 Pipeline Interface.
Exposes the clean public interfaces for intake analysis, capability extraction,
scenario generation, scenario criticism, scenario validation, and coverage calculation.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional

from app.models.agent_test_spec import AgentTestSpecification, ScenarioDefinition, CoverageReport
from app.core.intake.semantic_analyzer import analyze_agent as _analyze_agent
from app.core.scenarios.generator import generate_scenarios as _generate_scenarios
from app.core.scenarios.critic import critique_scenarios as _critique_scenarios
from app.core.scenarios.validator import validate_scenarios as _validate_scenarios
from app.core.scenarios.coverage import calculate_coverage as _calculate_coverage

async def analyze_agent(agent_path: str, api_key: Optional[str] = None) -> AgentTestSpecification:
    """
    Analyzes an agent supplied as source files/configuration, parses imports/tools, 
    extracts semantic capabilities, and returns an AgentTestSpecification.
    """
    return await _analyze_agent(agent_path, api_key=api_key)

async def generate_scenarios(
    spec: AgentTestSpecification,
    count: int = 12,
    api_key: Optional[str] = None,
    run_critic: bool = True
) -> List[ScenarioDefinition]:
    """
    Generates a targeted suite of ScenarioDefinition objects covering capabilities and risks,
    optionally running them through the Scenario Critic.
    """
    scenarios = await _generate_scenarios(spec, count=count, api_key=api_key)
    if run_critic:
        scenarios = await _critique_scenarios(scenarios, spec, api_key=api_key)
    return scenarios

def validate_scenarios(
    scenarios: List[ScenarioDefinition],
    spec: AgentTestSpecification
) -> Dict[str, Any]:
    """
    Validates scenario definitions against agent capability specs, parameter structure,
    and schema formats.
    """
    return _validate_scenarios(scenarios, spec)

def calculate_coverage(
    spec: AgentTestSpecification,
    scenarios: List[ScenarioDefinition]
) -> CoverageReport:
    """
    Calculates capability/scenario coverage reports identifying unexercised paths or tools.
    """
    return _calculate_coverage(spec, scenarios)
