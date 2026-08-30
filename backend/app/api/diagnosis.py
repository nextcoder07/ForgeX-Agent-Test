"""
Failure Diagnosis API.
Provides deep-dive root cause analysis and evidence-linked explanations for evaluation runs.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.diagnosis import AgentDiagnosisReport, build_empty_diagnosis_report
from app.core.diagnosis.root_cause_analyzer import RootCauseAnalyzer
from app.services.store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnosis", tags=["Diagnosis"])
analyzer = RootCauseAnalyzer()


@router.get("/agent/{agent_id}", response_model=AgentDiagnosisReport)
async def get_agent_latest_diagnosis(agent_id: str, evaluation_run_id: Optional[str] = Query(None)):
    """Retrieve diagnosis report for an agent, using explicit evaluation_run_id if provided."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    target_run_id = evaluation_run_id
    if not target_run_id:
        # Fallback to latest evaluation run for this agent if no specific run_id requested
        all_jobs = [j for j in store.jobs.values() if getattr(j, "agent_id", None) == agent.id]
        all_scorecards = [sc for sc in store.scorecards.values() if getattr(sc, "agent_id", None) == agent.id]

        if all_jobs:
            sorted_jobs = sorted(all_jobs, key=lambda j: getattr(j, "created_at", ""))
            target_run_id = sorted_jobs[-1].id
        elif all_scorecards:
            target_run_id = all_scorecards[-1].evaluation_id

    if not target_run_id:
        return build_empty_diagnosis_report(
            agent_id=agent.id,
            agent_name=agent.name,
            evaluation_run_id="",
            summary=f"No evaluated execution runs exist for agent '{agent.name}'. Execute scenarios in Sandbox first."
        )

    return await get_or_generate_diagnosis(target_run_id)


@router.get("/{id_param}", response_model=AgentDiagnosisReport)
async def get_or_generate_diagnosis(id_param: str):
    """Retrieve or compute a deep root-cause diagnosis report for an evaluation_run_id, execution_id, or agent_id."""
    cached = store.get_diagnosis_report(id_param)
    if cached:
        return cached

    # 1. Resolve id_param to canonical evaluation_run_id and agent_id
    evaluation_run_id = id_param
    scorecard = store.get_scorecard(evaluation_run_id)
    verdicts = store.verdicts.get(evaluation_run_id, [])
    traces = store.traces.get(evaluation_run_id, [])

    # If not found directly, check if id_param is an execution_id that maps to an evaluation run
    if not scorecard and not verdicts and not traces:
        matching_job = next((j for j in store.jobs.values() if getattr(j, "execution_id", None) == id_param or j.id == id_param), None)
        if matching_job and matching_job.id != id_param:
            evaluation_run_id = matching_job.id
            scorecard = store.get_scorecard(evaluation_run_id)
            verdicts = store.verdicts.get(evaluation_run_id, [])
            traces = store.traces.get(evaluation_run_id, [])

    agent_id = scorecard.agent_id if scorecard else (verdicts[0].agent_id if verdicts else None)

    # 2. Check if id_param is an agent_id directly
    if not agent_id:
        agent = store.get_agent(id_param)
        if agent:
            return await get_agent_latest_diagnosis(agent.id)

        # Non-existent agent or invalid run ID: return clean empty diagnosis report via factory
        return build_empty_diagnosis_report(
            agent_id="unknown",
            agent_name="Unknown Agent",
            evaluation_run_id=id_param,
            summary=f"No evaluation records found for run ID '{id_param}'."
        )

    agent = store.get_agent(agent_id)
    if not agent:
        return build_empty_diagnosis_report(
            agent_id=agent_id,
            agent_name="Unknown Agent",
            evaluation_run_id=evaluation_run_id,
            summary=f"Agent '{agent_id}' not found."
        )

    report = analyzer.analyze_evaluation(agent, evaluation_run_id, verdicts, traces)
    store.save_diagnosis_report(report)
    return report
