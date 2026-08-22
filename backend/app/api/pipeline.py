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
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return run
