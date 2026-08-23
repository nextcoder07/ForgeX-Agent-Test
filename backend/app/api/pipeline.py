"""
Pipeline Telemetry & Stage Observability API Router.
"""

from __future__ import annotations

import uuid
import datetime as dt
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

from app.models.pipeline import PipelineRun, PipelineStage, TelemetryEvent
from app.services.store import store

router = APIRouter(prefix="/pipeline", tags=["Pipeline Telemetry"])


class FullEvaluationRequest(BaseModel):
    agent_id: str
    secrets: Optional[Dict[str, str]] = None
    requested_mode: Optional[str] = None

@router.get("/runs", response_model=List[PipelineRun])
def list_pipeline_runs():
    return store.list_pipeline_runs()


@router.get("/runs/{run_id}", response_model=PipelineRun)
def get_pipeline_run(run_id: str):
    run = store.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return run


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


async def _run_full_evaluation_task(pipeline_id: str, agent_id: str, secrets: Dict[str, str], requested_mode: Optional[str]):
    from app.api.scenarios import execute_scenario_generation_run, ScenarioGenerationRequest
    from app.api.executions import _run_sandbox_scenarios_task
    from app.api.evaluations import _run_evaluation_task
    from app.models.execution import ExecutionJob
    from app.models.evaluation import EvaluationJob
    
    agent = store.get_agent(agent_id)
    if not agent:
        return
        
    run = store.get_pipeline_run(pipeline_id)
    if not run:
        return

    def update_stage(stage_index, status, progress, error=None):
        if stage_index < len(run.stages):
            run.stages[stage_index].status = status
            run.stages[stage_index].progress_pct = progress
            if error:
                run.stages[stage_index].error = error
        store.save_pipeline_run(run)

    # Stage 1: Scenarios
    update_stage(0, "running", 10)
    scenarios = store.list_scenarios()
    agent_scenarios = [s for s in scenarios if s.agent_id == agent_id]
    
    if len(agent_scenarios) < 20:
        gen_req = ScenarioGenerationRequest(
            agent_id=agent_id,
            target_count=20 - len(agent_scenarios)
        )
        try:
            gen_res = await execute_scenario_generation_run(gen_req)
            agent_scenarios.extend(gen_res.scenarios)
        except Exception as e:
            update_stage(0, "failed", 100, str(e))
            run.status = "failed"
            store.save_pipeline_run(run)
            return

    update_stage(0, "completed", 100)
    
    # Stage 2: Execution
    update_stage(1, "running", 10)
    scenario_ids = [s.id for s in agent_scenarios]
    exec_job_id = f"exec-{uuid.uuid4().hex[:8]}"
    
    exec_job = ExecutionJob(
        id=exec_job_id,
        agent_id=agent_id,
        agent_name=agent.name,
        status="pending",
        total_scenarios=len(scenario_ids),
        completed_scenarios=0,
        mode=requested_mode or "faithful",
        created_at=_now()
    )
    store.save_execution_job(exec_job)
    
    try:
        await _run_sandbox_scenarios_task(exec_job_id, agent_id, scenario_ids, secrets)
        update_stage(1, "completed", 100)
    except Exception as e:
        update_stage(1, "failed", 100, str(e))
        run.status = "failed"
        store.save_pipeline_run(run)
        return

    # Stage 3: Evaluation
    update_stage(2, "running", 10)
    eval_job_id = f"eval-{uuid.uuid4().hex[:8]}"
    eval_job = EvaluationJob(
        id=eval_job_id,
        agent_id=agent_id,
        agent_version_id=agent.version_label or "v1",
        execution_run_ids=[exec_job_id],
        status="running",
        created_at=_now(),
        started_at=_now(),
        total_traces=len(scenario_ids)
    )
    store.save_evaluation_job(eval_job)
    
    try:
        await _run_evaluation_task(eval_job_id)
        update_stage(2, "completed", 100)
    except Exception as e:
        update_stage(2, "failed", 100, str(e))
        run.status = "failed"
        store.save_pipeline_run(run)
        return

    run.status = "completed"
    run.completed_stages = 3
    run.completed_at = _now()
    store.save_pipeline_run(run)


@router.post("/run-full-evaluation", response_model=PipelineRun)
def run_full_evaluation(payload: FullEvaluationRequest, background_tasks: BackgroundTasks):
    from app.core.dependencies.dependency_resolver import DependencyResolver
    
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")
        
    res_result = DependencyResolver.resolve_mode(
        agent=agent,
        requested_mode=payload.requested_mode,
        provided_secrets=payload.secrets
    )
    
    if not res_result.execution_dependency_binding.all_fulfilled:
        missing = [s.credential_bound or s.capability for s in res_result.execution_dependency_binding.service_bindings if s.status == "MISSING"]
        raise HTTPException(
            status_code=400, 
            detail={
                "message": f"Cannot start pipeline. Missing required credentials.",
                "missing_credentials": missing
            }
        )

    pipeline_id = f"pipe-{uuid.uuid4().hex[:8]}"
    
    stages = [
        PipelineStage(id=f"stg-{uuid.uuid4().hex[:6]}", stage_name="scenario_generation", display_title="1. Scenario Generation", status="queued"),
        PipelineStage(id=f"stg-{uuid.uuid4().hex[:6]}", stage_name="execution", display_title="2. Sandbox Execution", status="queued"),
        PipelineStage(id=f"stg-{uuid.uuid4().hex[:6]}", stage_name="evaluation", display_title="3. LLM Evaluation", status="queued"),
    ]
    
    run = PipelineRun(
        id=pipeline_id,
        agent_id=payload.agent_id,
        agent_name=agent.name,
        status="running",
        total_stages=3,
        completed_stages=0,
        stages=stages,
        started_at=_now()
    )
    store.save_pipeline_run(run)
    
    background_tasks.add_task(
        _run_full_evaluation_task,
        pipeline_id=pipeline_id,
        agent_id=payload.agent_id,
        secrets=payload.secrets or {},
        requested_mode=payload.requested_mode
    )
    
    return run
