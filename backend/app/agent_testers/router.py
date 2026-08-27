"""
API Router for Stage Agent Testers & Judges.
Endpoints to trigger on-demand audits, retrieve audit history, and monitor tester health.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.agent_testers.models import (
    StageAuditRequest,
    StageAuditVerdict,
    StageTesterHealth,
    MultiAgentAuditRequest,
    MultiAgentAuditVerdict,
)
from app.agent_testers.stage_tester import stage_tester_orchestrator, STAGE_FALLBACK_MODELS
from app.services.store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent-testers", tags=["Agent Testers & Stage Judges"])


@router.get("/health", response_model=StageTesterHealth)
async def get_tester_health():
    """Inspects the readiness of the Agent Tester subsystem, active models, and local connectivity."""
    return await stage_tester_orchestrator.get_health_status()


@router.get("/fallback-models")
async def get_stage_fallback_models():
    """Returns the dedicated local fallback models configured for each website stage."""
    return STAGE_FALLBACK_MODELS


@router.post("/audit", response_model=StageAuditVerdict)
async def run_stage_audit(request: StageAuditRequest):
    """Executes a dedicated AI judge session to evaluate Stage Input vs Result."""
    try:
        return await stage_tester_orchestrator.audit_stage(request)
    except Exception as e:
        logger.error(f"Stage audit failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stage audit execution failed: {str(e)}")


@router.post("/audit-batch", response_model=MultiAgentAuditVerdict)
async def run_multi_agent_audit(request: MultiAgentAuditRequest):
    """Executes a comparative stage audit across multiple selected agents and synthesizes local model training data."""
    try:
        return await stage_tester_orchestrator.audit_multiple_agents(request)
    except Exception as e:
        logger.error(f"Multi-agent audit failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Multi-agent stage audit failed: {str(e)}")


@router.get("/audits/{agent_id}", response_model=List[StageAuditVerdict])
async def list_agent_stage_audits(
    agent_id: str,
    stage: Optional[str] = Query(None, description="Optional filter by stage name")
):
    """Returns all audit records for a given agent, optionally filtered by stage."""
    audits = store.list_stage_judge_audits(agent_id=agent_id, stage=stage)
    return audits


@router.get("/audits/{agent_id}/latest/{stage}", response_model=Optional[StageAuditVerdict])
async def get_latest_stage_audit(agent_id: str, stage: str):
    """Returns the latest audit record for a specific stage of an agent."""
    audits = store.list_stage_judge_audits(agent_id=agent_id, stage=stage)
    if not audits:
        return None
    return audits[0]

