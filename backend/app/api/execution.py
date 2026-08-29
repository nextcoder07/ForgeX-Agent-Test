"""
Kaggle-Style Trajectory Execution, Event Sourcing, and Benchmark API Router.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.execution import ExecutionSession, ExecutionStep, ExecutionMetrics, BenchmarkRecord
from app.services.store import store
from app.core.execution.controller import ExecutionController
from app.core.execution.replay_engine import ReplayEngine
from app.core.evaluation.trajectory_evaluator import TrajectoryEvaluator
from app.services.activity_log import activity_log

from app.models.dependency_model import ProvideCredentialsRequest
from app.core.dependencies.dependency_resolver import DependencyResolver

router = APIRouter(prefix="/execution", tags=["Execution"])


@router.get("/preflight/{agent_id}")
async def get_agent_execution_preflight(agent_id: str):
    """Fetches preflight requirements, credential demands, sandbox status, and available scenarios for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agent_scenarios = [s for s in store.list_scenarios(agent_id) if getattr(s, 'validation_status', '') != 'FAILED_GENERATION']

    sandbox_specs = store.list_sandbox_specs()
    sandbox_spec = next((spec for spec in sandbox_specs if spec.agent_id == agent_id), None)

    prompt = DependencyResolver.evaluate_execution_credential_demands(agent=agent)

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "domain": agent.domain,
        "sandbox_status": sandbox_spec.status if sandbox_spec else "READY",
        "sandbox_blockers": sandbox_spec.blockers if sandbox_spec else [],
        "scenarios_count": len(agent_scenarios),
        "scenarios": [
            {
                "id": s.id,
                "title": s.title,
                "category": s.category.value if hasattr(s.category, "value") else str(s.category),
                "purpose": s.purpose
            } for s in agent_scenarios
        ],
        "credential_prompt": prompt.dict(),
        "ready_for_execution": prompt.all_fulfilled and (not sandbox_spec or sandbox_spec.status != "BLOCKED")
    }


class StartExecutionRequest(BaseModel):
    agent_id: str
    scenario_id: str
    evaluation_run_id: Optional[str] = None
    provided_secrets: Dict[str, str] = {}


@router.post("/sessions/start")
async def start_execution_session(payload: StartExecutionRequest):
    """Launches a sandboxed execution session for an agent and scenario after verifying API key credential demands."""
    from app.core.llm.key_manager import UnifiedKeyManager
    UnifiedKeyManager().reset_rotation()

    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    scenario = store.get_scenario(payload.scenario_id) or next((s for s in store.list_scenarios(payload.agent_id) if s.id == payload.scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{payload.scenario_id}' not found")

    if (getattr(scenario, 'validation_status', '') != 'EXECUTABLE' 
        or getattr(scenario, 'critic_status', '') != 'CRITIC_APPROVED'
        or getattr(scenario, 'agent_id', '') != payload.agent_id
        or getattr(scenario, 'agent_version_id', None) != getattr(agent, 'current_version_id', None)):
        raise HTTPException(
            status_code=400,
            detail="Only executable and critic-approved scenarios matching the current agent version can enter the execution queue."
        )

    # Gatekeeper Check 0: Sandbox Status Check
    sandbox_specs = store.list_sandbox_specs()
    sandbox_spec = next((spec for spec in sandbox_specs if spec.agent_id == agent.id), None)
    if not sandbox_spec or sandbox_spec.status != "READY":
        blockers_str = ", ".join(sandbox_spec.blockers) if (sandbox_spec and sandbox_spec.blockers) else "Sandbox specification unavailable"
        activity_log.emit(
            category="SANDBOX",
            action="EXECUTION_BLOCKED",
            detail=f"Execution blocked for agent {agent.name}: {blockers_str}",
            status="warning"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Sandbox specification unavailable. Blockers: {blockers_str}"
        )

    # 1. Gatekeeper Check: Evaluate Credential Demands
    prompt = DependencyResolver.evaluate_execution_credential_demands(
        agent=agent,
        provided_secrets=payload.provided_secrets
    )

    if not prompt.all_fulfilled:
        activity_log.emit(
            category="SANDBOX",
            action="CREDS_REQUIRED",
            detail=f"Execution blocked for agent {agent.name}: {prompt.message}",
            status="warning"
        )
        return {
            "session_id": prompt.session_id,
            "status": "CREDS_REQUIRED",
            "message": prompt.message,
            "credential_prompt": prompt.dict()
        }

    activity_log.emit(
        category="SANDBOX",
        action="SESSION_START",
        detail=f"Starting execution session for agent {agent.name} on scenario: {scenario.title}",
        status="success"
    )

    result = await ExecutionController.run_session(agent, scenario, payload.evaluation_run_id)

    activity_log.emit(
        category="SANDBOX",
        action="SESSION_COMPLETE",
        detail=f"Completed execution session: {result['session_id']} ({result['trajectory_steps']} steps recorded)",
        status="success"
    )

    return result


@router.post("/sessions/{session_id}/provide-credentials")
async def provide_credentials_and_resume_execution(session_id: str, payload: ProvideCredentialsRequest, agent_id: str, scenario_id: str):
    """Submits user API keys interactively to fulfill missing credential demands and start execution."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    scenarios = store.list_scenarios()
    scenario = next((s for s in scenarios if s.id == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    # Re-evaluate credential demands with newly submitted keys
    prompt = DependencyResolver.evaluate_execution_credential_demands(
        agent=agent,
        provided_secrets=payload.credentials,
        session_id=session_id
    )

    if not prompt.all_fulfilled:
        return {
            "session_id": session_id,
            "status": "CREDS_REQUIRED",
            "message": prompt.message,
            "credential_prompt": prompt.dict()
        }

    result = await ExecutionController.run_session(agent, scenario)
    return result


@router.get("/sessions/{session_id}", response_model=ExecutionSession)
def get_execution_session(session_id: str):
    """Retrieve metadata for a specific execution session."""
    session = store.get_execution_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Execution session '{session_id}' not found")
    return session


@router.get("/sessions/{session_id}/trajectory", response_model=List[ExecutionStep])
def get_session_trajectory(session_id: str):
    """Retrieve sequential event-sourcing trajectory steps for an execution session."""
    session = store.get_execution_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Execution session '{session_id}' not found")
    return store.get_execution_steps(session_id)


@router.get("/sessions/{session_id}/metrics", response_model=ExecutionMetrics)
def get_session_metrics(session_id: str):
    """Retrieve execution performance metrics (steps, latency, tool calls, cost)."""
    metrics = store.get_execution_metrics(session_id)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"Metrics for execution session '{session_id}' not found")
    return metrics


@router.post("/sessions/{session_id}/replay")
def replay_execution_session(session_id: str):
    """Reconstructs and replays an execution trajectory for regression diffing."""
    result = ReplayEngine.replay_session(session_id)
    if not result.get("reconstructed"):
        raise HTTPException(status_code=404, detail=result.get("error", "Replay failed"))
    return result


@router.get("/benchmark/records", response_model=List[BenchmarkRecord])
def list_benchmark_records():
    """List stored benchmark dataset records for ML training and model comparisons."""
    return store.list_benchmark_records()
