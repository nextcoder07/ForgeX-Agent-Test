"""
Evaluation Stage & Scorecard Hardening Integration Test Suite.
Verifies trace normalization, evidence-based assertion evaluation, root cause analysis,
failure clustering, 10-dimension scorecard calculation, and regression comparison.
"""

import pytest
from app.models.agent import AgentRecord, ToolDefinition
from app.models.scenario import Scenario, ScenarioCategory, ScenarioAssertion
from app.models.execution import ExecutionTrace, TraceEvent, ToolCallRecord
from app.core.evaluation.trace_normalizer import normalize_execution_trace
from app.core.evaluation.verdict_engine import evaluate_execution_verdict
from app.core.evaluation.semantic_judge import evaluate_semantic_output
from app.core.evaluation.root_cause_analyzer import analyze_scenario_failure, cluster_failure_findings
from app.core.evaluation.scorecard_engine import compute_ten_dimension_scores
from app.core.evaluation.regression_engine import compare_agent_versions
from app.models.failure import RunVerdict


def test_rule_1_and_2_trace_normalization_preserves_raw_evidence():
    """Rules 1 & 2: Trace normalizer builds normalized packet without mutating raw trace."""
    trace = ExecutionTrace(
        id="trc-norm-1",
        agent_id="agent-01",
        agent_version="v1.0",
        scenario_id="sc-01",
        status="COMPLETED",
        total_latency_ms=120.0,
        events=[
            TraceEvent(timestamp="2026-08-30T00:00:00Z", role="system", content="PROCESS_STARTED: Command 'python agent.py'"),
            TraceEvent(timestamp="2026-08-30T00:00:01Z", role="agent_message", content="STDOUT_CHUNK: Processed order #101 successfully"),
            TraceEvent(timestamp="2026-08-30T00:00:02Z", role="system", content="PROCESS_EXITED: Exit code 0")
        ]
    )

    packet = normalize_execution_trace(trace)
    assert packet.trace_id == "trc-norm-1"
    assert packet.process_started is True
    assert packet.exit_code == 0
    assert "Processed order #101" in packet.stdout_full
    assert len(packet.normalized_events) == 3


def test_rule_3_and_4_assertion_engine_and_verdict_priority():
    """Rules 3 & 4: Assertion engine evaluates evidence deterministically and forms correct PASS/FAIL verdicts."""
    trace = ExecutionTrace(
        id="trc-astn-1",
        agent_id="agent-01",
        agent_version="v1.0",
        scenario_id="sc-01",
        status="COMPLETED",
        total_latency_ms=85.0,
        events=[
            TraceEvent(timestamp="2026-08-30T00:00:00Z", role="system", content="PROCESS_STARTED: Command 'python agent.py'"),
            TraceEvent(timestamp="2026-08-30T00:00:01Z", role="agent_message", content="STDOUT_CHUNK: Execution finished cleanly"),
            TraceEvent(timestamp="2026-08-30T00:00:02Z", role="system", content="PROCESS_EXITED: Exit code 0")
        ]
    )

    scenario = Scenario(
        id="sc-01",
        agent_id="agent-01",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Normal Scenario",
        purpose="Verify assertion engine",
        assertions=[
            ScenarioAssertion(id="a1", assertion_type="STDOUT_CONTAINS", expected_value="Execution finished cleanly"),
            ScenarioAssertion(id="a2", assertion_type="NO_UNHANDLED_EXCEPTION", expected_value="true")
        ]
    )

    verdict_res = evaluate_execution_verdict(trace, scenario)
    assert verdict_res.execution_status == "COMPLETED"
    assert verdict_res.evaluation_verdict == "PASS"
    assert verdict_res.passed_count == 2


def test_rule_6_preflight_blocked_scenarios_yield_not_evaluable_without_score_penalty():
    """Rule 6: Preflight BLOCKED runs yield NOT_EVALUABLE and are excluded from Agent Quality scorecards."""
    trace = ExecutionTrace(
        id="trc-block-1",
        agent_id="agent-01",
        agent_version="v1.0",
        scenario_id="sc-blocked",
        status="BLOCKED",
        total_latency_ms=0.0,
        events=[
            TraceEvent(timestamp="2026-08-30T00:00:00Z", role="preflight", content="PRE-FLIGHT / DEPENDENCY_BLOCK: MISSING_USER_CREDENTIAL — Missing required credential: TAVILY_API_KEY")
        ]
    )

    scenario = Scenario(
        id="sc-blocked",
        agent_id="agent-01",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Blocked Scenario",
        purpose="Verify preflight block verdict"
    )

    verdict_res = evaluate_execution_verdict(trace, scenario)
    assert verdict_res.execution_status == "BLOCKED"
    assert verdict_res.evaluation_verdict == "NOT_EVALUABLE"

    # Scorecard calculation excluding BLOCKED run
    v_blocked = RunVerdict(run_id="r-bl", scenario_id="sc-blocked", agent_id="agent-01", trace_id="trc-block-1", passed=False, status="BLOCKED")

    scorecard = compute_ten_dimension_scores([v_blocked])
    assert scorecard.overall_score == 100.0  # Zero penalty for blocked preflight run


def test_rule_8_and_18_tool_discipline_failure_and_root_cause_analysis():
    """Rules 8 & 18: Tool discipline mismatch produces specific TOOL_DISCIPLINE failure category and root cause."""
    trace = ExecutionTrace(
        id="trc-tool-fail",
        agent_id="agent-01",
        agent_version="v1.0",
        scenario_id="sc-tool-01",
        status="COMPLETED",
        total_latency_ms=150.0,
        tool_calls=[
            ToolCallRecord(id="tc-1", sequence=1, tool_name="database_delete")
        ]
    )

    scenario = Scenario(
        id="sc-tool-01",
        agent_id="agent-01",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Tool Scenario",
        purpose="Verify tool discipline evaluation",
        assertions=[
            ScenarioAssertion(id="a1", assertion_type="TOOL_CALLED", target="search", expected_value="search")
        ]
    )

    verdict_res = evaluate_execution_verdict(trace, scenario)
    assert verdict_res.evaluation_verdict == "FAIL"

    packet = normalize_execution_trace(trace)
    rca = analyze_scenario_failure(packet, scenario, verdict_res.findings)
    assert rca is not None
    assert rca.category == "TOOL_DISCIPLINE"
    assert "search" in rca.symptom


def test_rule_15_semantic_judge_safe_fallback_on_unavailable():
    """Rule 15: If semantic LLM judge fails or is unavailable, records status='UNAVAILABLE' without crashing."""
    packet = normalize_execution_trace(ExecutionTrace(
        id="trc-sem-1",
        agent_id="agent-01",
        agent_version="v1.0",
        scenario_id="sc-sem-1",
        status="BLOCKED",
        total_latency_ms=0.0
    ))

    scenario = Scenario(
        id="sc-sem-1",
        agent_id="agent-01",
        agent_version_id="v1.0",
        category=ScenarioCategory.NORMAL,
        title="Semantic Test",
        purpose="Verify semantic judge fallback"
    )

    sem_res = evaluate_semantic_output(packet, scenario)
    assert sem_res.status == "UNAVAILABLE"
    assert sem_res.confidence == 0.0


def test_rule_28_and_30_regression_comparison_rejects_promotion_on_security_regression():
    """Rules 28 & 30: Regression comparison rejects promotion if a new critical security regression occurs."""
    v1_evals = [
        {"scenario_id": "sc-sec-01", "category": "security", "evaluation_verdict": "PASS"},
        {"scenario_id": "sc-norm-01", "category": "normal", "evaluation_verdict": "FAIL"}
    ]
    v2_evals = [
        {"scenario_id": "sc-sec-01", "category": "security", "evaluation_verdict": "FAIL"},  # Critical security regression!
        {"scenario_id": "sc-norm-01", "category": "normal", "evaluation_verdict": "PASS"}   # Fixed normal issue
    ]

    comp_res = compare_agent_versions(
        v1_evaluations=v1_evals,
        v2_evaluations=v2_evals,
        overall_score_v1=75.0,
        overall_score_v2=85.0,  # Score increased, but security regressed!
        v1_version_id="v1.0",
        v2_version_id="v1.1"
    )

    assert comp_res.promotion_decision == "REJECTED"
    assert comp_res.critical_security_regressions == 1
    assert "critical security/safety regression" in comp_res.rejection_reason


def test_delete_single_evaluation_run_completely():
    """Verify single evaluation run deletion endpoint completely purges job and artifacts from store."""
    from app.services.store import store
    from app.models.evaluation import EvaluationJob
    from app.api.evaluations import delete_evaluation_job

    job_id = "eval-test-delete-99"
    job = EvaluationJob(
        id=job_id,
        agent_id="agent-del-1",
        agent_name="Del Agent",
        agent_version="v1.0",
        status="completed",
        current_step="Done",
        total_scenarios=5,
        completed_scenarios=5,
        total_verdicts=5,
        created_at="2026-08-30T00:00:00Z"
    )
    store.jobs[job_id] = job
    assert job_id in store.jobs

    res = delete_evaluation_job(job_id)
    assert res["status"] == "success"
    assert job_id not in store.jobs

