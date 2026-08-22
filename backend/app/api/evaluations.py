"""
Evaluation Execution, Scorecard, Verdicts, Traces, and Regression Comparison API Router.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import List
from fastapi import APIRouter, HTTPException
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

    # 1. Plan and generate scenarios
    strategy = build_test_strategy(agent, desired_count=payload.scenario_batch_size)
    scenarios = await generate_scenarios_for_agent(agent, strategy, llm)

    traces: List[ExecutionTrace] = []
    verdicts: List[RunVerdict] = []

    # 2. Run each scenario in sandbox and evaluate
    for sc in scenarios:
        # Run attack / primary scenario
        t_primary = run_scenario_in_sandbox(agent, sc)
        t_cf = None

        # If scenario failed or is adversarial, run counterfactual clean control
        if payload.include_counterfactuals and (sc.category.value in ["adversarial", "security", "safety"]):
            t_cf = replay_counterfactual_control(agent, sc, t_primary)

        # Hybrid evaluation (Rule engine + LLM judge)
        v = await evaluate_trace(agent, sc, t_primary, llm, counterfactual_trace=t_cf)

        traces.append(t_primary)
        if t_cf:
            traces.append(t_cf)
        verdicts.append(v)

    # 3. Compute failure clusters & scorecard
    clusters = cluster_failure_verdicts(verdicts)
    scorecard = compute_reliability_scorecard(job_id, agent, verdicts)

    # 4. Save to store
    job = EvaluationJob(
        id=job_id,
        agent_id=agent.id,
        agent_name=agent.name,
        agent_version=agent.version_label,
        status="completed",
        total_scenarios=len(scenarios),
        completed_scenarios=len(scenarios),
        created_at=_now(),
        finished_at=_now()
    )

    store.jobs[job_id] = job
    store.scorecards[job_id] = scorecard
    store.verdicts[job_id] = verdicts
    store.traces[job_id] = traces
    store.clusters[job_id] = clusters

    return job


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
