"""
Regression test suite for Scenario Coverage Gap Engine.
Verifies strict isolation between user tools, workflow nodes, framework constructs, capabilities, and external services.
"""

import pytest
from app.models.agent import AgentRecord, ToolDefinition, DependencyDefinition
from app.models.scenario import Scenario, ScenarioCategory
from app.core.scenarios.coverage_engine import compute_coverage_gaps


def test_agent_with_zero_tools_and_workflow_nodes():
    """Rule 1: Zero-tool agent must report 0/0 tools, unexercised_tools=[], and workflow coverage calculated independently."""
    agent = AgentRecord(
        id="agent-crew-1",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Email Crew Agent",
        description="Autonomous email crew agent",
        status="active",
        tools=[],
        agent_spec={
            "tools": [],
            "workflow": [
                {"id": "build_email_crew", "name": "build_email_crew"},
                {"id": "main", "name": "main"},
                {"id": "analyze_task", "name": "analyze_task"},
                {"id": "write_task", "name": "write_task"},
            ],
            "evidence_packet": {
                "framework_constructs": [
                    {"name": "Email Context Analyst", "role": "Email Context Analyst", "type": "crewai_agent"},
                    {"name": "Professional Email Writer", "role": "Professional Email Writer", "type": "crewai_agent"},
                    {"name": "crew", "role": "crew", "type": "crewai_crew"},
                ]
            }
        }
    )

    report = compute_coverage_gaps(agent, [])

    assert report.total_tools == 0
    assert report.exercised_tools == 0
    assert report.unexercised_tools == []
    assert not any("tool(s) never exercised" in gap for gap in report.gaps_detected)
    assert report.workflow_node_coverage_pct == 0.0


def test_crewai_framework_constructs_never_appear_in_tools():
    """Rule 2: CrewAI agents, tasks, and crews must NEVER be included in tools or unexercised_tools."""
    agent = AgentRecord(
        id="agent-crew-2",
        owner_id="user-1",
        workspace_id="ws-1",
        name="CrewAI Writer",
        description="CrewAI Writer agent",
        status="active",
        tools=[],
        agent_spec={
            "tools": [],
            "workflow": [
                {"id": "analyze_task", "name": "analyze_task"},
                {"id": "write_task", "name": "write_task"},
            ],
            "evidence_packet": {
                "framework_constructs": [
                    {"role": "Email Context Analyst"},
                    {"role": "Professional Email Writer"},
                    {"role": "crew"},
                ]
            }
        }
    )

    scenarios = [
        Scenario(
            id="SC-01",
            agent_id="agent-crew-2",
            agent_version_id="v1",
            category=ScenarioCategory.NORMAL,
            title="Happy path crew execution",
            purpose="Executes crew analysis task",
            description="Executes crew",
            target_workflow_node="analyze_task"
        )
    ]

    report = compute_coverage_gaps(agent, scenarios)

    assert report.total_tools == 0
    assert "Email Context Analyst" not in report.unexercised_tools
    assert "Professional Email Writer" not in report.unexercised_tools
    assert "crew" not in report.unexercised_tools
    assert "analyze_task" not in report.unexercised_tools
    assert "write_task" not in report.unexercised_tools


def test_agent_with_real_tool_tracks_tool_coverage():
    """Rule 3: Agent with real @tool appears in tool coverage and can be unexercised."""
    tool = ToolDefinition(
        name="send_email",
        description="Sends email",
        canonical_capability="EMAIL"
    )
    agent = AgentRecord(
        id="agent-tool-1",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Email Sender Agent",
        description="Email sender",
        status="active",
        tools=[tool],
        agent_spec={
            "tools": [{"name": "send_email", "type": "function"}]
        }
    )

    report = compute_coverage_gaps(agent, [])

    assert report.total_tools == 1
    assert report.exercised_tools == 0
    assert report.unexercised_tools == ["send_email"]
    assert any("1 user tool(s) never exercised" in gap for gap in report.gaps_detected)


def test_scenario_targeting_workflow_node_increases_workflow_coverage_not_tool_coverage():
    """Rule 4: Scenario targeting analyze_task increases workflow coverage, NOT tool coverage."""
    tool = ToolDefinition(
        name="fetch_database_records",
        description="Fetches records",
        canonical_capability="DATA_RETRIEVAL"
    )
    agent = AgentRecord(
        id="agent-wf-1",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Hybrid Workflow Agent",
        description="Hybrid agent",
        status="active",
        tools=[tool],
        workflow=[
            {"id": "analyze_task", "name": "analyze_task"},
            {"id": "write_task", "name": "write_task"},
        ],
        agent_spec={
            "tools": [{"name": "fetch_database_records", "type": "function"}],
            "workflow": [
                {"id": "analyze_task", "name": "analyze_task"},
                {"id": "write_task", "name": "write_task"},
            ]
        }
    )

    sc = Scenario(
        id="SC-WF-1",
        agent_id="agent-wf-1",
        agent_version_id="v1",
        category=ScenarioCategory.NORMAL,
        title="Target analyze task",
        purpose="Target analyze task node",
        description="Targets analyze_task node",
        target_workflow_node="analyze_task"
    )

    report = compute_coverage_gaps(agent, [sc])

    assert report.total_tools == 1
    assert report.exercised_tools == 0
    assert report.unexercised_tools == ["fetch_database_records"]
    assert report.workflow_node_coverage_pct == 50.0


def test_scenario_targeting_real_tool_increases_tool_coverage():
    """Rule 5: Scenario targeting a real tool increases tool coverage."""
    tool = ToolDefinition(
        name="fetch_database_records",
        description="Fetches records",
        canonical_capability="DATA_RETRIEVAL"
    )
    agent = AgentRecord(
        id="agent-wf-2",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Hybrid Workflow Agent",
        description="Hybrid agent 2",
        status="active",
        tools=[tool],
        agent_spec={
            "tools": [{"name": "fetch_database_records", "type": "function"}],
            "workflow": [
                {"id": "analyze_task", "name": "analyze_task"},
            ]
        }
    )

    sc = Scenario(
        id="SC-TOOL-1",
        agent_id="agent-wf-2",
        agent_version_id="v1",
        category=ScenarioCategory.NORMAL,
        title="Target real tool",
        purpose="Target real tool assertion",
        description="Targets real tool assertion",
        required_capabilities=["DATA_RETRIEVAL"]
    )

    report = compute_coverage_gaps(agent, [sc])

    assert report.total_tools == 1
    assert report.exercised_tools == 1
    assert report.unexercised_tools == []
    assert report.capability_coverage_pct == 100.0


def test_zero_applicable_surfaces_handled_without_penalization():
    """Rule 6 & 7: Agent with zero failure surfaces or invariants is not penalized."""
    agent = AgentRecord(
        id="agent-simple-1",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Simple Agent",
        description="Simple description",
        status="active",
        tools=[],
        agent_spec={
            "tools": [],
            "failure_surfaces": [],
            "constitution": {"never_rules": [], "always_rules": []}
        }
    )

    sc = Scenario(
        id="SC-SIMP-1",
        agent_id="agent-simple-1",
        agent_version_id="v1",
        category=ScenarioCategory.NORMAL,
        title="Simple test",
        purpose="Simple test purpose",
        description="Simple test",
        interface_type="CLI"
    )

    report = compute_coverage_gaps(agent, [sc])

    assert report.failure_surface_coverage_pct == 100.0
    assert report.invariant_coverage_pct == 100.0
    assert report.overall_coverage_pct > 0.0


def test_coverage_engine_never_reports_zero_total_tools_with_unexercised_items():
    """Rule 8: Invariant check — total_tools == 0 guarantees unexercised_tools is empty."""
    agent = AgentRecord(
        id="agent-inv-1",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Zero Tool Agent",
        description="Zero tool description",
        status="active",
        tools=[],
        agent_spec={
            "tools": [],
            "evidence_packet": {
                "framework_constructs": [{"name": "fake_tool_1"}, {"name": "fake_tool_2"}]
            }
        }
    )

    report = compute_coverage_gaps(agent, [])

    if report.total_tools == 0:
        assert report.unexercised_tools == [], "unexercised_tools must be empty when total_tools == 0"
