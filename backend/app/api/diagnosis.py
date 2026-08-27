"""
Failure Diagnosis API.
Provides deep-dive root cause analysis and evidence-linked explanations for evaluation runs.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.diagnosis import AgentDiagnosisReport
from app.core.diagnosis.root_cause_analyzer import RootCauseAnalyzer
from app.services.store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnosis", tags=["Diagnosis"])
analyzer = RootCauseAnalyzer()


@router.get("/agent/{agent_id}", response_model=AgentDiagnosisReport)
async def get_agent_latest_diagnosis(agent_id: str):
    """Retrieve the latest diagnosis report for an agent, returning structured status if clean or no runs."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # Find latest scorecard/evaluation for this agent
    all_scorecards = [sc for sc in store.scorecards.values() if sc.agent_id == agent.id]
    if not all_scorecards:
        return AgentDiagnosisReport(
            id=f"diag-none-{agent.id}",
            evaluation_run_id="",
            agent_id=agent.id,
            agent_name=agent.name,
            total_verdicts_evaluated=0,
            failed_verdicts_count=0,
            diagnoses=[],
            primary_layer_blame="NONE",
            summary=f"No evaluated execution runs exist for agent '{agent.name}'. Execute scenarios in Sandbox first."
        )

    latest_sc = all_scorecards[-1]
    return await get_or_generate_diagnosis(latest_sc.evaluation_id)


@router.get("/{evaluation_run_id}", response_model=AgentDiagnosisReport)
async def get_or_generate_diagnosis(evaluation_run_id: str):
    """Retrieve or compute a deep root-cause diagnosis report for an evaluation run."""
    cached = store.get_diagnosis_report(evaluation_run_id)
    if cached:
        return cached

    scorecard = store.get_scorecard(evaluation_run_id)
    verdicts = store.verdicts.get(evaluation_run_id, [])
    traces = store.traces.get(evaluation_run_id, [])

    agent_id = scorecard.agent_id if scorecard else (verdicts[0].agent_id if verdicts else None)
    if not agent_id:
        # Search if evaluation_run_id matches an agent directly
        agent = store.get_agent(evaluation_run_id)
        if agent:
            return await get_agent_latest_diagnosis(agent.id)
        
        # Return structured fallback instead of generic 404
        return AgentDiagnosisReport(
            id=f"diag-empty-{evaluation_run_id}",
            evaluation_run_id=evaluation_run_id,
            agent_id="unknown",
            agent_name="Unknown Agent",
            total_verdicts_evaluated=0,
            failed_verdicts_count=0,
            diagnoses=[],
            primary_layer_blame="NONE",
            summary=f"No evaluation records found for run ID '{evaluation_run_id}'."
        )

    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    report = analyzer.analyze_evaluation(agent, evaluation_run_id, verdicts, traces)
    store.save_diagnosis_report(report)
    return report
