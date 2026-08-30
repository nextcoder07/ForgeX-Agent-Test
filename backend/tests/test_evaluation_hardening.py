from types import SimpleNamespace

import pytest

from app.core.evaluation.hybrid_evaluator import evaluate_trace
from app.core.evaluation.scorecard_engine import compute_reliability_scorecard
from app.api.evaluations import normalize_execution_binding
from app.models.agent import AgentRecord, ToolDefinition
from app.models.execution import ExecutionTrace, TraceEvent, ToolCallRecord
from app.models.scenario import Scenario, ScenarioCategory


class FailingJudgeLLM:
    async def judge_trace(self, trace_json, constraints):
        raise TimeoutError("provider_timeout")


def _build_agent():
    return AgentRecord(
        id="agent-eval-hardening",
        name="hardening-agent",
        display_name="Hardening Agent",
        description="Test agent",
        created_at="2026-01-01T00:00:00Z",
        domain="general",
        system_prompt="Stay safe.",
        tools=[ToolDefinition(name="query_order", description="Query order", canonical_capability="ORDER_LOOKUP")],
    )


@pytest.mark.asyncio
async def test_evaluate_trace_handles_missing_constitution_and_marks_semantic_unavailable():
    agent = _build_agent()
    scenario = Scenario(
        id="SC-NULL-CONST-01",
        category=ScenarioCategory.NORMAL,
        title="No constitution",
        purpose="Ensure missing constitution does not crash evaluation.",
        user_messages=["Check order ORD-123"],
        required_capabilities=["ORDER_LOOKUP"],
        assertions=[],
    )
    trace = ExecutionTrace(
        id="trc-null-constitution",
        scenario_id=scenario.id,
        agent_id=agent.id,
        agent_version=agent.version_label,
        status="COMPLETED",
        events=[TraceEvent(timestamp="12:00", role="user", content="Check order ORD-123")],
        tool_calls=[ToolCallRecord(id="tc-1", sequence=1, tool_name="query_order", arguments={"order_id": "ORD-123"}, result={"status": "ok"})],
    )

    verdict = await evaluate_trace(agent, scenario, trace, FailingJudgeLLM())

    assert verdict.status in {"PASS", "FAIL", "INCONCLUSIVE"}
    assert verdict.semantic_judge_status == "UNAVAILABLE"
    assert verdict.semantic_judge_reason == "provider_timeout"


def test_normalize_execution_binding_blocks_incomplete_binding():
    normalized = normalize_execution_binding(None)

    assert normalized.status == "EVALUATION_BLOCKED"
    assert normalized.reason == "INCOMPLETE_EXECUTION_BINDING"


def test_compute_reliability_scorecard_handles_empty_verdicts_as_inconclusive():
    agent = _build_agent()
    scorecard = compute_reliability_scorecard("eval-empty", agent, [])

    assert scorecard.inconclusive == 1
    assert scorecard.passed == 0
    assert scorecard.failed == 0
    assert scorecard.provenance["evaluation_status"] == "INCONCLUSIVE"
    assert scorecard.provenance["warning"] == "No evaluable scenarios produced"


def test_generate_explainable_evaluation_report_with_string_binding_mode():
    from app.core.evaluation.scorecard_engine import generate_explainable_evaluation_report
    agent = _build_agent()
    binding_duck = SimpleNamespace(
        mode="faithful",
        model_substitution=False,
        confidence="HIGH",
        original_model="gpt-4o-mini",
        executed_model="gemini-3.7-flash"
    )
    report = generate_explainable_evaluation_report("eval-str-mode", agent, [], binding_duck)
    assert report.evaluation_id == "eval-str-mode"
    assert "FAITHFUL" in report.explainability[1]


def test_agent_diagnosis_report_fallback_instantiation():
    from app.models.diagnosis import AgentDiagnosisReport
    report = AgentDiagnosisReport(
        id="diag-empty-test",
        evaluation_run_id="exec-123",
        agent_id="unknown",
        agent_name="Unknown Agent",
        total_failures=0,
        critical_failures=0,
        diagnoses=[],
        defect_breakdown={},
        primary_repair_recommendation="No evaluation records found for run ID 'exec-123'."
    )
    assert report.total_failures == 0
    assert report.critical_failures == 0
    assert report.agent_id == "unknown"


def test_normalize_enum_value_utility():
    from app.models.enums import normalize_enum_value
    from enum import Enum
    class Mode(Enum):
        FAITHFUL = "faithful"
    
    assert normalize_enum_value(Mode.FAITHFUL) == "faithful"
    assert normalize_enum_value("faithful") == "faithful"
    assert normalize_enum_value(None, default="faithful") == "faithful"
    assert normalize_enum_value(123) == "123"


def test_build_empty_diagnosis_report_factory():
    from app.models.diagnosis import build_empty_diagnosis_report
    report = build_empty_diagnosis_report("agent-123", "Test Agent", "eval-123", "No failures")
    assert report.total_failures == 0
    assert report.critical_failures == 0
    assert report.agent_id == "agent-123"
    assert report.agent_name == "Test Agent"
    assert report.evaluation_run_id == "eval-123"


@pytest.mark.asyncio
async def test_gemini_provider_unusable_key_circuit_breaker():
    from app.core.llm.gemini_provider import GeminiProvider, LLMGenerationError
    provider = GeminiProvider(api_key="INVALID_TEST_KEY")
    provider.is_available = False
    provider.last_error_reason = "API key invalid (AUTHENTICATION_ERROR)"
    
    with pytest.raises(LLMGenerationError) as exc_info:
        await provider.generate("system", "user")
    
    assert "Gemini provider is marked unavailable" in str(exc_info.value)
