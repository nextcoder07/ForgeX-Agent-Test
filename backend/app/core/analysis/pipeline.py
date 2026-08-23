"""
Stage 2 analysis pipeline: agent/tool/risk analysis, mock provisioning, scenario generation.
"""
from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from app.models.agent import AgentRecord, ToolDefinition
from app.models.scenario import Scenario
from app.core.llm.base import LLMProvider
from app.core.analysis.agent_analyzer import AgentAnalyzer, AgentAnalysisResult
from app.core.analysis.tool_analyzer import ToolAnalyzer, ToolAnalysisResult
from app.core.analysis.risk_analyzer import RiskAnalyzer, RiskAnalysisResult
from app.core.analysis.mock_tool_factory import MockToolFactory
from app.core.scenarios.strategy_planner import build_test_strategy
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent


class Stage2PipelineResult(BaseModel):
    agent_analysis: AgentAnalysisResult
    tool_analysis: ToolAnalysisResult
    provisioned_tools: List[ToolDefinition] = Field(default_factory=list)
    risk_analysis: RiskAnalysisResult
    scenarios: List[Scenario] = Field(default_factory=list)


def provision_missing_mocks(agent: AgentRecord, tool_analysis: ToolAnalysisResult) -> List[ToolDefinition]:
    existing = {t.name.lower() for t in agent.tools}
    provisioned: List[ToolDefinition] = []
    for item in tool_analysis.required_tools:
        if not item.mock_required:
            continue
        mock_tool = MockToolFactory.provision_mock_tool(item.name, item.purpose, item.risk_level)
        if mock_tool.name.lower() in existing:
            continue
        agent.tools.append(mock_tool)
        existing.add(mock_tool.name.lower())
        provisioned.append(mock_tool)
    return provisioned


async def run_stage2_pipeline(
    agent: AgentRecord,
    llm: LLMProvider,
    *,
    persist_store: Any = None,
    target_count: int = 16,
) -> Stage2PipelineResult:
    agent_analysis = await AgentAnalyzer(llm).analyze_agent(agent)
    tool_analysis = await ToolAnalyzer(llm).analyze_tools(agent)
    provisioned = provision_missing_mocks(agent, tool_analysis)

    required_names = [item.name for item in tool_analysis.required_tools]
    risk_analysis = await RiskAnalyzer(llm).analyze_risks(agent, required_tools=required_names)

    strategy = build_test_strategy(agent, desired_count=target_count)
    scenarios = await generate_scenarios_for_agent(
        agent,
        strategy,
        llm,
        agent_analysis=agent_analysis,
        tool_analysis=tool_analysis,
        risk_analysis=risk_analysis,
    )

    if persist_store is not None:
        persist_store.save_agent(agent)
        for scenario in scenarios:
            scenario.agent_id = agent.id
            persist_store.save_scenario(scenario)

    return Stage2PipelineResult(
        agent_analysis=agent_analysis,
        tool_analysis=tool_analysis,
        provisioned_tools=provisioned,
        risk_analysis=risk_analysis,
        scenarios=scenarios,
    )


def pipeline_result_as_dicts(result: Stage2PipelineResult) -> Dict[str, Any]:
    return {
        "agent_analysis": result.agent_analysis.model_dump(),
        "tool_analysis": result.tool_analysis.model_dump(),
        "provisioned_tools": [t.model_dump() for t in result.provisioned_tools],
        "risk_analysis": result.risk_analysis.model_dump(),
        "scenarios": result.scenarios,
    }
