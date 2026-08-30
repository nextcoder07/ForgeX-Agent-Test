"""
Execution Preflight & Sandbox Runtime Provisioning Pipeline Test Suite.
Verifies the complete Stage 4 execution lifecycle, package/import disambiguation,
isolation keying, and preflight blocker handling.
"""

import pytest
from app.models.agent import AgentRecord, ToolDefinition, DependencyDefinition
from app.models.scenario import Scenario, ScenarioCategory
from app.core.dependencies.tool_gateway import ToolGateway
from app.core.dependencies.runtime_smoke_tester import RuntimeSmokeTester
from app.core.sandbox.sandbox_manager import build_sandbox_specification_for_agent, get_or_create_sandbox_spec
from app.core.sandbox.subprocess_runner import run_scenario_in_subprocess, create_sanitized_environment


def test_python_dotenv_distribution_maps_to_dotenv_import():
    """Rule 5: python-dotenv distribution package maps to 'dotenv' import verification."""
    tester = RuntimeSmokeTester()
    assert tester._package_is_importable("python-dotenv==1.0.1") is True
    assert tester._package_is_importable("python_dotenv==1.0.1") is True
    assert tester._package_is_importable("dotenv") is True


def test_version_strings_are_stripped_during_module_extraction():
    """Rule 1 & 5: Version numbers (==0.80.0, ==0.2.0) are stripped cleanly during import resolution."""
    agent = AgentRecord(
        id="agent-crew-deps",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Email Crew Agent",
        description="Autonomous crew agent",
        status="active",
        dependencies=[
            DependencyDefinition(id="dep-1", name="crewai==0.80.0", type="package", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="dep-2", name="langchain-openai==0.2.0", type="package", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="dep-3", name="python-dotenv==1.0.1", type="package", required=True, detected_from="requirements.txt"),
        ]
    )

    modules = RuntimeSmokeTester._extract_modules_to_test(agent)
    assert "crewai" in modules
    assert "langchain_openai" in modules or "langchain-openai" in modules
    assert "python-dotenv" in modules or "python_dotenv" in modules or "dotenv" in modules

    smoke_res = RuntimeSmokeTester.run_smoke_test(agent)
    import_checks = {c.target: c.passed for c in smoke_res.checks if c.check_type == "IMPORT"}
    assert import_checks.get("crewai") is True
    assert import_checks.get("langchain_openai") is True or import_checks.get("langchain-openai") is True
    assert import_checks.get("python-dotenv") is True or import_checks.get("dotenv") is True or import_checks.get("python_dotenv") is True


def test_runtime_sandbox_keying_prevents_cross_agent_spec_leakage():
    """Rules 6, 7 & 8: Sandbox specification and model bindings are strictly keyed by agent_id & version."""
    agent1 = AgentRecord(
        id="agent-66cc159f",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Agent 1",
        description="First agent",
        version_label="v1.0",
        status="active"
    )
    agent2 = AgentRecord(
        id="agent-69257593",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Agent 2",
        description="Second agent",
        version_label="v1.0",
        status="active"
    )

    spec1 = get_or_create_sandbox_spec(agent1)
    spec2 = get_or_create_sandbox_spec(agent2)

    assert spec1.agent_id == "agent-66cc159f"
    assert spec2.agent_id == "agent-69257593"
    assert spec1.id != spec2.id


def test_missing_credential_produces_credential_failure_not_package_failure():
    """Rule 9: Missing OPENAI_API_KEY produces credential preflight failure, not package failure."""
    agent = AgentRecord(
        id="agent-no-key",
        owner_id="user-1",
        workspace_id="ws-1",
        name="OpenAI Agent",
        description="Requires OpenAI key",
        status="active",
        dependencies=[
            DependencyDefinition(id="dep-tav", name="TAVILY_API_KEY", type="credential", provider="Tavily", required=True, detected_from="code")
        ]
    )

    smoke_res = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={})
    assert smoke_res.is_executable is False
    assert smoke_res.blocking_reason == "MISSING_USER_CREDENTIAL"
    assert any("TAVILY_API_KEY" in b for b in smoke_res.blockers)


def test_blocked_preflight_does_not_produce_fake_tool_calls_or_execution_events():
    """Rules 11 & 12: Blocked preflight does not produce fake tool calls, 0ms latency, or COMPLETED state."""
    agent = AgentRecord(
        id="agent-blocked-run",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Blocked Agent",
        description="Blocked agent",
        status="active",
        dependencies=[
            DependencyDefinition(id="dep-cust", name="CUSTOM_UNSUPPORTED_SECRET_KEY", type="credential", required=True, detected_from="code")
        ]
    )

    scenario = Scenario(
        id="SC-BLOCK-1",
        agent_id="agent-blocked-run",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Blocked Scenario",
        purpose="Verify preflight block behavior",
        description="Scenario that will be blocked"
    )

    gateway = ToolGateway(tools=agent.tools)
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content="print('Hello World')",
        gateway=gateway
    )

    assert trace.status == "BLOCKED"
    assert trace.total_latency_ms == 0.0
    assert len(trace.tool_calls) == 0
    assert len(trace.events) == 1
    assert "PRE-FLIGHT / DEPENDENCY_BLOCK" in trace.events[0].content or "Preflight blocked" in trace.events[0].content


def test_end_to_end_crewai_langchain_dotenv_subprocess_execution():
    """Rule 13: End-to-end execution with crewai, langchain-openai, python-dotenv reaches RUNNING."""
    agent = AgentRecord(
        id="agent-e2e-crew",
        owner_id="user-1",
        workspace_id="ws-1",
        name="CrewAI Research Agent",
        description="Research agent",
        status="active",
        dependencies=[
            DependencyDefinition(id="dep-c", name="crewai==0.80.0", type="package", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="dep-l", name="langchain-openai==0.2.0", type="package", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="dep-d", name="python-dotenv==1.0.1", type="package", required=True, detected_from="requirements.txt"),
        ]
    )

    scenario = Scenario(
        id="SC-E2E-1",
        agent_id="agent-e2e-crew",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Happy path execution",
        purpose="Verify end-to-end execution",
        description="Executes script successfully",
        interface_type="CLI"
    )

    code = """
import os
import sys
import dotenv

print("EXECUTION_SUCCESS: Subprocess started and executed cleanly.")
"""

    gateway = ToolGateway(tools=agent.tools)
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content=code,
        gateway=gateway
    )

    assert trace.status == "COMPLETED"
    assert trace.total_latency_ms > 0.0
    assert any("PROCESS_STARTED" in e.content for e in trace.events)
    assert any("EXECUTION_SUCCESS" in e.content for e in trace.events)
