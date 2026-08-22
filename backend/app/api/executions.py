"""
Sandbox Execution & Pipeline Execution API Router.
Supports execution mode resolution (Faithful, Compatible, Simulation), model bindings,
and sandboxed execution trace generation.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.execution import ExecutionJob, ExecutionTrace
from app.models.dependency_model import ExecutionMode, ExecutionModelBinding
from app.services.store import store
from app.core.sandbox.sandbox_manager import SandboxManager
from app.core.dependencies.dependency_resolver import DependencyResolver
from app.core.evaluation.counterfactual import replay_counterfactual_control
from app.services.activity_log import activity_log

router = APIRouter(prefix="/executions", tags=["Executions"])


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RunExecutionRequest(BaseModel):
    agent_id: str
    scenario_ids: List[str]
    requested_mode: Optional[str] = "faithful"  # "faithful", "compatible", "simulation"
    include_counterfactuals: bool = True
    secrets: Dict[str, str] = {}


def _run_sandbox_scenarios_task(
    job_id: str,
    agent_id: str,
    scenario_ids: List[str],
    binding: ExecutionModelBinding,
    include_counterfactuals: bool,
    secrets: Dict[str, str]
):
    """Background task to execute scenarios inside SandboxManager and save traces."""
    agent = store.get_agent(agent_id)
    job = store.get_execution_job(job_id)
    if not agent or not job:
        return

    job.status = "running"
    store.save_execution_job(job)

    manager = SandboxManager()
    traces: List[ExecutionTrace] = []

    activity_log.emit(
        category="SANDBOX",
        action="BATCH_RUN_START",
        detail=f"Executing {len(scenario_ids)} scenarios under mode '{binding.mode.value}' (Model: {binding.executed_model}) for agent {agent.name}",
        request_summary=f"Job ID: {job_id} | Substitution: {'YES' if binding.model_substitution else 'NO'} | Fidelity: {binding.fidelity.value}",
        status="success"
    )

    for idx, sc_id in enumerate(scenario_ids):
        sc = store.scenarios.get(sc_id)
        if not sc:
            continue

        activity_log.emit(
            category="SANDBOX",
            action="RUN_SCENARIO",
            detail=f"[{idx+1}/{len(scenario_ids)}] Sandbox running scenario: {sc.title} ({sc.category.value})",
            status="success"
        )

        try:
            # 1. Create unique ephemeral sandbox
            sb_instance = manager.create_sandbox(agent_id=agent.id, scenario_id=sc.id)
            manager.install_dependencies(sb_instance, agent)
            manager.inject_allowed_environment(sb_instance, allowed_env={"MODE": binding.mode.value}, secrets=secrets)

            # 2. Run primary trace inside sandbox
            t_primary = manager.run_agent(sb_instance, agent, sc, binding)
            traces.append(t_primary)

            # 3. Clean up sandbox instance
            manager.destroy_sandbox(sb_instance.sandbox_id)

            # 4. Run counterfactual control if enabled
            if include_counterfactuals and (sc.category.value in ["adversarial", "security", "safety"]):
                activity_log.emit(
                    category="SANDBOX",
                    action="COUNTERFACTUAL_RUN",
                    detail=f"Replaying counterfactual control for scenario: {sc.title}",
                    status="warning"
                )
                t_cf = replay_counterfactual_control(agent, sc, t_primary)
                traces.append(t_cf)

        except Exception as e:
            activity_log.emit(
                category="SANDBOX",
                action="RUN_ERROR",
                detail=f"Error executing scenario {sc.title}: {str(e)}",
                status="error"
            )

        job.completed_scenarios = idx + 1
        store.save_execution_job(job)

    # Store traces mapped under the job_id
    store.traces[job_id] = traces

    job.status = "completed"
    job.finished_at = _now()
    store.save_execution_job(job)

    activity_log.emit(
        category="SANDBOX",
        action="BATCH_RUN_COMPLETE",
        detail=f"Sandbox execution job {job_id} completed successfully.",
        response_summary=f"Total traces collected: {len(traces)}",
        status="success"
    )


@router.post("/run", response_model=ExecutionJob)
async def start_execution_job(payload: RunExecutionRequest, background_tasks: BackgroundTasks):
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    if not payload.scenario_ids:
        raise HTTPException(status_code=422, detail="No scenarios selected for execution")

    job_id = f"exec-{uuid.uuid4().hex[:8]}"

    # Resolve execution mode & bind model
    req_mode_enum = None
    if payload.requested_mode:
        try:
            req_mode_enum = ExecutionMode(payload.requested_mode.lower())
        except Exception:
            req_mode_enum = ExecutionMode.FAITHFUL

    res_result = DependencyResolver.resolve_mode(
        agent=agent,
        requested_mode=req_mode_enum,
        provided_secrets=payload.secrets,
        execution_id=job_id
    )
    binding = res_result.active_binding
    store.save_execution_model_binding(binding)

    job = ExecutionJob(
        id=job_id,
        agent_id=payload.agent_id,
        agent_name=agent.name,
        status="pending",
        total_scenarios=len(payload.scenario_ids),
        completed_scenarios=0,
        execution_mode=binding.mode.value,
        original_model=binding.original_model,
        executed_model=binding.executed_model,
        model_substitution=binding.model_substitution,
        confidence=binding.confidence.upper(),
        created_at=_now(),
    )
    store.save_execution_job(job)

    # Queue background task for non-blocking execution
    background_tasks.add_task(
        _run_sandbox_scenarios_task,
        job_id,
        payload.agent_id,
        payload.scenario_ids,
        binding,
        payload.include_counterfactuals,
        payload.secrets
    )

    return job


@router.get("/jobs", response_model=List[ExecutionJob])
def list_execution_jobs():
    """List all manual sandbox execution jobs."""
    return store.list_execution_jobs()


@router.get("/jobs/{job_id}", response_model=ExecutionJob)
def get_execution_job(job_id: str):
    """Retrieve execution job status and metadata."""
    job = store.get_execution_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Execution job '{job_id}' not found")
    return job


@router.get("/jobs/{job_id}/traces", response_model=List[ExecutionTrace])
def get_execution_job_traces(job_id: str):
    """Retrieve all execution traces generated by the manual execution job."""
    return store.traces.get(job_id, [])


@router.get("/jobs/{job_id}/binding", response_model=ExecutionModelBinding)
def get_execution_binding(job_id: str):
    """Retrieve execution model binding record detailing original vs executed model and substitution status."""
    binding = store.get_execution_model_binding(job_id)
    if not binding:
        raise HTTPException(status_code=404, detail=f"Execution binding for '{job_id}' not found")
    return binding
