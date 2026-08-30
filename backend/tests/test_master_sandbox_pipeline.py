"""
Master Sandbox & Scenario Execution Pipeline Test Suite.
Verifies the complete end-to-end execution pipeline from ExecutionManifest construction,
RuntimeBuilder provisioning, credential/model resolution, real subprocess launch,
observability & trace logging, to dual verdict evaluation.
"""

import os
import pytest
from app.models.agent import AgentRecord, DependencyDefinition, ToolDefinition
from app.models.scenario import Scenario, ScenarioCategory, ScenarioAssertion
from app.core.execution.manifest_builder import build_execution_manifest
from app.core.sandbox.runtime_builder import RuntimeBuilder
from app.core.sandbox.subprocess_runner import run_scenario_in_subprocess, create_sanitized_environment
from app.core.dependencies.tool_gateway import ToolGateway
from app.core.evaluation.verdict_engine import evaluate_execution_verdict


def test_phase_1_and_2_canonical_execution_manifest_construction():
    """Phases 1 & 2: ExecutionManifest is immutable and captures agent, interface, deps, and scenario."""
    agent = AgentRecord(
        id="agent-master-01",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Master Test Agent",
        description="Autonomous test agent",
        version_label="v1.2",
        status="active",
        dependencies=[
            DependencyDefinition(id="d1", name="crewai==0.80.0", type="package", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="d2", name="python-dotenv==1.0.1", type="package", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="d3", name="OPENAI_API_KEY", type="credential", required=True, detected_from="code"),
        ]
    )

    scenario = Scenario(
        id="SC-MASTER-1",
        agent_id="agent-master-01",
        agent_version_id="v1.2",
        category=ScenarioCategory.NORMAL,
        title="Execution Manifest Test",
        purpose="Verify manifest builder",
        description="Tests canonical manifest creation",
        interface_type="CLI",
        invocation={"command": "python agent.py --input hello", "args": ["--input", "hello"]}
    )

    manifest = build_execution_manifest(agent, scenario, provided_secrets={"OPENAI_API_KEY": "sk-test-123"})
    assert manifest.agent.agent_id == "agent-master-01"
    assert manifest.agent.agent_version_id == "v1.2"
    assert manifest.interface.interface_type == "CLI"
    assert len(manifest.dependencies) == 2
    assert any(d.package_name == "python-dotenv" and d.import_name == "dotenv" for d in manifest.dependencies)
    assert any(c.key_name == "OPENAI_API_KEY" and c.status == "AVAILABLE" for c in manifest.credentials)


def test_phase_3_and_4_runtime_builder_provisioning_and_import_verification():
    """Phases 3 & 4: RuntimeBuilder provisions workspace, verifies imports, and redacts secrets."""
    agent = AgentRecord(
        id="agent-rt-01",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Runtime Agent",
        description="Agent for runtime builder",
        status="active",
        dependencies=[
            DependencyDefinition(id="d1", name="python-dotenv==1.0.1", type="package", required=True, detected_from="requirements.txt")
        ]
    )

    scenario = Scenario(
        id="SC-RT-1",
        agent_id="agent-rt-01",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Runtime provisioning test",
        purpose="Verify runtime environment creation",
        description="Provisions workspace"
    )

    manifest = build_execution_manifest(agent, scenario, provided_secrets={})
    env_rec = RuntimeBuilder.provision_runtime_environment(manifest, code_content="print('Hello')")

    assert env_rec.status == "READY"
    assert env_rec.agent_id == "agent-rt-01"
    assert os.path.exists(env_rec.workspace_dir)
    assert "SUPABASE_KEY" not in env_rec.sanitized_env


def test_phase_5_missing_required_credential_blocks_preflight():
    """Phase 5: Missing required credential results in BLOCKED status and USER_REQUIRED preflight state."""
    agent = AgentRecord(
        id="agent-cred-block",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Secret Demanding Agent",
        description="Requires unknown secret",
        status="active",
        dependencies=[
            DependencyDefinition(id="d1", name="CUSTOM_ENTERPRISE_DB_KEY", type="credential", required=True, detected_from="code")
        ]
    )

    scenario = Scenario(
        id="SC-CRED-1",
        agent_id="agent-cred-block",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Blocked Credential Scenario",
        purpose="Verify credential blocker",
        description="Missing key blocks preflight"
    )

    gateway = ToolGateway(tools=[])
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content="print('Will not run')",
        gateway=gateway
    )

    assert trace.status == "BLOCKED"
    assert trace.total_latency_ms == 0.0
    assert len(trace.events) == 1
    assert "PRE-FLIGHT / DEPENDENCY_BLOCK" in trace.events[0].content

    verdict_res = evaluate_execution_verdict(trace, scenario)
    assert verdict_res.execution_status == "BLOCKED"
    assert verdict_res.evaluation_verdict == "NOT_EVALUABLE"


def test_phase_7_8_9_real_subprocess_execution_and_trace_observability():
    """Phases 7, 8, 9: Actual subprocess executes real code, captures stdout/stderr/events, and evaluates verdict."""
    agent = AgentRecord(
        id="agent-real-exec",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Real Subprocess Agent",
        description="Executes python CLI script",
        status="active",
        dependencies=[
            DependencyDefinition(id="d1", name="python-dotenv==1.0.1", type="package", required=True, detected_from="requirements.txt")
        ]
    )

    scenario = Scenario(
        id="SC-REAL-1",
        agent_id="agent-real-exec",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Happy path execution",
        purpose="Verify real subprocess execution",
        description="Script prints output and exits 0",
        interface_type="CLI",
        assertions=[
            ScenarioAssertion(id="a1", assertion_type="STDOUT_CONTAINS", expected_value="FORGEX_REAL_SUBPROCESS_RUNNING"),
            ScenarioAssertion(id="a2", assertion_type="NO_UNHANDLED_EXCEPTION", expected_value="true")
        ]
    )

    code = """
import os
import sys
import dotenv

print("FORGEX_REAL_SUBPROCESS_RUNNING: Process started with PID", os.getpid())
"""

    gateway = ToolGateway(tools=[])
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content=code,
        gateway=gateway
    )

    assert trace.status == "COMPLETED"
    assert trace.total_latency_ms > 0.0
    assert any("PROCESS_STARTED" in e.content for e in trace.events)
    assert any("FORGEX_REAL_SUBPROCESS_RUNNING" in e.content for e in trace.events)

    verdict_res = evaluate_execution_verdict(trace, scenario)
    assert verdict_res.execution_status == "COMPLETED"
    assert verdict_res.evaluation_verdict == "PASS"
    assert verdict_res.passed_count == 2


def test_chat_interface_launches_real_subprocess_via_stdin_without_fake_harness():
    """Verify CHAT scenarios launch the real subprocess and pipe input via stdin without synthetic tool harnesses."""
    agent = AgentRecord(
        id="agent-chat-real",
        owner_id="user-1",
        workspace_id="ws-1",
        name="Real Chat Subprocess Agent",
        description="Reads prompt from stdin",
        status="active"
    )

    scenario = Scenario(
        id="SC-CHAT-1",
        agent_id="agent-chat-real",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Real Chat Interface Execution",
        purpose="Verify stdin execution",
        description="Reads stdin",
        interface_type="CHAT",
        user_messages=["Hello ForgeX Real Subprocess"],
        assertions=[
            ScenarioAssertion(id="a1", assertion_type="STDOUT_CONTAINS", expected_value="RECEIVED_STDIN_PROMPT: Hello ForgeX Real Subprocess")
        ]
    )

    code = """
import sys

input_text = sys.stdin.read().strip()
print("RECEIVED_STDIN_PROMPT:", input_text)
"""

    gateway = ToolGateway(tools=[])
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content=code,
        gateway=gateway
    )

    assert trace.status == "COMPLETED"
    assert any("PROCESS_STARTED" in e.content for e in trace.events)
    assert any("RECEIVED_STDIN_PROMPT: Hello ForgeX Real Subprocess" in e.content for e in trace.events)
    assert len(trace.tool_calls) == 0  # Zero fake tool calls injected

    verdict_res = evaluate_execution_verdict(trace, scenario)
    assert verdict_res.execution_status == "COMPLETED"
    assert verdict_res.evaluation_verdict == "PASS"

