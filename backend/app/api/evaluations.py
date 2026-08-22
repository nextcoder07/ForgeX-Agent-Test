"""
Evaluation Execution, Scorecard, Verdicts, Traces, and Regression Comparison API Router.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.evaluation import EvaluationRequest, EvaluationJob, ReliabilityScorecard, RegressionComparison
from app.models.failure import RunVerdict, FailureCluster
from app.models.execution import ExecutionTrace
from app.services.store import store
from app.core.scenarios.strategy_planner import build_test_strategy
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.sandbox.runner import run_scenario_in_sandbox
from app.core.evaluation.counterfactual import replay_counterfactual_control
from app.core.evaluation.hybrid_evaluator import evaluate_trace
from app.core.evaluation.failure_clustering import cluster_failure_verdicts
from app.core.evaluation.scorecard_engine import compute_reliability_scorecard, compare_agent_regressions
from app.core.llm.gemini_provider import GeminiProvider
from app.services.activity_log import activity_log

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


def _now() -> str:
    return dt.datetime.utcnow().isoformat()


@router.post("/run", response_model=EvaluationJob)
async def start_evaluation_job(payload: EvaluationRequest):
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    job_id = f"eval-{uuid.uuid4().hex[:8]}"
    llm = GeminiProvider()

    activity_log.emit(
        category="EVALUATION",
        action="JOB_START",
        detail=f"Starting evaluation job {job_id} for agent: {agent.name}",
        request_summary=f"Batch size: {payload.scenario_batch_size} | Counterfactuals: {payload.include_counterfactuals}",
        status="success"
    )

    # Stage 1: Plan, generate, and persist scenarios
    strategy = build_test_strategy(agent, desired_count=payload.scenario_batch_size)
    scenarios = await generate_scenarios_for_agent(agent, strategy, llm)
    for scenario in scenarios:
        scenario.agent_id = agent.id
        store.save_scenario(scenario)

    activity_log.emit(
        category="EVALUATION",
        action="STRATEGY_GENERATED",
        detail=f"Constructed and saved {len(scenarios)} scenarios to persistent store",
        status="success"
    )

    # Stage 2: Create execution job, run scenarios in sandbox, and persist traces
    exec_job_id = f"exec-{uuid.uuid4().hex[:8]}"
    scenario_ids = [sc.id for sc in scenarios]

    exec_job = ExecutionJob(
        id=exec_job_id,
        agent_id=agent.id,
        agent_name=agent.name,
        status="running",
        total_scenarios=len(scenario_ids),
        completed_scenarios=0,
        scenario_ids=scenario_ids,
        created_at=_now(),
    )
    store.save_execution_job(exec_job)

    from app.api.executions import _run_sandbox_scenarios_task
    _run_sandbox_scenarios_task(
        exec_job_id,
        agent.id,
        scenario_ids,
        payload.include_counterfactuals
    )

    # Stage 3: Evaluate executed traces using the persistent execution job
    eval_req = EvaluateExecutionRequest(
        execution_job_id=exec_job_id,
        include_counterfactuals=payload.include_counterfactuals
    )
    return await evaluate_execution(eval_req)


@router.get("/{job_id}/scorecard", response_model=ReliabilityScorecard)
def get_scorecard(job_id: str):
    sc = store.get_scorecard(job_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scorecard '{job_id}' not found")
    return sc


@router.get("/{job_id}/verdicts", response_model=List[RunVerdict])
def get_verdicts(job_id: str):
    return store.verdicts.get(job_id, [])


@router.get("/{job_id}/traces", response_model=List[ExecutionTrace])
def get_traces(job_id: str):
    return store.traces.get(job_id, [])


@router.get("/{job_id}/clusters", response_model=List[FailureCluster])
def get_failure_clusters(job_id: str):
    return store.get_clusters(job_id)


@router.get("/regression/compare", response_model=RegressionComparison)
def compare_regression(from_job_id: str = "eval-seed-01", to_job_id: str = "eval-seed-02"):
    sc1 = store.get_scorecard(from_job_id)
    sc2 = store.get_scorecard(to_job_id)
    if not sc1 or not sc2:
        raise HTTPException(status_code=404, detail="One or both scorecards not found for comparison")
    return compare_agent_regressions(sc1, sc2)


class EvaluateExecutionRequest(BaseModel):
    execution_job_id: str
    include_counterfactuals: bool = True

@router.post("/evaluate-execution", response_model=EvaluationJob)
async def evaluate_execution(payload: EvaluateExecutionRequest):
    exec_job = store.get_execution_job(payload.execution_job_id)
    if not exec_job:
        raise HTTPException(status_code=404, detail=f"Execution job '{payload.execution_job_id}' not found")

    agent = store.get_agent(exec_job.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{exec_job.agent_id}' not found")

    traces_list = store.traces.get(payload.execution_job_id, [])
    if not traces_list:
        raise HTTPException(status_code=422, detail="No execution traces found for this job")

    job_id = f"eval-{uuid.uuid4().hex[:8]}"
    llm = GeminiProvider()

    activity_log.emit(
        category="EVALUATION",
        action="JOB_START",
        detail=f"Starting LLM evaluation for execution job {payload.execution_job_id}",
        request_summary=f"Traces to judge: {len(traces_list)}",
        status="success"
    )

    # Group primary and counterfactual traces
    primaries = [t for t in traces_list if not t.is_counterfactual]
    counterfactuals = {t.counterfactual_of: t for t in traces_list if t.is_counterfactual}

    verdicts: List[RunVerdict] = []

    for t_primary in primaries:
        # Resolve scenario object from persistent store
        sc = store.get_scenario(t_primary.scenario_id)
        if not sc:
            continue

        # Get control trace if matching counterfactual exists
        t_cf = counterfactuals.get(t_primary.id)

        # Evaluate trace using LLM Judge + Rules
        v = await evaluate_trace(agent, sc, t_primary, llm, counterfactual_trace=t_cf)
        verdicts.append(v)

        activity_log.emit(
            category="EVALUATION",
            action="VERDICT",
            detail=f"Evaluation complete for '{sc.title}'",
            response_summary=f"Passed: {v.passed}",
            status="success" if v.passed else "error"
        )

    # Compute clusters & scorecard
    clusters = cluster_failure_verdicts(verdicts)
    scorecard = compute_reliability_scorecard(job_id, agent, verdicts)

    job = EvaluationJob(
        id=job_id,
        agent_id=agent.id,
        agent_name=agent.name,
        agent_version=agent.version_label,
        status="completed",
        total_scenarios=len(primaries),
        completed_scenarios=len(primaries),
        created_at=_now(),
        finished_at=_now()
    )

    store.jobs[job_id] = job
    store.scorecards[job_id] = scorecard
    store.verdicts[job_id] = verdicts
    store.traces[job_id] = traces_list
    store.clusters[job_id] = clusters

    activity_log.emit(
        category="EVALUATION",
        action="JOB_COMPLETE",
        detail=f"LLM evaluation job {job_id} finished successfully.",
        response_summary=f"Passed: {scorecard.passed}/{scorecard.total_scenarios} | Safety Score: {scorecard.safety}% | Composite: {scorecard.composite}%",
        status="success" if scorecard.passed == scorecard.total_scenarios else "warning"
    )

    return job

