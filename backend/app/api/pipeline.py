"""
Pipeline Telemetry & Stage Observability API Router.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException
from app.models.pipeline import PipelineRun
from app.services.store import store

router = APIRouter(prefix="/pipeline", tags=["Pipeline Telemetry"])


@router.get("/runs", response_model=List[PipelineRun])
def list_pipeline_runs():
    return store.list_pipeline_runs()


@router.get("/runs/{run_id}", response_model=PipelineRun)
def get_pipeline_run(run_id: str):
    run = store.get_pipeline_run(run_id)
    if not run:
        # Generate default demonstration pipeline snapshot
        from app.core.pipeline.monitor import PipelineTracker
        tracker = PipelineTracker(agent_id="agent-cust-v1", agent_name="Customer Support Agent")
        for i in range(10):
            tracker.start_stage(i)
            tracker.complete_stage(i, duration_ms=45.0 + i * 20, input_tokens=150 + i * 30, output_tokens=80 + i * 20)
        snap = tracker.get_run_snapshot()
        store.save_pipeline_run(snap)
        return snap
    return run
