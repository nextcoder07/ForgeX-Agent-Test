"""
Admin Telemetry & User-Shared Improvement Pipeline API Router.
Allows users to submit evaluation traces and failure clusters to the admin for platform LLM fine-tuning.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user, UserRecord
from app.services.store import store

router = APIRouter(prefix="/telemetry", tags=["Admin Telemetry & Improvements"])


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class TelemetrySubmissionRequest(BaseModel):
    agent_id: str
    evaluation_job_id: Optional[str] = None
    note: Optional[str] = ""
    include_traces: bool = True
    include_scorecard: bool = True


class AdminTelemetryRecord(BaseModel):
    id: str
    user_id: str
    user_email: Optional[str] = None
    agent_id: str
    agent_name: Optional[str] = ""
    evaluation_job_id: Optional[str] = None
    status: str = "submitted"  # submitted, approved_for_training, archived
    note: Optional[str] = ""
    scorecard_composite: Optional[float] = None
    verdicts_count: int = 0
    traces_count: int = 0
    payload: Dict[str, Any] = Field(default_factory=dict)
    submitted_at: str


@router.post("/submit", response_model=AdminTelemetryRecord)
def submit_telemetry_to_admin(
    req: TelemetrySubmissionRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    """Users submit their evaluation run data to ForgeX Admin for model improvements."""
    agent = store.get_agent(req.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")

    eval_id = req.evaluation_job_id
    scorecard = store.get_scorecard(eval_id) if eval_id else None
    verdicts = store.verdicts.get(eval_id, []) if eval_id else []
    traces = store.traces.get(eval_id, []) if eval_id else []

    sub_id = f"sub-{uuid.uuid4().hex[:8]}"
    payload = {
        "agent": agent.model_dump() if hasattr(agent, "model_dump") else agent.dict(),
        "scorecard": scorecard.model_dump() if hasattr(scorecard, "model_dump") else (scorecard.dict() if scorecard else None),
        "verdicts": [v.model_dump() if hasattr(v, "model_dump") else v.dict() for v in verdicts] if req.include_traces else [],
        "traces": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in traces] if req.include_traces else [],
        "note": req.note
    }

    record = AdminTelemetryRecord(
        id=sub_id,
        user_id=current_user.user_id,
        user_email=current_user.email,
        agent_id=req.agent_id,
        agent_name=agent.name,
        evaluation_job_id=eval_id,
        status="submitted",
        note=req.note,
        scorecard_composite=scorecard.composite if scorecard else None,
        verdicts_count=len(verdicts),
        traces_count=len(traces),
        payload=payload,
        submitted_at=_now()
    )

    # Persist in memory / Supabase
    if not hasattr(store, "_telemetry_submissions"):
        store._telemetry_submissions = {}
    store._telemetry_submissions[sub_id] = record

    if store.agents._sb:
        try:
            row = {
                "id": record.id,
                "user_id": record.user_id,
                "user_email": record.user_email,
                "agent_id": record.agent_id,
                "eval_job_id": record.evaluation_job_id,
                "status": record.status,
                "payload": payload,
                "submitted_at": record.submitted_at
            }
            store.agents._sb.table("admin_telemetry_submissions").upsert(row).execute()
        except Exception:
            pass

    return record


@router.get("/admin/submissions", response_model=List[AdminTelemetryRecord])
def list_admin_telemetry_submissions(
    current_user: UserRecord = Depends(get_current_user)
):
    """Admin endpoint to inspect all submitted evaluation records."""
    if not hasattr(store, "_telemetry_submissions"):
        store._telemetry_submissions = {}

    if store.agents._sb:
        try:
            res = store.agents._sb.table("admin_telemetry_submissions").select("*").execute()
            if res.data:
                for r in res.data:
                    sid = r["id"]
                    if sid not in store._telemetry_submissions:
                        p = r.get("payload") or {}
                        sc = p.get("scorecard") or {}
                        store._telemetry_submissions[sid] = AdminTelemetryRecord(
                            id=sid,
                            user_id=r.get("user_id", ""),
                            user_email=r.get("user_email"),
                            agent_id=r.get("agent_id", ""),
                            agent_name=(p.get("agent") or {}).get("name", ""),
                            evaluation_job_id=r.get("eval_job_id"),
                            status=r.get("status", "submitted"),
                            scorecard_composite=sc.get("composite"),
                            verdicts_count=len(p.get("verdicts", [])),
                            traces_count=len(p.get("traces", [])),
                            payload=p,
                            submitted_at=r.get("submitted_at", _now())
                        )
        except Exception:
            pass

    return list(store._telemetry_submissions.values())


@router.post("/admin/submissions/{submission_id}/approve", response_model=AdminTelemetryRecord)
def approve_submission_for_training(
    submission_id: str,
    current_user: UserRecord = Depends(get_current_user)
):
    """Admin approves a submission and exports it to the fine-tuning dataset queue."""
    if not hasattr(store, "_telemetry_submissions"):
        store._telemetry_submissions = {}

    record = store._telemetry_submissions.get(submission_id)
    if not record:
        raise HTTPException(status_code=404, detail="Submission not found")

    record.status = "approved_for_training"
    store._telemetry_submissions[submission_id] = record

    if store.agents._sb:
        try:
            store.agents._sb.table("admin_telemetry_submissions").update({"status": "approved_for_training"}).eq("id", submission_id).execute()
        except Exception:
            pass

    return record
