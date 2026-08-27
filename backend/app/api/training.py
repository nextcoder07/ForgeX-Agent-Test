"""
Training Dataset Builder API.
Generates SFT, DPO/Preference, and Failure-Recovery datasets from verified execution traces.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from app.models.training import TrainingDataset
from app.core.models_training.dataset_builder import DatasetBuilder
from app.services.store import store
from app.services.activity_log import activity_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/training", tags=["Training Datasets"])
builder = DatasetBuilder()


class GenerateDatasetRequest(BaseModel):
    agent_id: str
    dataset_name: str
    dataset_type: str = "HYBRID"  # SFT, DPO_PREFERENCE, FAILURE_RECOVERY, HYBRID
    evaluation_run_ids: Optional[List[str]] = None


@router.get("/datasets", response_model=List[TrainingDataset])
async def list_datasets(agent_id: Optional[str] = Query(None, description="Filter by agent ID")):
    """List all created training datasets."""
    return store.list_training_datasets(agent_id)


@router.get("/datasets/{dataset_id}", response_model=TrainingDataset)
async def get_dataset(dataset_id: str):
    """Get dataset details and sample records."""
    ds = store.get_training_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@router.post("/datasets/generate", response_model=TrainingDataset)
async def generate_dataset(req: GenerateDatasetRequest):
    """Compile a new training dataset from execution trajectories and evaluation verdicts."""
    agent = store.get_agent(req.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")

    # Collect verdicts and traces from specified evaluation runs or all runs for agent
    all_verdicts = []
    all_traces = []

    target_eval_ids = req.evaluation_run_ids
    if not target_eval_ids:
        target_eval_ids = [sc.evaluation_id for sc in store.scorecards.values() if sc.agent_id == req.agent_id]

    for eval_id in target_eval_ids:
        all_verdicts.extend(store.verdicts.get(eval_id, []))
        all_traces.extend(store.traces.get(eval_id, []))

    scenarios = [s for s in store.list_scenarios() if s.agent_id == req.agent_id]
    if not scenarios:
        scenarios = store.list_scenarios()[:10]

    dataset = builder.build_dataset_from_runs(
        agent=agent,
        dataset_name=req.dataset_name,
        scenarios=scenarios,
        verdicts=all_verdicts,
        traces=all_traces,
        dataset_type=req.dataset_type
    )

    store.save_training_dataset(dataset)
    activity_log.emit(
        category="RUNTIME",
        action="DATASET_COMPILED",
        detail=f"Compiled training dataset '{dataset.name}' with {dataset.example_count} examples ({dataset.dataset_type})",
        status="success"
    )
    return dataset


@router.get("/datasets/{dataset_id}/export")
async def export_dataset_jsonl(dataset_id: str, format_type: str = Query("ALL", description="ALL, SFT, DPO, RECOVERY")):
    """Export dataset as a JSONL file download."""
    ds = store.get_training_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    jsonl_content = builder.export_as_jsonl(ds, format_type)
    return Response(
        content=jsonl_content,
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": f"attachment; filename={ds.name.lower().replace(' ', '_')}_{format_type.lower()}.jsonl"}
    )


# ── Training Jobs & Model Lifecycle Endpoints ───────────────────────────────

from app.models.model_training_job import TrainingJob, ModelVersionRecord, HardwarePreflight
from app.core.models_training.training_orchestrator import TrainingOrchestrator
from app.core.models_training.hardware_preflight_engine import HardwarePreflightEngine
from fastapi import BackgroundTasks

orchestrator = TrainingOrchestrator()
preflight_engine = HardwarePreflightEngine()


class StartTrainingJobRequest(BaseModel):
    agent_id: str
    model_connection_id: str
    dataset_id: str
    training_method: str = "QLORA_4BIT"
    epochs: int = 3
    learning_rate: float = 2e-4
    lora_r: int = 16


@router.get("/hardware-preflight", response_model=HardwarePreflight)
async def get_hardware_preflight(model_name: str = Query("Qwen2.5-Coder-7B")):
    """Evaluate GPU memory footprint and QLoRA training feasibility."""
    return preflight_engine.evaluate_hardware(model_name=model_name)


@router.post("/jobs/start", response_model=TrainingJob)
async def start_training_job(req: StartTrainingJobRequest, background_tasks: BackgroundTasks):
    """Launch a model fine-tuning job in the background."""
    job = orchestrator.create_training_job(
        agent_id=req.agent_id,
        model_connection_id=req.model_connection_id,
        dataset_id=req.dataset_id,
        training_method=req.training_method,
        epochs=req.epochs,
        learning_rate=req.learning_rate,
        lora_r=req.lora_r
    )
    # Run async training loop in background
    background_tasks.add_task(orchestrator.execute_training_job_async, job.id)
    return job


@router.get("/jobs", response_model=List[TrainingJob])
async def list_training_jobs(agent_id: Optional[str] = Query(None)):
    """List all training jobs with status and progress."""
    return store.list_training_jobs(agent_id)


@router.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_training_job(job_id: str):
    """Get training job status, loss curve, and checkpoints."""
    job = store.get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return job


@router.post("/jobs/{job_id}/promote", response_model=ModelVersionRecord)
async def promote_model_version(job_id: str):
    """Promote the trained model adapter to be active for the agent."""
    try:
        return orchestrator.promote_model_version(job_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/models/versions", response_model=List[ModelVersionRecord])
async def list_model_versions(agent_id: Optional[str] = Query(None)):
    """List all versioned model adapters registered for agents."""
    return store.list_model_versions(agent_id)
