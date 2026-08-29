"""
Fix My Agent API Router.
Exposes endpoints for checking agent evaluation issues, requesting explicit user repair authorization,
starting the autonomous repair loop, stopping the loop, and fetching iteration history.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.repair import RepairSession, RepairStatus
from app.services.store import store
from app.core.repair.repair_orchestrator import RepairOrchestrator
from app.core.repair.fixing_agent import FixingAgent, generate_unified_diff
from app.core.llm.providers import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repair", tags=["Fix My Agent"])

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(os.path.dirname(APP_DIR))
TEST_AGENTS_DIR = os.path.join(BACKEND_DIR, "test-agents")


class StartRepairRequest(BaseModel):
    session_id: str
    max_iterations: int = 5


def _get_agent_primary_code(agent: Any) -> str:
    """Retrieve raw Python source code for agent."""
    if agent.source_files:
        for fname, content in agent.source_files.items():
            if fname.endswith(".py") and content.strip():
                return content

    if os.path.isdir(TEST_AGENTS_DIR):
        for d in os.listdir(TEST_AGENTS_DIR):
            if d.lower() in agent.id.lower() or agent.id.lower() in d.lower() or d.lower().replace("-", "_") in agent.name.lower().replace("-", "_"):
                target_py = os.path.join(TEST_AGENTS_DIR, d, "agent.py")
                if os.path.isfile(target_py):
                    try:
                        with open(target_py, "r", encoding="utf-8", errors="ignore") as f:
                            return f.read()
                    except Exception:
                        pass
    return f"# Agent {agent.name}\n# System prompt: {agent.system_prompt}\n"


@router.get("/agents/{agent_id}/status", response_model=Dict[str, Any])
def get_agent_repair_status(agent_id: str):
    """Retrieve agent issues and prompt asking user for explicit repair confirmation. Does NOT modify agent!"""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    session = RepairOrchestrator.get_or_create_session(agent_id)
    baseline = session.baseline_scorecard

    # Find latest scorecard
    latest_sc = session.latest_scorecard or baseline
    if not latest_sc:
        for sc in reversed(list(store.scorecards.values())):
            if sc.agent_id == agent_id:
                latest_sc = sc
                break

    # Get failure verdicts
    eval_id = latest_sc.evaluation_id if latest_sc else ""
    verdicts = store.verdicts.get(eval_id, [])

    findings = []
    for v in verdicts:
        if not v.passed:
            findings.extend(v.findings)

    failed_count = latest_sc.failed if latest_sc else 0
    crit_count = latest_sc.critical_failures if latest_sc else 0

    # Build dynamic proposed plan items
    proposed_plan = []
    seen_categories = set()
    for idx, f in enumerate(findings):
        cat = f.category.upper()
        if cat not in seen_categories:
            seen_categories.add(cat)
            proposed_plan.append({
                "issue_id": f"ISSUE-{len(proposed_plan)+1}",
                "category": f.category,
                "severity": f.severity.upper() if f.severity else "HIGH",
                "title": f.title,
                "problem": f.explanation or f.description,
                "proposed_fix": f.remediation or "Apply defensive parameter validation and constitution constraints.",
                "affected_file": "agent.py",
                "evidence": f.evidence
            })

    # Prepare preview of repairs
    original_code = _get_agent_primary_code(agent)
    llm = get_provider("gemini")
    fixing_agent = FixingAgent(llm)
    repair_preview = fixing_agent.analyze_and_repair(
        agent=agent,
        scorecard=latest_sc or session.baseline_scorecard,
        verdicts=verdicts,
        iteration=1
    )

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
        "evaluation_complete": latest_sc is not None,
        "failed_scenarios_count": failed_count,
        "reliability_issues_count": crit_count,
        "issues_detected": failed_count > 0 or crit_count > 0 or len(findings) > 0,
        "prompt_message": "Issues detected. Would you like Fix My Agent to attempt repairs?" if (failed_count > 0 or crit_count > 0) else "No issues detected. Agent is certified robust.",
        "baseline_scorecard": baseline,
        "latest_scorecard": latest_sc,
        "findings": [f.dict() if hasattr(f, "dict") else f.model_dump() for f in findings],
        "proposed_plan": proposed_plan,
        "original_code": original_code,
        "proposed_modified_code": repair_preview.get("updated_code", original_code),
        "proposed_diff": repair_preview.get("diff_summary", "# No modifications proposed"),
        "changes_made": repair_preview.get("changes_made", []),
        "fixing_agent_reasoning": repair_preview.get("fixing_agent_reasoning", "")
    }


@router.post("/sessions/start", response_model=RepairSession)
def start_repair_session(payload: StartRepairRequest, background_tasks: BackgroundTasks):
    """Explicitly start the repair loop after user clicks 'Fix Agent' and approves Repair Plan."""
    session = store.repair_sessions.get(payload.session_id)
    if not session:
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
