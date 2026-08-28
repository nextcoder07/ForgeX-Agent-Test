"""Six-stage registered-agent reliability pipeline and telemetry API."""

from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.dependencies.dependency_resolver import DependencyResolver
from app.core.repair.repair_orchestrator import RepairOrchestrator
from app.models.evaluation import EvaluationJob
from app.models.execution import ExecutionJob
from app.models.pipeline import PipelineRun, PipelineStage, TelemetryEvent
from app.services.store import store
from app.api.executions import _run_sandbox_scenarios_task
from app.api.evaluations import _process_traces_evaluation_job_task

router = APIRouter(prefix="/pipeline", tags=["Pipeline Telemetry"])


class FullEvaluationRequest(BaseModel):
    agent_id: str
    secrets: Optional[Dict[str, str]] = None
    requested_mode: Optional[str] = "simulation"
    scenario_count: int = 20


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


def _new_run(agent_id: str, agent_name: str) -> PipelineRun:
    titles = [
        ("intake", "1. Registered Intake & AST"),
        ("scenarios", "2. Scenario Intelligence"),
        ("dependencies", "3. Dependency & Tool Gateway"),
        ("execution", "4. Sandboxed Execution & Traces"),
        ("evaluation", "5. Hybrid Evaluation & Scorecard"),
        ("remediation", "6. Remediation & Telemetry"),
    ]
    stages = [
        PipelineStage(
            id=f"stg-{uuid.uuid4().hex[:8]}",
            stage_name=name,
            display_title=title,
            model=None,
        )
        for name, title in titles
    ]
    return PipelineRun(
        id=f"pipe-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        agent_name=agent_name,
        status="running",
        total_stages=6,
        stages=stages,
        started_at=_now(),
    )


def _record_event(run: PipelineRun, stage: PipelineStage, event_type: str, message: str, metadata: Dict[str, Any] = None):
    run.events.append(TelemetryEvent(
        id=f"evt-{uuid.uuid4().hex[:8]}",
        stage_id=stage.id,
        timestamp=_now(),
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    ))


def _start_stage(run: PipelineRun, index: int, details: Dict[str, Any] = None):
    stage = run.stages[index]
    stage.status = "running"
    stage.progress_pct = 10
    stage.details.update(details or {})
    _record_event(run, stage, "STAGE_START", f"Started {stage.display_title}", details)


def _finish_stage(run: PipelineRun, index: int, started: float, details: Dict[str, Any] = None):
    stage = run.stages[index]
    stage.status = "completed"
    stage.progress_pct = 100
    stage.duration_ms = round((time.perf_counter() - started) * 1000, 2)
    stage.details.update(details or {})
    _record_event(run, stage, "STAGE_FINISH", f"Completed {stage.display_title}", details)


def _fail_run(run: PipelineRun, index: int, started: float, error: Exception):
    stage = run.stages[index]
    stage.status = "failed"
    stage.progress_pct = 100
    stage.duration_ms = round((time.perf_counter() - started) * 1000, 2)
    stage.error = str(error)
    _record_event(run, stage, "STAGE_FINISH", f"Failed {stage.display_title}", {"error": str(error)})
    run.status = "failed"
    run.completed_at = _now()
    store.save_pipeline_run(run)


async def run_full_6stage_pipeline(
    pipeline_id: str,
    agent_id: str,
    secrets: Dict[str, str],
    requested_mode: str,
    scenario_count: int,
) -> PipelineRun:
    from app.api.evaluations import _process_traces_evaluation_job_task
    from app.api.executions import _run_sandbox_scenarios_task
    from app.api.scenarios import execute_scenario_generation_run
    from app.models.scenario import ScenarioGenerationRequest

    run = store.get_pipeline_run(pipeline_id)
    agent = store.get_agent(agent_id)
    if not run or not agent:
        raise ValueError("Pipeline or registered agent no longer exists")

    # Stage 1: registration is the intake boundary for this pipeline.
    started = time.perf_counter()
    _start_stage(run, 0, {"source": "registered_agent", "artifact_id": agent.artifact_id})
    _finish_stage(run, 0, started, {"runtime": agent.runtime_manifest.get("runtime"), "execution_status": agent.execution_status})
    store.save_pipeline_run(run)

    # Stage 2: generate and persist scenarios for this exact agent.
    started = time.perf_counter()
    _start_stage(run, 1, {"requested_count": scenario_count})
    try:
        generation = await execute_scenario_generation_run(
            ScenarioGenerationRequest(agent_id=agent_id, target_count=scenario_count)
        )
        scenario_ids = [scenario.id for scenario in generation.scenarios if scenario.validation_status != "FAILED_GENERATION"]
        _finish_stage(run, 1, started, {"scenario_count": len(generation.scenarios), "ready_count": generation.ready_count, "generation_run_id": generation.id})
    except Exception as error:
        _fail_run(run, 1, started, error)
        return run
    store.save_pipeline_run(run)

    # Stage 3: resolve execution mode and required credentials.
    started = time.perf_counter()
    _start_stage(run, 2, {"requested_mode": requested_mode})
    try:
        resolution = DependencyResolver.resolve_mode(agent=agent, requested_mode=requested_mode, provided_secrets=secrets)
        binding = resolution.active_binding
        _finish_stage(run, 2, started, {
            "mode": binding.mode.value,
            "provider": binding.executed_provider,
            "model": binding.executed_model,
            "all_fulfilled": resolution.execution_dependency_binding.all_fulfilled,
        })
    except Exception as error:
        _fail_run(run, 2, started, error)
        return run
    store.save_pipeline_run(run)

    # Stage 4: execute selected scenarios and persist sessions/traces.
    started = time.perf_counter()
    _start_stage(run, 3, {"scenario_count": len(scenario_ids)})
    exec_job = ExecutionJob(
        id=f"exec-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        agent_name=agent.name,
        status="pending",
        total_scenarios=len(scenario_ids),
        scenario_ids=scenario_ids,
        execution_mode=binding.mode.value,
        original_model=binding.original_model,
        executed_model=binding.executed_model,
        model_substitution=binding.model_substitution,
        confidence=binding.confidence.upper(),
        created_at=_now(),
    )
    store.save_execution_job(exec_job)
    try:
        _run_sandbox_scenarios_task(
            exec_job.id,
            agent_id,
            scenario_ids,
            binding=binding,
            include_counterfactuals=True,
            secrets=secrets,
        )
        traces = store.traces.get(exec_job.id, [])
        _finish_stage(run, 3, started, {"execution_job_id": exec_job.id, "trace_count": len(traces)})
    except Exception as error:
        _fail_run(run, 3, started, error)
        return run
    store.save_pipeline_run(run)

    # Stage 5: evaluate the exact traces produced by stage 4.
    started = time.perf_counter()
    _start_stage(run, 4, {"trace_count": len(traces)})
    eval_job = EvaluationJob(
        id=f"eval-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        agent_name=agent.name,
        agent_version=agent.version_label,
        status="pending",
        current_step="Evaluation queued",
        total_scenarios=len(traces),
        created_at=_now(),
        execution_mode=binding.mode.value,
        original_model=binding.original_model,
        executed_model=binding.executed_model,
        model_substitution=binding.model_substitution,
        confidence=binding.confidence.upper(),
    )
    store.jobs[eval_job.id] = eval_job
    try:
        _process_traces_evaluation_job_task(eval_job.id, agent_id, traces, binding)
        _finish_stage(run, 4, started, {"evaluation_job_id": eval_job.id, "scorecard": "persisted", "traces_evaluated": len(traces)})
    except Exception as error:
        _fail_run(run, 4, started, error)
        return run
    store.save_pipeline_run(run)

    # Stage 6: prepare, but do not apply, a repair session.
    started = time.perf_counter()
    _start_stage(run, 5)
    try:
        repair_session = RepairOrchestrator.get_or_create_session(agent_id)
        _finish_stage(run, 5, started, {"repair_session_id": repair_session.id, "status": "awaiting_explicit_approval"})
    except Exception as error:
        _fail_run(run, 5, started, error)
        return run

    run.status = "completed"
    run.completed_stages = 6
    run.completed_at = _now()
    run.overall_duration_ms = round((dt.datetime.fromisoformat(run.completed_at.replace("Z", "+00:00")) - dt.datetime.fromisoformat(run.started_at.replace("Z", "+00:00"))).total_seconds() * 1000, 2)
    store.save_pipeline_run(run)
    return run


async def _run_full_pipeline_task(pipeline_id: str, payload: FullEvaluationRequest):
    await run_full_6stage_pipeline(
        pipeline_id, payload.agent_id, payload.secrets or {}, payload.requested_mode or "simulation", payload.scenario_count
    )


@router.get("/runs", response_model=List[PipelineRun])
def list_pipeline_runs():
    return store.list_pipeline_runs()


@router.get("/runs/{run_id}", response_model=PipelineRun)
def get_pipeline_run(run_id: str):
    run = store.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return run


@router.post("/run-full", response_model=PipelineRun)
@router.post("/run-full-evaluation", response_model=PipelineRun)
def run_full_evaluation(payload: FullEvaluationRequest, background_tasks: BackgroundTasks):
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")
    if payload.scenario_count < 1 or payload.scenario_count > 100:
        raise HTTPException(status_code=422, detail="scenario_count must be between 1 and 100")

    run = _new_run(agent.id, agent.name)
    store.save_pipeline_run(run)
    background_tasks.add_task(_run_full_pipeline_task, run.id, payload)
    return run

