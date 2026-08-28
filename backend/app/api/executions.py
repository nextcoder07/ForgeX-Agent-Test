"""
Sandbox Execution & Pipeline Execution API Router.
Supports execution mode resolution (Faithful, Compatible, Simulation), model bindings,
and sandboxed execution trace generation.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.execution import (
    ExecutionJob, ExecutionTrace, ExecutionRun, ExecutionSession,
    ExecutionAction, ExecutionPreflight, PreExecutionSnapshot,
    PostExecutionSnapshot, ObservationSummary, ExecutionLifecycleState,
    ExecutionFailureState, EvidencePackage, TraceEvent
)
from app.core.execution.preflight import run_scenario_preflight
from app.models.dependency_model import ExecutionMode, ExecutionModelBinding
from app.services.store import store
from app.core.sandbox.sandbox_manager import SandboxManager
from app.core.dependencies.dependency_resolver import DependencyResolver
from app.core.evaluation.counterfactual import replay_counterfactual_control
from app.services.activity_log import activity_log
import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/executions", tags=["Executions"])


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RunExecutionRequest(BaseModel):
    agent_id: str
    scenario_ids: List[str]
    requested_mode: Optional[str] = "faithful"  # "faithful", "compatible", "simulation"
    include_counterfactuals: bool = True
    run_sync: bool = False
    secrets: Dict[str, str] = Field(default_factory=dict)


class PreflightExecutionRequest(BaseModel):
    agent_id: str
    scenario_ids: List[str]
    secrets: Dict[str, str] = Field(default_factory=dict)


@router.post("/preflight")
def check_execution_preflight(payload: PreflightExecutionRequest):
    """Run preflight validation check and variable resolution before starting execution."""
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    scenarios = [store.get_scenario(sc_id) for sc_id in payload.scenario_ids if store.get_scenario(sc_id)]
    if not scenarios:
        raise HTTPException(status_code=404, detail="No valid scenarios found for preflight check")

    preflight_results = []
    
    # 1. Dependency Mode Check
    res_result = DependencyResolver.resolve_mode(
        agent=agent,
        requested_mode=None, # Will auto-select best mode
        provided_secrets=payload.secrets
    )
    overall_ready = res_result.execution_dependency_binding.all_fulfilled
    missing = [s.credential_bound or s.capability for s in res_result.execution_dependency_binding.service_bindings if s.status == "MISSING"]
    
    if not overall_ready:
        return {
            "agent_id": agent.id,
            "overall_status": "BLOCKED",
            "scenarios_checked": 0,
            "preflight_results": [],
            "missing_credentials": missing
        }

    # 2. Scenario Variable Check
    for sc in scenarios:
        pf_res = run_scenario_preflight(
            scenario=sc,
            agent=agent,
            execution_run_id="",
            provided_variables=payload.secrets
        )
        if not pf_res.is_ready:
            overall_ready = False
        preflight_results.append(pf_res.model_dump() if hasattr(pf_res, "model_dump") else pf_res.dict())

    return {
        "agent_id": agent.id,
        "overall_status": "READY" if overall_ready else "BLOCKED",
        "scenarios_checked": len(preflight_results),
        "preflight_results": preflight_results
    }


def _run_sandbox_scenarios_task(
    job_id: str,
    agent_id: str,
    scenario_ids: List[str],
    binding: Optional[Any] = None,
    include_counterfactuals: bool = True,
    secrets: Dict[str, str] = None
):
    """Background or sync task to execute scenarios inside SandboxManager, collect evidence, and seal execution."""
    if secrets is None:
        secrets = {}
    
    agent = store.get_agent(agent_id)
    job = store.get_execution_job(job_id)
    if not agent or not job:
        return

    # Automatically resolve user-selected AI model connections from Setup screen
    if agent.runtime_manifest and "model_bindings" in agent.runtime_manifest:
        model_bindings = agent.runtime_manifest.get("model_bindings", {})
        for slot_id, conn_id in model_bindings.items():
            if conn_id and conn_id != "system_default" and conn_id != "unbound":
                conn = store.get_model_connection(conn_id)
                if conn and conn.api_key:
                    provider_prefix = conn.provider.upper() if conn.provider else "OPENAI"
                    secrets[f"{provider_prefix}_API_KEY"] = conn.api_key
                    if conn.base_url:
                        secrets[f"{provider_prefix}_BASE_URL"] = conn.base_url
                    if conn.model_identifier:
                        secrets[f"{provider_prefix}_MODEL"] = conn.model_identifier

    job.status = "running"
    store.save_execution_job(job)


    # Create ExecutionRun batch record
    exec_run = ExecutionRun(
        id=job_id,
        agent_id=agent_id,
        agent_version_id=agent.version_label,
        scenario_ids=scenario_ids,
        execution_mode=getattr(binding, "mode", ExecutionMode.FAITHFUL).value if binding else "faithful",
        status=ExecutionLifecycleState.RUNNING.value,
        started_at=_now(),
        requested_count=len(scenario_ids),
        ready_count=len(scenario_ids)
    )
    store.save_execution_run(exec_run)

    manager = SandboxManager()
    traces: List[ExecutionTrace] = []

    mode_val = getattr(getattr(binding, "mode", None), "value", "subprocess")
    model_name = getattr(binding, "executed_model", "default")
    substitution_flag = "YES" if getattr(binding, "model_substitution", False) else "NO"

    activity_log.emit(
        category="SANDBOX",
        action="BATCH_RUN_START",
        detail=f"Executing {len(scenario_ids)} scenarios under mode '{mode_val}' (Model: {model_name}) for agent {agent.name}",
        request_summary=f"Job ID: {job_id} | Substitution: {substitution_flag}",
        status="success"
    )

    try:
        for idx, sc_id in enumerate(scenario_ids):
            sc = store.get_scenario(sc_id)
            if not sc:
                continue
            if getattr(sc, 'validation_status', '') == 'FAILED_GENERATION':
                continue

            session_id = f"sess-{uuid.uuid4().hex[:8]}"
            session = ExecutionSession(
                id=session_id,
                execution_run_id=job_id,
                agent_version_id=agent.version_label,
                scenario_id=sc.id,
                status=ExecutionLifecycleState.PREFLIGHT.value,
                started_at=_now()
            )
            store.save_execution_session(session)

            # Preflight
            pf_res = run_scenario_preflight(scenario=sc, agent=agent, execution_run_id=job_id, provided_variables=secrets)
            if pf_res.preflight_record:
                session.preflight = pf_res.preflight_record

            if not pf_res.is_ready:
                session.status = ExecutionLifecycleState.FINALIZING.value
                session.failure_state = ExecutionFailureState.BLOCKED.value
                session.finished_at = _now()
                store.save_execution_session(session)
                exec_run.blocked_count += 1
                store.save_execution_run(exec_run)

                # Record blocked trace so UI displays scenario finding immediately
                blocked_trace = ExecutionTrace(
                    id=f"trc-{uuid.uuid4().hex[:10]}",
                    scenario_id=sc.id,
                    agent_id=agent.id,
                    agent_version=agent.version_label,
                    status="BLOCKED",
                    events=[
                        TraceEvent(timestamp=_now(), role="preflight", content=f"Preflight blocked: {', '.join(getattr(pf_res, 'blockers', []) or ['Missing required dependencies'])}"),
                    ],
                    is_counterfactual=False
                )
                traces.append(blocked_trace)
                store.traces[job_id] = list(traces)
                job.completed_scenarios = idx + 1
                store.save_execution_job(job)
                continue

            # Build Sandbox
            session.status = ExecutionLifecycleState.SANDBOX_BUILDING.value
            store.save_execution_session(session)

            try:
                sb_instance = manager.create_sandbox(agent_id=agent.id, scenario_id=sc.id)
                manager.install_dependencies(sb_instance, agent)
                manager.inject_allowed_environment(sb_instance, allowed_env={"MODE": mode_val}, secrets=secrets)

                # Pre-Execution Snapshot
                session.pre_snapshot = PreExecutionSnapshot(
                    filesystem_state={"workspace": sb_instance.temp_dir},
                    environment_metadata={"MODE": mode_val},
                    database_fixture_state=sc.initial_state,
                    network_policy={"allow": ["localhost"], "default": "DENY"},
                    timestamp=_now()
                )

                session.status = ExecutionLifecycleState.RUNNING.value
                store.save_execution_session(session)

                # Primary Execution Trace
                t_primary = manager.run_agent(sb_instance, agent, sc, binding)
                traces.append(t_primary)

                # Post-Execution Snapshot
                session.post_snapshot = PostExecutionSnapshot(
                    filesystem_state={"workspace": sb_instance.temp_dir},
                    modified_files=[],
                    state_diffs=[],
                    process_exit_code=0,
                    timestamp=_now()
                )

                # Build 4-Layer Action Evidence Records
                actions: List[ExecutionAction] = []
                for seq, tc in enumerate(t_primary.tool_calls):
                    pol_decision = tc.routing_decision if tc.routing_decision in ["ALLOW", "BLOCK", "REDIRECT"] else ("BLOCK" if tc.status == "BLOCKED_POLICY" else "ALLOW")
                    act = ExecutionAction(
                        id=f"act-{session_id}-{seq+1}",
                        execution_session_id=session_id,
                        sequence=seq + 1,
                        action_type="TOOL_CALL",
                        target=tc.tool_name,
                        attempt_payload=tc.arguments,
                        policy_decision=pol_decision,
                        policy_reason=tc.policy_reason,
                        executed=(pol_decision != "BLOCK"),
                        result_status=tc.status,
                        execution_result=tc.result,
                        side_effect_detected=tc.actual_side_effect_occurred,
                        evaluation_status="NOT_EVALUATED",
                        timestamp=_now()
                    )
                    actions.append(act)
                    store.save_execution_action(act)

                # Build EvidencePackage
                obs_sum = getattr(t_primary, "observation_summary", None) or ObservationSummary()
                traj_hash = getattr(t_primary, "trajectory_hash", None) or f"hash-{uuid.uuid4().hex[:8]}"

                evidence_pkg = EvidencePackage(
                    session_id=session_id,
                    scenario_id=sc.id,
                    agent_version_id=agent.version_label,
                    observation_summary=obs_sum,
                    evidence_references=[f"ref-act-{a.id}" for a in actions],
                    trajectory_hash=traj_hash,
                    sealing_timestamp=_now()
                )

                # Build Canonical Evidence Graph
                try:
                    from app.models.canonical_data_models import (
                        EvidenceGraph, EvidenceNode, EvidenceEdge, EvidenceNodeType, EvidenceEdgeType
                    )

                    graph_nodes: List[EvidenceNode] = []
                    graph_edges: List[EvidenceEdge] = []

                    user_msg = (sc.user_messages or ["No prompt"])[0] if sc.user_messages else "No prompt"
                    u_node = EvidenceNode(
                        id=f"node-user-{session_id}",
                        node_type=EvidenceNodeType.USER_INPUT,
                        label=f"User Prompt: {str(user_msg)[:80]}",
                        timestamp=session.started_at,
                        data={"full_prompt": str(user_msg)}
                    )
                    graph_nodes.append(u_node)
                    prev_node_id = u_node.id

                    for act in actions:
                        attempt_node = EvidenceNode(
                            id=f"node-attempt-{act.id}",
                            node_type=EvidenceNodeType.ACTION_ATTEMPT,
                            label=f"Attempt: {act.target}",
                            timestamp=act.timestamp or _now(),
                            data={"payload": act.attempt_payload}
                        )
                        graph_nodes.append(attempt_node)
                        graph_edges.append(EvidenceEdge(
                            source_node_id=prev_node_id,
                            target_node_id=attempt_node.id,
                            edge_type=EvidenceEdgeType.CAUSES,
                            description="Triggered action attempt"
                        ))

                        pol_str = act.policy_decision if isinstance(act.policy_decision, str) else (act.policy_decision.get("decision", "ALLOW") if isinstance(act.policy_decision, dict) else str(act.policy_decision))
                        is_viol = (pol_str == "BLOCK" or act.result_status == "BLOCKED_POLICY")
                        pol_node = EvidenceNode(
                            id=f"node-policy-{act.id}",
                            node_type=EvidenceNodeType.POLICY_DECISION,
                            label=f"Policy Gate: {pol_str}",
                            timestamp=act.timestamp or _now(),
                            data={"decision": act.policy_decision, "reason": act.policy_reason},
                            is_violation=is_viol
                        )
                        graph_nodes.append(pol_node)
                        graph_edges.append(EvidenceEdge(
                            source_node_id=attempt_node.id,
                            target_node_id=pol_node.id,
                            edge_type=EvidenceEdgeType.EVALUATES,
                            description=act.policy_reason or "Policy evaluated"
                        ))
                        prev_node_id = pol_node.id

                    canonical_evidence_graph = EvidenceGraph(
                        scenario_id=sc.id,
                        execution_session_id=session_id,
                        nodes=graph_nodes,
                        edges=graph_edges,
                        sealed_hash=traj_hash,
                        created_at=_now()
                    )
                    session.evidence_graph = canonical_evidence_graph.model_dump() if hasattr(canonical_evidence_graph, "model_dump") else canonical_evidence_graph.dict()
                except Exception as e:
                    logger.warning(f"Could not build canonical evidence graph for session {session_id}: {e}")

                session.actions = actions
                session.observation_summary = obs_sum
                session.trajectory_hash = traj_hash
                session.evidence_package = evidence_pkg
                session.status = ExecutionLifecycleState.EVIDENCE_SEALED.value
                session.finished_at = _now()
                store.save_execution_session(session)

                # Clean up sandbox
                manager.destroy_sandbox(sb_instance.sandbox_id)

                # Replay counterfactual if required
                cat_val = sc.category.value if hasattr(sc.category, "value") else str(sc.category)
                if include_counterfactuals and (cat_val in ["adversarial", "security", "safety"]):
                    t_cf = replay_counterfactual_control(agent, sc, t_primary)
                    traces.append(t_cf)

                exec_run.completed_count += 1

            except Exception as e:
                session.status = ExecutionLifecycleState.FINALIZING.value
                session.failure_state = ExecutionFailureState.FAILED_EXECUTION.value
                session.finished_at = _now()
                store.save_execution_session(session)
                exec_run.failed_count += 1

                failed_trace = ExecutionTrace(
                    id=f"trc-{uuid.uuid4().hex[:10]}",
                    scenario_id=sc.id,
                    agent_id=agent.id,
                    agent_version=agent.version_label,
                    status="FAILED",
                    events=[
                        TraceEvent(timestamp=_now(), role="error", content=f"Execution error: {str(e)}"),
                    ],
                    is_counterfactual=False
                )
                traces.append(failed_trace)

                activity_log.emit(
                    category="SANDBOX",
                    action="RUN_ERROR",
                    detail=f"Error executing scenario {sc.title}: {str(e)}",
                    status="error"
                )

            store.traces[job_id] = list(traces)
            job.completed_scenarios = idx + 1
            store.save_execution_job(job)

    finally:
        job.completed_scenarios = len(scenario_ids)
        store.traces[job_id] = list(traces)
        job.status = "completed"
        job.finished_at = _now()
        store.save_execution_job(job)

        exec_run.status = ExecutionLifecycleState.EVIDENCE_SEALED.value
        exec_run.finished_at = _now()
        store.save_execution_run(exec_run)

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

    missing_ids = [sc_id for sc_id in payload.scenario_ids if not store.get_scenario(sc_id)]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Scenarios not found in storage: {missing_ids}")

    job_id = f"exec-{uuid.uuid4().hex[:8]}"

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
    
    if not res_result.execution_dependency_binding.all_fulfilled:
        # Gracefully auto-fallback to COMPATIBLE mode with platform test models instead of hard blocking
        res_result = DependencyResolver.resolve_mode(
            agent=agent,
            requested_mode=ExecutionMode.COMPATIBLE,
            provided_secrets=payload.secrets,
            execution_id=job_id
        )
        if not res_result.execution_dependency_binding.all_fulfilled:
            res_result = DependencyResolver.resolve_mode(
                agent=agent,
                requested_mode=ExecutionMode.SIMULATION,
                provided_secrets=payload.secrets,
                execution_id=job_id
            )

    binding = res_result.active_binding or ExecutionModelBinding(
        id=f"bind-{job_id}",
        execution_id=job_id,
        original_model="default",
        executed_model="ForgeX Test Model",
        original_provider="default",
        executed_provider="platform_test_pool",
        mode=ExecutionMode.FAITHFUL,
        model_substitution=False,
        reason="Auto-resolved with platform defaults",
        confidence="high",
        created_at=_now()
    )
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

    if payload.run_sync:
        _run_sandbox_scenarios_task(
            job_id,
            payload.agent_id,
            payload.scenario_ids,
            binding,
            payload.include_counterfactuals,
            payload.secrets
        )
        return store.get_execution_job(job_id) or job
    else:
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


@router.get("/sessions/{session_id}")
def get_execution_session(session_id: str):
    """Retrieve execution session details, fine-grained lifecycle status, and observation summary."""
    sess = store.get_execution_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Execution session '{session_id}' not found")
    return sess


@router.get("/sessions/{session_id}/actions")
def get_execution_session_actions(session_id: str):
    """Retrieve queryable list of 4-layer ExecutionAction records for a session."""
    actions = store.get_execution_actions(session_id)
    return [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in actions]


@router.get("/sessions/{session_id}/evidence")
def get_execution_session_evidence(session_id: str):
    """Retrieve sealed evidence package for an execution session."""
    sess = store.get_execution_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Execution session '{session_id}' not found")

    actions = store.get_execution_actions(session_id)
    artifacts = store.get_execution_artifacts(session_id)

    return {
        "session_id": sess.id,
        "execution_run_id": sess.execution_run_id,
        "status": sess.status,
        "trajectory_hash": sess.trajectory_hash,
        "preflight": sess.preflight,
        "pre_snapshot": sess.pre_snapshot,
        "post_snapshot": sess.post_snapshot,
        "observation_summary": sess.observation_summary,
        "evidence_package": sess.evidence_package,
        "actions_count": len(actions),
        "actions": [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in actions],
        "artifacts_count": len(artifacts),
        "artifacts": [art.model_dump() if hasattr(art, "model_dump") else art.dict() for art in artifacts]
    }


@router.get("/sessions/{session_id}/artifacts/{artifact_id}")
def get_execution_session_artifact(session_id: str, artifact_id: str):
    """Retrieve specific raw evidence artifact for an execution session."""
    artifacts = store.get_execution_artifacts(session_id)
    target = next((art for art in artifacts if art.id == artifact_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found in session '{session_id}'")
    return target


