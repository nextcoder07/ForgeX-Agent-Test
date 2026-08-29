"""
Tests for Stage 2 Scenario Hard Validator & Context Builder.

Covers:
  - ScenarioContext extraction from AgentRecord
  - Rule A: JSON validation guard
  - Rule 1: CLI flag whitelist
  - Rule 2: Impossible exit_code=1 on empty invocation when defaults exist
  - Rule 3: Invented STDOUT_CONTAINS rejection
  - Rule 4: Workflow node whitelist
  - Rule 5: Capability whitelist
  - Rule 8: Fault target validation
  - Quality score computation
  - Assertion normalization (Email & Recovery semantic mapping)
"""

import pytest
from unittest.mock import MagicMock
from app.core.scenarios.scenario_context import (
    build_scenario_context,
    ScenarioContext
)
from app.core.scenarios.scenario_validator import (
    hard_validate_scenarios,
    normalize_assertions,
    compute_scenario_quality_score,
    _RISK_BY_CATEGORY,
    _cli_args_from_invocation,
    _assertion_value_is_in_source,
)
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    ScenarioAssertion,
    TargetSubsystem,
    AssertionType,
    FaultInjection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EMAIL_AGENT_SPEC = {
    "inputs": [
        {"name": "context", "type": "string", "default": "Follow up on demo", "required": False},
        {"name": "tone", "type": "string", "default": "professional", "required": False},
        {"name": "recipient", "type": "string", "default": "a potential client", "required": False},
    ],
    "outputs": [
        {"name": "email_brief", "type": "string", "semantic_type": "EMAIL_BRIEF", "description": "Email brief"},
        {"name": "email", "type": "string", "semantic_type": "EMAIL_DRAFT", "description": "Final email"},
    ],
    "capabilities": ["EMAIL", "LLM_INFERENCE"],
    "workflow": [
        {"id": "main", "name": "main()"},
        {"id": "analyze_task", "name": "Email Context Analyst (analyze_task)"},
        {"id": "write_task", "name": "Professional Email Writer (write_task)"},
    ],
    "side_effects": ["MODEL_INFERENCE: ChatOpenAI"],
    "dependencies": [{"name": "SendGrid"}],
    "evidence_packet": {
        "cli_arguments": [
            {"flags": ["--context"], "required": False, "default_value": "Follow up on demo"},
            {"flags": ["--tone"], "required": False, "default_value": "professional"},
            {"flags": ["--recipient"], "required": False, "default_value": "a potential client"},
        ],
        "framework_constructs": [
            {"type": "crewai_agent", "role": "Email Context Analyst", "var_name": "analyst"},
            {"type": "crewai_agent", "role": "Professional Email Writer", "var_name": "writer"},
        ],
        "llm_constructors": [{"source_class": "ChatOpenAI", "provider": "openai"}],
        "source_files": {
            "agent.py": "def main():\n    pass\n"
        },
    },
}

EMAIL_AGENT_MANIFEST = {
    "entrypoint": "agent.py",
    "detected_interface": "CLI",
    "interface_type": "CLI",
}


def _make_agent(spec=None, manifest=None):
    agent = MagicMock()
    agent.id = "agent-email-test"
    agent.name = "email"
    agent.domain = "communication"
    agent.description = "Email drafting agent"
    agent.tools = []
    agent.dependencies = []
    agent.agent_spec = spec or EMAIL_AGENT_SPEC
    agent.runtime_manifest = manifest or EMAIL_AGENT_MANIFEST
    agent.constitution = MagicMock()
    agent.constitution.goals = ["Draft professional emails"]
    agent.constitution.never_rules = []
    agent.constitution.always_rules = []
    agent.evidence_packet = None
    return agent


def _make_scenario(
    category=ScenarioCategory.NORMAL,
    args=None,
    assertions=None,
    target_workflow_node=None,
    required_capabilities=None,
    required_services=None,
    fault_injections=None,
):
    sc = MagicMock(spec=Scenario)
    sc.id = "SC-TEST-aabbcc"
    sc.title = f"Test {category.value} scenario"
    sc.category = category
    sc.invocation = {"command": "python agent.py", "arguments": args or []}
    sc.assertions = assertions or [
        ScenarioAssertion(assertion_type="PROCESS_EXIT_CODE", target="exit_code", expected_value=0, description="exits ok")
    ]
    sc.target_workflow_node = target_workflow_node
    sc.target_workflow_node_rationale = None
    sc.required_capabilities = required_capabilities or []
    sc.required_services = required_services or []
    sc.fault_injections = fault_injections or []
    sc.risk_level = "medium"
    sc.target_subsystem = TargetSubsystem.REASONING_PLANNING
    sc.validation_status = "GENERATED"
    sc.status = "GENERATED"
    sc.critic_notes = None
    sc.expected_behavior = {"must": ["complete task"]}
    return sc


# ---------------------------------------------------------------------------
# ScenarioContext Extraction Tests
# ---------------------------------------------------------------------------

def test_context_extracts_cli_flags():
    agent = _make_agent()
    context = build_scenario_context(agent)
    assert "--context" in context.valid_cli_flags
    assert "--tone" in context.valid_cli_flags
    assert "--recipient" in context.valid_cli_flags
    assert "--input" not in context.valid_cli_flags


def test_context_all_inputs_have_defaults():
    agent = _make_agent()
    context = build_scenario_context(agent)
    assert context.all_inputs_have_defaults is True


def test_context_workflow_nodes():
    agent = _make_agent()
    context = build_scenario_context(agent)
    assert "main" in context.workflow_nodes
    assert "analyze_task" in context.workflow_nodes
    assert "nonexistent_node" not in context.workflow_nodes


def test_context_multi_agent_detection():
    agent = _make_agent()
    context = build_scenario_context(agent)
    assert context.multi_agent is True
    assert "Email Context Analyst" in context.agent_personas


def test_context_capabilities_and_services():
    agent = _make_agent()
    context = build_scenario_context(agent)
    assert "EMAIL" in context.capabilities
    assert "openai" in [s.lower() for s in context.external_services]
    assert "sendgrid" in [s.lower() for s in context.external_services]


def test_context_produces_email_not_json():
    agent = _make_agent()
    context = build_scenario_context(agent)
    assert context.produces_email is True
    assert context.produces_json is False


# ---------------------------------------------------------------------------
# Assertion Normalization
# ---------------------------------------------------------------------------

def test_normalize_assertions_email_greeting():
    agent = _make_agent()
    context = build_scenario_context(agent)
    sc = _make_scenario(assertions=[
        ScenarioAssertion(assertion_type="STDOUT_CONTAINS", expected_value="Dear John,")
    ])
    normalize_assertions(sc, context)
    assert sc.assertions[0].assertion_type == "EMAIL_SECTION_PRESENT"
    assert sc.assertions[0].expected_value == "greeting"


def test_normalize_assertions_recovery_timeout():
    agent = _make_agent()
    context = build_scenario_context(agent)
    sc = _make_scenario(category=ScenarioCategory.RECOVERY, assertions=[
        ScenarioAssertion(assertion_type="STDOUT_CONTAINS", expected_value="Error: timeout")
    ])
    normalize_assertions(sc, context)
    assert sc.assertions[0].assertion_type == "NO_UNHANDLED_EXCEPTIONS"
    assert sc.assertions[1].assertion_type == "PROCESS_TERMINATES_WITHIN_TIMEOUT"


# ---------------------------------------------------------------------------
# Quality Score
# ---------------------------------------------------------------------------

def test_quality_score_high_quality():
    agent = _make_agent()
    context = build_scenario_context(agent)
    sc = _make_scenario(
        target_workflow_node="analyze_task",
        required_capabilities=["EMAIL"],
        required_services=["openai"],
        fault_injections=[FaultInjection(target_tool="openai", fault_type="timeout")]
    )
    sc.target_subsystem = TargetSubsystem.ERROR_RECOVERY
    score = compute_scenario_quality_score(sc, context)
    assert score >= 0.75  # Should score very high for hitting all targets


def test_quality_score_low_quality():
    agent = _make_agent()
    context = build_scenario_context(agent)
    sc = _make_scenario(
        target_workflow_node=None,
        required_capabilities=[],
        required_services=[]
    )
    sc.expected_behavior = {}
    score = compute_scenario_quality_score(sc, context)
    assert score < 0.45  # Will likely be rejected


# ---------------------------------------------------------------------------
# Hard Validator Rules
# ---------------------------------------------------------------------------

def test_rule_a_rejects_json_assertion_on_non_json_agent():
    agent = _make_agent()
    sc = _make_scenario(assertions=[
        ScenarioAssertion(assertion_type="STDOUT_JSON_VALID", expected_value=True)
    ])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE_A_JSON_ASSERTION_ON_NON_JSON_AGENT" in report[0]["violations"][0]


def test_rule1_rejects_invented_flag_input():
    agent = _make_agent()
    sc = _make_scenario(args=["--input", "malicious_input.txt"])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE1_UNKNOWN_CLI_FLAGS" in report[0]["violations"][0]


def test_rule2_rejects_impossible_exit_code():
    agent = _make_agent()
    sc = _make_scenario(args=[], assertions=[
        ScenarioAssertion(assertion_type="PROCESS_EXIT_CODE", expected_value=1)
    ])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE2_IMPOSSIBLE_EXIT_CODE" in report[0]["violations"][0]


def test_rule3_rejects_invented_error_message():
    agent = _make_agent()
    sc = _make_scenario(assertions=[
        ScenarioAssertion(assertion_type="STDOUT_CONTAINS", expected_value="Error: Bad topic")
    ])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE3_INVENTED_ERROR_MESSAGE" in report[0]["violations"][0]


def test_rule4_rejects_invalid_workflow_node():
    agent = _make_agent()
    sc = _make_scenario(target_workflow_node="invented_node")
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE4_INVALID_WORKFLOW_NODE" in report[0]["violations"][0]


def test_rule5_rejects_invalid_capability():
    agent = _make_agent()
    sc = _make_scenario(required_capabilities=["INVENTED_CAP"])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE5_INVALID_CAPABILITY" in report[0]["violations"][0]


def test_rule8_rejects_invalid_fault_target():
    agent = _make_agent()
    sc = _make_scenario(fault_injections=[
        FaultInjection(target_tool="InventedAPI", fault_type="timeout")
    ])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE8_INVALID_FAULT_TARGET" in report[0]["violations"][0]


def test_rule9_rejects_duplicate_invocations():
    agent = _make_agent()
    sc1 = _make_scenario(args=["--context", "demo"])
    sc2 = _make_scenario(args=["--context", "demo"])
    passing, report = hard_validate_scenarios([sc1, sc2], agent)
    assert len(passing) == 1
    assert len(report) == 1
    assert "RULE9_DUPLICATE_INVOCATION" in report[0]["violations"][0]


def test_scenario_quality_rejection():
    agent = _make_agent()
    # Scenario missing most targets and uses brittle assertions
    sc = _make_scenario(
        target_workflow_node=None,
        required_capabilities=[],
        assertions=[ScenarioAssertion(assertion_type="STDOUT_CONTAINS", expected_value="Something")]
    )
    sc.expected_behavior = {}
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE_Q_QUALITY_TOO_LOW" in report[0]["violations"][0]


# ---------------------------------------------------------------------------
# Rule 10 & Rule 11
# ---------------------------------------------------------------------------

def test_rule10_rejects_invalid_service():
    agent = _make_agent()
    sc = _make_scenario(required_services=["InventedService"])
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 0
    assert "RULE10_INVALID_SERVICE" in report[0]["violations"][0]


def test_rule11_autocorrects_target_subsystem():
    agent = _make_agent()
    # If set to generic reasoning_planning, it gets auto-corrected
    sc = _make_scenario(category=ScenarioCategory.RECOVERY)
    sc.target_subsystem = TargetSubsystem.REASONING_PLANNING
    sc.fault_injections = [FaultInjection(target_tool="OpenAI", fault_type="timeout")]
    
    passing, report = hard_validate_scenarios([sc], agent)
    assert len(passing) == 1
    assert passing[0].target_subsystem == TargetSubsystem.EXTERNAL_SERVICE_RESILIENCE

