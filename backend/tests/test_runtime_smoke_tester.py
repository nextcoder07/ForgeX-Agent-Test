from app.models.agent import AgentRecord, DependencyDefinition, ToolDefinition
from app.models.scenario import Scenario, ScenarioCategory, ScenarioAssertion
from app.core.dependencies.runtime_smoke_tester import RuntimeSmokeTester, FORGEX_SUPPORTED_PLATFORM_PROVIDERS
from app.core.execution.preflight import run_scenario_preflight
from app.core.scenarios.scenario_validator import normalize_assertions
from app.core.scenarios.scenario_context import build_scenario_context


def test_runtime_smoke_tester_identifies_supported_platform_providers():
    assert "OPENAI" in FORGEX_SUPPORTED_PLATFORM_PROVIDERS
    assert "GEMINI" in FORGEX_SUPPORTED_PLATFORM_PROVIDERS
    assert "OPENROUTER" in FORGEX_SUPPORTED_PLATFORM_PROVIDERS


def test_runtime_smoke_tester_detects_missing_unsupported_credential():
    agent = AgentRecord(
        id="agent-custom-acme",
        name="Acme Agent",
        description="Test Acme agent",
        version_label="v1.0",
        dependencies=[
            DependencyDefinition(id="dep-1", name="ACME_API_KEY", type="credential", detected_from="AST_IMPORT")
        ],
        tools=[ToolDefinition(name="AcmeSearch", description="Custom Acme search tool")]
    )

    result = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={})
    assert result.is_executable is False
    assert result.overall_status == "RUNTIME_BLOCKED"
    assert result.blocking_reason == "MISSING_USER_CREDENTIAL"
    assert any("ACME_API_KEY" in b for b in result.blockers)


def test_runtime_smoke_tester_passes_when_user_supplies_credential():
    agent = AgentRecord(
        id="agent-custom-acme",
        name="Acme Agent",
        description="Test Acme agent",
        version_label="v1.0",
        dependencies=[
            DependencyDefinition(id="dep-1", name="ACME_API_KEY", type="credential", detected_from="AST_IMPORT")
        ],
        tools=[ToolDefinition(name="AcmeSearch", description="Custom Acme search tool")]
    )

    result = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={"ACME_API_KEY": "acme-secret-val-123"})
    assert result.is_executable is True
    assert result.overall_status == "EXECUTABLE"
    assert len(result.blockers) == 0


def test_preflight_blocks_scenario_when_smoke_test_fails():
    agent = AgentRecord(
        id="agent-web-tavily-missing",
        name="Web Agent",
        description="Test web agent",
        version_label="v1.0",
        dependencies=[
            DependencyDefinition(id="dep-1", name="CUSTOM_UNSUPPORTED_KEY", type="credential", detected_from="AST_IMPORT")
        ]
    )
    scenario = Scenario(
        id="sc-01",
        agent_id="agent-web-tavily-missing",
        title="Test Search",
        purpose="Test search capability",
        category=ScenarioCategory.NORMAL,
        interface_type="CLI",
        invocation={"command": "python agent.py --query test"}
    )

    preflight_res = run_scenario_preflight(scenario, agent, provided_variables={})
    assert preflight_res.is_ready is False
    assert preflight_res.status == "BLOCKED"
    assert preflight_res.preflight_record.overall_status == "BLOCKED"


def test_preflight_handles_supported_platform_default_source_without_crashing():
    agent = AgentRecord(
        id="agent-platform-default",
        name="Platform Default Agent",
        description="Test platform default credential handling",
        version_label="v1.0",
        dependencies=[
            DependencyDefinition(id="dep-1", name="OPENAI_API_KEY", type="api_key", detected_from="MANUAL")
        ],
    )
    scenario = Scenario(
        id="sc-platform-default",
        agent_id="agent-platform-default",
        title="Platform default credential scenario",
        purpose="Verify supported platform defaults map to a valid enum source",
        category=ScenarioCategory.NORMAL,
        interface_type="CHAT",
        user_messages=["hello"],
    )

    preflight_res = run_scenario_preflight(scenario, agent, provided_variables={})
    assert preflight_res.status in {"READY", "BLOCKED"}
    assert preflight_res.preflight_record is not None


def test_normalize_assertions_eliminates_null_and_guarantees_minimum_two():
    agent = AgentRecord(
        id="agent-simple",
        name="Simple Agent",
        description="Test simple agent",
        version_label="v1.0",
        source_files={"agent.py": "import argparse\nprint('hello')"}
    )
    ctx = build_scenario_context(agent)

    # Scenario with 1 assertion having expected_value: null
    scenario = Scenario(
        id="sc-null-test",
        agent_id="agent-simple",
        title="Weak Assertion Scenario",
        purpose="Verify assertion normalization",
        category=ScenarioCategory.NORMAL,
        interface_type="CLI",
        assertions=[
            ScenarioAssertion(
                assertion_type="PROCESS_EXIT_CODE",
                target="exit_code",
                expected_value=None
            )
        ]
    )

    normalize_assertions(scenario, ctx)

    # Must have >= 2 concrete assertions, and none with expected_value == None
    assert len(scenario.assertions) >= 2
    for a in scenario.assertions:
        assert a.expected_value is not None
    
    exit_code_assertion = next((a for a in scenario.assertions if a.assertion_type == "PROCESS_EXIT_CODE"), None)
    assert exit_code_assertion is not None
    assert exit_code_assertion.expected_value == 0


def test_extract_secrets_from_uploaded_files():
    source_files = {
        ".env": "TAVILY_API_KEY=tvly-uploaded-secret-123\nOPENAI_API_KEY=your_key_here\n# Commented=value\nVALID_CUSTOM_KEY=custom-val-999\n",
        "config.json": '{"API_SECRET": "sec-456", "EMPTY_KEY": "your_api_key_here"}'
    }
    extracted = RuntimeSmokeTester.extract_secrets_from_source_files(source_files)
    assert extracted.get("TAVILY_API_KEY") == "tvly-uploaded-secret-123"
    assert extracted.get("VALID_CUSTOM_KEY") == "custom-val-999"
    assert extracted.get("API_SECRET") == "sec-456"
    assert "OPENAI_API_KEY" not in extracted  # Placeholder ignored
    assert "EMPTY_KEY" not in extracted  # Placeholder ignored


def test_smoke_test_passes_with_uploaded_env_file():
    agent = AgentRecord(
        id="agent-uploaded-env",
        name="Agent with .env",
        description="Agent containing uploaded .env file",
        version_label="v1.0",
        source_files={
            ".env": "CUSTOM_SPECIAL_KEY=custom-key-live-12345\n",
            "agent.py": "import os\nprint(os.getenv('CUSTOM_SPECIAL_KEY'))\n"
        },
        dependencies=[
            DependencyDefinition(id="dep-1", name="CUSTOM_SPECIAL_KEY", type="credential", detected_from="AST_IMPORT")
        ]
    )
    result = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={})
    assert result.is_executable is True
    cred_check = next(c for c in result.checks if c.target == "CUSTOM_SPECIAL_KEY")
    assert cred_check.passed is True
    assert "uploaded configuration file" in cred_check.message


def test_all_setup_requirements_must_be_fulfilled_before_executable():
    agent = AgentRecord(
        id="agent-strict-setup",
        name="Strict Setup Agent",
        description="Test agent requiring multiple credentials",
        version_label="v1.0",
        dependencies=[
            DependencyDefinition(id="dep-1", name="MISSING_SERVICE_KEY_1", type="credential", detected_from="AST_IMPORT"),
            DependencyDefinition(id="dep-2", name="MISSING_SERVICE_KEY_2", type="credential", detected_from="AST_IMPORT")
        ]
    )
    # Neither key provided -> BLOCKED
    res1 = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={})
    assert res1.is_executable is False
    assert len(res1.blockers) >= 2

    # Partial key provided (only key 1) -> Still BLOCKED
    res2 = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={"MISSING_SERVICE_KEY_1": "val1"})
    assert res2.is_executable is False
    assert any("MISSING_SERVICE_KEY_2" in b for b in res2.blockers)

    # All keys provided -> EXECUTABLE
    res3 = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets={
        "MISSING_SERVICE_KEY_1": "val1",
        "MISSING_SERVICE_KEY_2": "val2"
    })
    assert res3.is_executable is True
    assert len(res3.blockers) == 0

