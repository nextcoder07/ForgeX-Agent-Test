"""
Fix My Agent API Router.
Exposes endpoints for checking agent evaluation issues, requesting explicit user repair authorization,
starting the autonomous repair loop, stopping the loop, and fetching iteration history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.repair import RepairSession, RepairStatus
from app.services.store import store
from app.core.repair.repair_orchestrator import RepairOrchestrator

router = APIRouter(prefix="/repair", tags=["Fix My Agent"])


class StartRepairRequest(BaseModel):
    session_id: str
    max_iterations: int = 5


@router.get("/agents/{agent_id}/status", response_model=Dict[str, Any])
def get_agent_repair_status(agent_id: str):
    """Retrieve agent issues and prompt asking user for explicit repair confirmation. Does NOT modify agent!"""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    session = RepairOrchestrator.get_or_create_session(agent_id)
    baseline = session.baseline_scorecard

    failed_count = session.remaining_failures if session.remaining_failures is not None else (baseline.failed if baseline else 3)
    crit_count = session.critical_failures if session.critical_failures is not None else (baseline.critical_failures if baseline else 2)

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "current_version": session.current_version or agent.version_label,
        "session_id": session.id,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "current_iteration": session.current_iteration,
        "max_iterations": session.max_iterations,
        "current_step": session.current_step,
        "final_status": session.final_status,
        "final_verdict": session.final_verdict,
        "error_message": session.error_message,
        "user_approved_repair": session.user_approved_repair,
        "evaluation_complete": True,
        "failed_scenarios_count": failed_count,
        "reliability_issues_count": crit_count,
        "issues_detected": failed_count > 0 or crit_count > 0,
        "prompt_message": "Issues detected. Would you like Fix My Agent to attempt repairs?",
        "baseline_scorecard": baseline,
        "latest_scorecard": session.latest_scorecard or baseline,
    }


@router.post("/sessions/start", response_model=RepairSession)
def start_repair_session(payload: StartRepairRequest, background_tasks: BackgroundTasks):
    """Explicitly start the repair loop after user clicks 'Fix Agent' and approves Repair Plan."""
    session = store.repair_sessions.get(payload.session_id)
    if not session:
        # Fall back to checking by agent_id
        session = RepairOrchestrator.get_or_create_session(payload.session_id)

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[REPAIR_REQUEST] session_id={session.id} agent_id={session.agent_id} base_version={session.original_version}")
    logger.info(f"[REPAIR_APPLY_STARTED] max_iterations={payload.max_iterations}")

    session.status = RepairStatus.RUNNING
    session.user_approved_repair = True
    store.repair_sessions[session.id] = session

    # Run repair loop
    background_tasks.add_task(
        RepairOrchestrator.start_repair_loop,
        session.id,
        payload.max_iterations
    )
    
    return session


@router.post("/sessions/{session_id}/stop", response_model=RepairSession)
def stop_repair_session(session_id: str):
    """Stop the repair loop on user request."""
    return RepairOrchestrator.stop_repair_loop(session_id)


@router.get("/sessions/{session_id}", response_model=RepairSession)
def get_repair_session(session_id: str):
    """Retrieve repair session history, iteration logs, and deltas."""
    session = store.repair_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Repair session '{session_id}' not found")
    return session

