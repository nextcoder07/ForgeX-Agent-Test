"""
Universal Agent Intake & Specification Reconstructor API Router.
"""

from __future__ import annotations

import os
import uuid
import datetime as dt
from typing import Dict, List
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.auth import get_current_user, UserRecord
from app.models.intake import (
    AgentIntakePayload,
    AgentUnderstandingResult,
    NormalizedAgentSpec,
    RegisterSpecRequest,
    AgentTestSpecification,
    SandboxSpecification,
    AgentDependency,
    PlatformResource,
    DependencyBinding,
)
from app.models.agent import AgentRecord
from app.services.store import store
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.pipeline.monitor import PipelineTracker
from app.core.llm.providers import get_platform_provider
from app.services.activity_log import activity_log

router = APIRouter(prefix="/intake", tags=["Intake"])
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(APP_DIR)
TEST_AGENTS_DIR = os.path.join(BACKEND_DIR, "test-agents")


def _now() -> str:
    return dt.datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Dependency Type → Platform Capability Mapping
# ---------------------------------------------------------------------------
_DEP_TYPE_TO_CAPABILITY = {
    "database": "DATABASE",
    "email": "EMAIL",
    "browser": "BROWSER",
    "payment": "PAYMENT",
    "filesystem": "FILESYSTEM",
    "http": "API_MOCK",
    "web_search": "WEB_SEARCH",
    "search": "WEB_SEARCH",
    "news": "NEWS_API",
    "location": "LOCATION_SERVICE",
    "maps": "LOCATION_SERVICE",
    "identity": "IDENTITY",
    "auth": "IDENTITY",
    "storage": "STORAGE",
    "s3": "STORAGE",
    "drive": "STORAGE",
    "git": "GIT",
    "runtime": "PYTHON_RUNTIME",
}

_CREDENTIAL_KEYWORDS = {
    "openai", "anthropic", "claude", "gpt", "api_key", "apikey",
    "oauth", "token", "secret", "credential", "google_drive",
    "aws_access", "azure", "huggingface",
}


def _resolve_dependencies_for_agent(agent_id: str, spec: NormalizedAgentSpec):
    """Auto-extract dependencies from a NormalizedAgentSpec and resolve them.

    Resolution Policy:
      1. Platform Runtime (Python 3.12 Sandbox) -> READY
      2. Python Packages (requirements.txt packages) -> PLATFORM_SANDBOX (READY via pip install)
      3. Secrets & API Credentials:
         - If required (e.g. OPENAI_API_KEY) -> USER_CREDENTIAL (user_credential_required)
         - If optional with code fallback (e.g. NEWS_API_KEY) -> OPTIONAL_CREDENTIAL (ready_with_fallback)
    """
    seen_names: set = set()

    # 1. Always add the platform runtime dependency
    runtime_name = "Python 3.12 Runtime"
    dep_rt = AgentDependency(
        id=f"dep-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        dependency_name=runtime_name,
        dependency_type="runtime",
        required=True,
        detected_from="config",
    )
    store.save_agent_dependency(dep_rt)
    store.save_dependency_binding(DependencyBinding(
        id=f"bind-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        dependency_name=runtime_name,
        resolution_type="platform_sandbox",
        status="ready",
        created_at=_now(),
    ))
    seen_names.add(runtime_name)

    # 2. Extract and resolve declared Python packages from spec.dependencies
    for dep_def in spec.dependencies:
        dep_name = dep_def.name
        if dep_name in seen_names:
            continue
        seen_names.add(dep_name)

        dep = AgentDependency(
            id=f"dep-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=dep_name,
            dependency_type=dep_def.type or "package",
            required=dep_def.required,
            detected_from=dep_def.detected_from,
        )
        store.save_agent_dependency(dep)

        # Standard packages and frameworks are installable in the platform sandbox via pip
        binding = DependencyBinding(
            id=f"bind-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=dep_name,
            resolution_type="platform_sandbox",
            status="ready",
            created_at=_now(),
        )
        store.save_dependency_binding(binding)

    # 3. Extract and resolve Detected Secrets / Model Credentials from runtime_manifest
    detected_secrets = spec.runtime_manifest.get("detected_secrets", []) if isinstance(spec.runtime_manifest, dict) else []
    for sec in detected_secrets:
        sec_name = sec.get("name") if isinstance(sec, dict) else getattr(sec, "name", "")
        is_required = sec.get("required", True) if isinstance(sec, dict) else getattr(sec, "required", True)
        if not sec_name or sec_name in seen_names:
            continue
        seen_names.add(sec_name)

        dep = AgentDependency(
            id=f"dep-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=sec_name,
            dependency_type="credential",
            required=is_required,
            detected_from="environment_variable",
        )
        store.save_agent_dependency(dep)

        if not is_required:
            binding = DependencyBinding(
                id=f"bind-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                dependency_name=sec_name,
                resolution_type="optional_credential",
                status="ready_with_fallback",
                created_at=_now(),
            )
        else:
            default_val = os.getenv(sec_name)
            if default_val:
                binding = DependencyBinding(
                    id=f"bind-{uuid.uuid4().hex[:8]}",
                    agent_id=agent_id,
                    dependency_name=sec_name,
                    resolution_type="system_default",
                    status="ready",
                    created_at=_now(),
                )
            else:
                binding = DependencyBinding(
                    id=f"bind-{uuid.uuid4().hex[:8]}",
                    agent_id=agent_id,
                    dependency_name=sec_name,
                    resolution_type="user_credential",
                    status="user_credential_required",
                    created_at=_now(),
                )
        store.save_dependency_binding(binding)


@router.get("/local-agents")
def list_local_demo_agents():
    """List all demonstration agents available in test-agents/."""
    agents = []
    if os.path.isdir(TEST_AGENTS_DIR):
        for d in os.listdir(TEST_AGENTS_DIR):
            if os.path.isdir(os.path.join(TEST_AGENTS_DIR, d)):
                agents.append(d)
    return {"local_agents": sorted(agents)}


@router.get("/local-agents/{agent_id}")
def get_local_demo_agent_files(agent_id: str):
    """Retrieve all files and metadata for a test-agent."""
    target = os.path.join(TEST_AGENTS_DIR, agent_id)
    if not os.path.isdir(target):
        raise HTTPException(status_code=404, detail=f"Demo agent '{agent_id}' not found in {TEST_AGENTS_DIR}")

    files_payload: Dict[str, str] = {}
    metadata: Dict[str, str] = {}

    for root, _, files in os.walk(target):
        for file in files:
            fpath = os.path.join(root, file)
            if file.endswith((".py", ".txt", ".json", ".yaml", ".yml", ".md", ".ts", ".js")):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        relative_path = os.path.relpath(fpath, target).replace(os.sep, "/")
                        files_payload[relative_path] = content
                        if file in ("metadata.yaml", "metadata.yml"):
                            for line in content.splitlines():
                                if ":" in line:
                                    k, v = line.split(":", 1)
                                    metadata[k.strip()] = v.strip().strip("'\"")
                except Exception:
                    pass

    return {
        "agent_id": agent_id,
        "metadata": metadata,
        "files": files_payload
    }


@router.delete("/agents/{agent_id}")
def delete_agent_endpoint(agent_id: str):
    """Permanently deletes an agent project and purges all associated scenarios, runs, and artifacts."""
    store.delete_agent(agent_id)
    activity_log.emit(
        category="INTAKE",
        action="AGENT_DELETED",
        detail=f"Permanently deleted agent '{agent_id}' and all associated scenarios/traces.",
        status="success"
    )
    return {"status": "success", "deleted_agent_id": agent_id}


@router.delete("/agents")
def purge_all_agents_endpoint():
    """Purges all agents, scenarios, jobs, and snapshot files for a clean workspace reset."""
    store.purge_all_agents()
    activity_log.emit(
        category="INTAKE",
        action="WORKSPACE_PURGED",
        detail="Purged all agents and disk snapshots for a clean workspace reset.",
        status="success"
    )
    return {"status": "success", "message": "Workspace purged clean"}


@router.post("/analyze", response_model=AgentUnderstandingResult)
async def analyze_agent(payload: AgentIntakePayload):
    """Executes the complete Agent Intake & Understanding pipeline."""
    activity_log.emit(
        category="INTAKE",
        action="ANALYZE_START",
        detail=f"Analyzing {len(payload.files)} files for agent: {payload.agent_name_hint}",
        request_summary=f"Endpoint: {payload.endpoint_url or 'None'} | Files: {list(payload.files.keys())}",
        status="success"
    )

    tracker = PipelineTracker(
        agent_id=payload.agent_name_hint or "Discovered Agent",
        agent_name=payload.agent_name_hint or "Discovered Agent"
    )

    llm = get_platform_provider()
    try:
        result = await process_agent_intake(payload, llm, tracker=tracker)
    except Exception as e:
        for stg in tracker.stages:
            if stg.status in ("running", "queued"):
                stg.status = "failed"
                stg.error = str(e)
        run_snap = tracker.get_run_snapshot()
        run_snap.status = "failed"
        store.save_pipeline_run(run_snap)
        activity_log.emit(
            category="INTAKE",
            action="ANALYZE_FAILED",
            detail=f"Analysis failed: {str(e)}",
            status="error"
        )
        raise HTTPException(status_code=500, detail=f"Gemini AI pipeline failed: {str(e)}")

    activity_log.emit(
        category="INTAKE",
        action="AST_PARSE",
        detail="Completed static AST parsing of files.",
        status="success"
    )

    if result.analysis_status == "COMPLETE":
        activity_log.emit(
            category="INTAKE",
            action="SPEC_RECONSTRUCT_SUCCESS",
            detail="Reconstructed normalized spec using Gemini semantic analysis.",
            status="success"
        )
    else:
        activity_log.emit(
            category="INTAKE",
            action="SPEC_RECONSTRUCT_PARTIAL",
            detail=f"Reconstructed normalized spec from deterministic AST facts ({result.semantic_status}).",
            status="warning"
        )

    # Save pipeline snapshot
    run_snap = tracker.get_run_snapshot()
    if result.analysis_status != "COMPLETE":
        run_snap.status = "partial"
    store.save_pipeline_run(run_snap)
    result.pipeline_run_id = run_snap.id

    activity_log.emit(
        category="INTAKE",
        action="ANALYZE_COMPLETE",
        detail=f"Analysis complete ({result.analysis_status}) for {result.normalized_spec.identity.get('name')}.",
        response_summary=f"Tools: {len(result.normalized_spec.tools)} | Status: {result.analysis_status} | Confidence: {result.confidence_score}%",
        status="success" if result.analysis_status == "COMPLETE" else "warning"
    )

    return result


@router.post("/register-spec", response_model=AgentRecord)
async def register_normalized_spec(
    payload: RegisterSpecRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    """Converts confirmed Normalized Spec into active agent record."""
    spec = payload.normalized_spec
    registered_name = spec.identity.get("name", "Custom Discovered Agent")
    chosen_name = payload.display_name.strip()
    if not chosen_name:
        raise HTTPException(status_code=422, detail="display_name must not be empty")
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"

    goals_list = spec.goals
    goals_str = f" designed to {goals_list[0].lower()}" if goals_list else ""
    domain_name = spec.identity.get("domain", "general").replace("_", " ").title()
    inferred_desc = f"Autonomous {domain_name} agent{goals_str}."
    ws_id = current_user.active_workspace_id
    user_id = current_user.user_id if current_user.user_id != "anonymous" else None
    
    from app.db.supabase_client import get_client
    sb = get_client()
    if sb:
        if not user_id:
            try:
                res_u = sb.table("user_profiles").select("id").limit(1).execute()
                if res_u.data and len(res_u.data) > 0:
                    user_id = res_u.data[0]["id"]
            except Exception:
                pass
        if not ws_id and user_id:
            try:
                res_m = sb.table("workspace_members").select("workspace_id").eq("user_id", user_id).limit(1).execute()
                if res_m.data and len(res_m.data) > 0:
                    ws_id = res_m.data[0].get("workspace_id")
            except Exception:
                pass
            if not ws_id:
                try:
                    res_w = sb.table("workspaces").select("id").eq("owner_id", user_id).limit(1).execute()
                    if res_w.data and len(res_w.data) > 0:
                        ws_id = res_w.data[0].get("id")
                except Exception:
                    pass
        if not ws_id:
            try:
                res_all_w = sb.table("workspaces").select("id, owner_id").limit(1).execute()
                if res_all_w.data and len(res_all_w.data) > 0:
                    ws_id = res_all_w.data[0]["id"]
                    if not user_id:
                        user_id = res_all_w.data[0].get("owner_id")
            except Exception:
                pass

    bp = spec.behavior_profile
    has_creds = len(spec.dependencies) == 0 or all(getattr(d, "status", "") in ("READY", "READY_PLATFORM_SANDBOX") for d in spec.dependencies)
    exec_status = "READY" if (has_creds and spec.execution_status in ("READY", "EXECUTION_READY")) else "BLOCKED"
    block_reason = None if exec_status == "READY" else "MISSING_AGENT_CREDENTIAL"

    # Extract deterministic surfaces from behavior profile, spec, or payload
    ev_packet = getattr(spec, "evidence_packet", {}) or getattr(payload, "evidence_packet", {}) or {}
    aud_report = getattr(spec, "audit_report", {}) or getattr(payload, "audit_report", {}) or {}

    # Hard Stage Gate: Reject registration if audit verdict is DEFECT
    if aud_report and aud_report.get("audit_verdict") == "DEFECT":
        raise HTTPException(
            status_code=422,
            detail=f"Intake Audit Gate Rejected: Agent specification contains critical defects ({aud_report.get('overall_quality_score', 0)}% quality score). Discrepancies: {aud_report.get('discrepancies', [])}"
        )

    inputs_val = (bp.inputs if bp and bp.inputs else []) or getattr(spec, "inputs", []) or (ev_packet.get("cli_arguments") if ev_packet else [])
    outputs_val = (bp.outputs if bp and bp.outputs else []) or getattr(spec, "outputs", []) or (ev_packet.get("output_structures") if ev_packet else [])
    caps_val = list(dict.fromkeys((spec.capabilities or []) + (bp.capabilities if bp and bp.capabilities else [])))
    
    # Distinguish Agent PII Capability vs Demo Data PII vs PII Query Possibility
    has_pii_security_surface = any("pii" in str(s).lower() for s in (bp.security_surfaces if bp and bp.security_surfaces else (getattr(spec, "security_surfaces", []) or [])))
    has_pii_io = any(k in str(inputs_val + outputs_val).lower() for k in ["resume", "candidate", "applicant", "ssn", "passport"])
    pii_agent_capability = has_pii_security_surface or has_pii_io
    demo_dataset_pii = any("demo" in str(fn).lower() or "demo.sqlite" in str(payload.source_files) for fn in (ev_packet.get("functions", []) if ev_packet else [])) and any(k in str(payload.source_files).lower() for k in ["alice@example.com", "customer", "email text"])
    pii_query_possible = any(k in str(caps_val).lower() for k in ["sql", "database", "rag"])

    # Extract dedicated decision surfaces
    dec_surfaces = []
    if bp and getattr(bp, "decision_surfaces", None):
        dec_surfaces = [s.model_dump() if hasattr(s, "model_dump") else s for s in bp.decision_surfaces]
    elif getattr(spec, "decision_surfaces", None):
        dec_surfaces = [s.model_dump() if hasattr(s, "model_dump") else s for s in spec.decision_surfaces]
    elif ev_packet and ev_packet.get("decision_surfaces"):
        dec_surfaces = ev_packet.get("decision_surfaces")

    # Workflow extraction
    workflow_val = []
    if bp and bp.workflow_graph and bp.workflow_graph.nodes:
        workflow_val = [n.model_dump() if hasattr(n, "model_dump") else n for n in bp.workflow_graph.nodes]
    elif getattr(spec, "workflow", None):
        workflow_val = [n.model_dump() if hasattr(n, "model_dump") else n for n in spec.workflow]
    elif ev_packet and ev_packet.get("functions"):
        workflow_val = [
            {"id": fn.get("name", "fn"), "name": f"{fn.get('name', 'fn')}()", "implementation": fn.get("name", "fn"), "node_type": "entrypoint" if fn.get("name") in ["main", "run"] else "node"}
            for fn in ev_packet.get("functions", [])
            if not str(fn.get("name", "")).startswith("_")
        ]

    # Security surfaces
    security_surfaces_val = []
    if bp and bp.security_surfaces:
        security_surfaces_val = [s.model_dump() if hasattr(s, "model_dump") else s for s in bp.security_surfaces]
    elif getattr(spec, "security_surfaces", None):
        security_surfaces_val = [s.model_dump() if hasattr(s, "model_dump") else s for s in spec.security_surfaces]
    elif ev_packet and ev_packet.get("security_surfaces"):
        security_surfaces_val = ev_packet.get("security_surfaces")

    # Side effects
    side_effects_val = []
    if bp and bp.side_effects:
        side_effects_val = list(dict.fromkeys(bp.side_effects))
    elif getattr(spec, "side_effects", None):
        side_effects_val = list(dict.fromkeys(spec.side_effects))
    elif ev_packet and ev_packet.get("side_effects"):
        side_effects_val = [f"{se.get('side_effect_type', 'OPERATION')}: {se.get('target', 'target')}" for se in ev_packet.get("side_effects", [])]

    # Dynamic Confidence Score: derived from audit report quality score and evidence count
    computed_confidence = float(aud_report.get("overall_quality_score", 88.0)) if aud_report else 85.0

    # Clean runtime manifest model dependencies to guarantee canonical agent_id matching
    manifest_clean = dict(spec.runtime_manifest or {})
    if "detected_model_dependencies" in manifest_clean:
        clean_model_deps = []
        for idx, md in enumerate(manifest_clean["detected_model_dependencies"]):
            md_dict = dict(md) if isinstance(md, dict) else (md.model_dump() if hasattr(md, "model_dump") else dict(md))
            md_dict["agent_id"] = agent_id
            md_dict["id"] = f"dep-model-{agent_id}-{idx + 1}"
            clean_model_deps.append(md_dict)
        manifest_clean["detected_model_dependencies"] = clean_model_deps

    rec = AgentRecord(
        id=agent_id,
        name=chosen_name or agent_id,
        display_name=chosen_name,
        source_name=registered_name,
        description=inferred_desc,
        domain=spec.identity.get("domain", "general"),
        identity=spec.identity or {},
        system_prompt="\n".join(spec.instructions),
        tools=spec.tools,
        dependencies=spec.dependencies,
        constitution=spec.constitution,
        capabilities=caps_val,
        inputs=inputs_val,
        outputs=outputs_val,
        workflow=workflow_val,
        data_surfaces={
            "pii_detected": pii_agent_capability,
            "sensitive_fields": getattr(bp, "sensitive_fields", []) if bp else (["name", "email", "phone", "location", "linkedin", "github", "employment_history", "education"] if pii_agent_capability else []),
            "demo_dataset_contains_pii": demo_dataset_pii,
            "pii_query_possible": pii_query_possible,
            "transformations": [t.model_dump() if hasattr(t, "model_dump") else t for t in (bp.data_transformations if bp else [])]
        },
        decision_surfaces=dec_surfaces,
        security_surfaces=security_surfaces_val,
        side_effects=side_effects_val,
        evidence_packet=ev_packet,
        audit_report=aud_report,
        confidence_score=computed_confidence,
        configuration_status="READY",
        blocking_reason=block_reason,
        endpoint=payload.endpoint_url,
        version_label="v1.0-discovered",
        artifact_id=payload.artifact.artifact_id if payload.artifact else None,
        artifact_hash=payload.artifact.artifact_hash if payload.artifact else None,
        source_files=payload.source_files,
        runtime_manifest=manifest_clean,
        execution_status=exec_status,
        input_type=payload.artifact.input_type if payload.artifact else "package",
        user_id=user_id or "default_user",
        owner_id=user_id,
        workspace_id=ws_id,
        created_at=_now()
    )
    agent_status = "SUCCESS"
    version_status = "SUCCESS"
    artifact_status = "SUCCESS" if payload.artifact else "SKIPPED"
    behavior_profile_status = "PENDING"
    sandbox_spec_status = "PENDING"

    try:
        store.save_agent(rec)
    except Exception as e:
        logger.error(f"Error saving agent to store: {e}")
        agent_status = "FAILED"

    if payload.artifact and agent_status == "SUCCESS":
        try:
            store.save_agent_artifact(rec, payload.artifact, payload.source_files)
        except Exception as e:
            logger.error(f"Error saving agent artifact: {e}")
            artifact_status = "FAILED"

    # --- Auto-extract dependencies and resolve bindings ---
    _resolve_dependencies_for_agent(rec.id, spec)

    # --- Build and Persist AgentBehaviorProfile ---
    try:
        if spec.behavior_profile:
            bp = spec.behavior_profile
            bp.agent_id = rec.id
            bp.agent_version_id = rec.id
            store.save_behavior_profile(bp)
        else:
            from app.core.intake.profile_builder import ProfileBuilder
            from app.models.agent_behavior import WorkflowGraph
            wf_graph = WorkflowGraph(
                entrypoint=spec.runtime_manifest.get("entrypoint", "agent.py") if isinstance(spec.runtime_manifest, dict) else "agent.py",
                nodes=[],
                edges=[]
            )
            bp = ProfileBuilder.build_behavior_profile(
                agent_id=rec.id,
                agent_name=rec.display_name or rec.name,
                domain=rec.domain or "general",
                workflow_graph=wf_graph,
                capabilities=spec.capabilities or [],
                external_calls=[],
                credential_references=[],
                transformations=[],
                invariants=[],
                failure_surfaces=[],
                agent_version_id=rec.id
            )
            store.save_behavior_profile(bp)
        behavior_profile_status = "SUCCESS"
    except Exception as e:
        logger.warning(f"Error building/saving AgentBehaviorProfile for {rec.id}: {e}")
        behavior_profile_status = "FAILED"

    # --- Auto-build and persist SandboxSpecification ---
    try:
        from app.core.sandbox.sandbox_manager import build_sandbox_specification_for_agent
        build_sandbox_specification_for_agent(rec)
        sandbox_spec_status = "SUCCESS"
    except Exception as e:
        logger.warning(f"Error auto-building sandbox specification: {e}")
        sandbox_spec_status = "FAILED"

    # --- Auto-build and persist AgentTestSpecification ---
    try:
        wf_nodes = []
        if spec.behavior_profile and hasattr(spec.behavior_profile, "workflow_graph") and hasattr(spec.behavior_profile.workflow_graph, "nodes"):
            wf_nodes = [getattr(n, "label", str(n)) for n in spec.behavior_profile.workflow_graph.nodes]
        test_spec = AgentTestSpecification(
            id=f"testspec-{rec.id}",
            agent_id=rec.id,
            goal=spec.goals[0] if spec.goals else "Execute agent workflows",
            inputs=[{"type": "user_message", "name": "prompt"}],
            tools=[t.model_dump() if hasattr(t, "model_dump") else (t.dict() if hasattr(t, "dict") else dict(t)) for t in spec.tools],
            workflow=wf_nodes,
            risks=[r if isinstance(r, str) else str(r) for r in (getattr(spec, "risks", []) or [])],
            created_at=_now()
        )
        store.save_agent_test_spec(test_spec)
    except Exception as e:
        logger.warning(f"Error auto-saving AgentTestSpecification for {rec.id}: {e}")

    # --- Auto-create and persist initial baseline AgentVersionRecord (v1.0) ---
    try:
        from app.models.canonical_data_models import AgentVersionRecord
        v1_record = AgentVersionRecord(
            id=f"ver-{rec.id}-v1.0",
            agent_id=rec.id,
            version_label="v1.0",
            parent_version_id=None,
            is_latest=True,
            change_summary="Initial baseline ingestion",
            source_files=rec.source_files or {},
            created_at=_now()
        )
        store.save_agent_version(v1_record)
        rec.current_version_id = v1_record.id
    except Exception as e:
        logger.warning(f"Error auto-saving baseline AgentVersionRecord for {rec.id}: {e}")



    # Overall registration status
    if (
        agent_status == "SUCCESS"
        and artifact_status in ("SUCCESS", "SKIPPED")
        and behavior_profile_status == "SUCCESS"
        and sandbox_spec_status == "SUCCESS"
    ):
        overall = "COMPLETE"
    elif agent_status == "FAILED":
        overall = "FAILED"
    else:
        overall = "PARTIAL"

    status_dict = {
        "agent_status": agent_status,
        "version_status": version_status,
        "artifact_status": artifact_status,
        "behavior_profile_status": behavior_profile_status,
        "sandbox_spec_status": sandbox_spec_status,
        "overall": overall
    }

    # Store registration status inside the record's runtime manifest
    if not isinstance(rec.runtime_manifest, dict):
        rec.runtime_manifest = {}
    rec.runtime_manifest["registration_status"] = status_dict

    # If sandbox spec failed, block execution
    if sandbox_spec_status == "FAILED":
        rec.execution_status = "EXECUTION_BLOCKED"
        try:
            # Update store with registration status details
            store.save_agent(rec)
        except Exception:
            pass

    activity_log.emit(
        category="INTAKE",
        action="REGISTER",
        detail=f"Registered agent spec: {chosen_name} | Sandbox: {sandbox_spec_status} | Profile: {behavior_profile_status} | Overall: {overall}",
        response_summary=f"Agent ID: {agent_id} | Domain: {rec.domain} | Status: {status_dict}",
        status="success" if overall == "COMPLETE" else "warning"
    )
    return rec



@router.get("/agents/{agent_id}/sandbox-spec", response_model=SandboxSpecification)
def get_agent_sandbox_specification(agent_id: str):
    """Retrieve or build the sandbox specification for a specific agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    from app.core.sandbox.sandbox_manager import get_or_create_sandbox_spec
    return get_or_create_sandbox_spec(agent)


@router.get("/test-specs", response_model=List[AgentTestSpecification])
def list_agent_test_specifications():
    """List all registered agent test specifications."""
    return store.list_agent_test_specs()


@router.get("/test-specs/{spec_id}", response_model=AgentTestSpecification)
def get_agent_test_specification(spec_id: str):
    """Retrieve a specific agent test specification by ID."""
    spec = store.get_agent_test_spec(spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Agent test specification '{spec_id}' not found")
    return spec


@router.post("/test-specs", response_model=AgentTestSpecification)
def create_agent_test_specification(spec: AgentTestSpecification):
    """Save or update an agent test specification."""
    store.save_agent_test_spec(spec)
    return spec


@router.get("/sandbox-specs", response_model=List[SandboxSpecification])
def list_sandbox_specifications():
    """List all registered sandbox specifications."""
    return store.list_sandbox_specs()


@router.get("/sandbox-specs/{spec_id}", response_model=SandboxSpecification)
def get_sandbox_specification(spec_id: str):
    """Retrieve a specific sandbox specification by ID."""
    spec = store.get_sandbox_spec(spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Sandbox specification '{spec_id}' not found")
    return spec


@router.post("/sandbox-specs", response_model=SandboxSpecification)
def create_sandbox_specification(spec: SandboxSpecification):
    """Save or update a sandbox specification."""
    store.save_sandbox_spec(spec)
    return spec


# ---------------------------------------------------------------------------
# Dependency Setup Flow Endpoints
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/dependencies", response_model=List[AgentDependency])
def get_agent_dependencies(agent_id: str):
    """List all detected dependencies for an agent, dynamically extracting from AgentRecord if unpopulated."""
    agent = store.get_agent(agent_id)
    if not agent:
        return []
    
    # 1. Try fetching stored dependencies first
    try:
        stored = store.get_agent_dependencies(agent_id)
        if stored:
            return stored
    except Exception:
        pass

    # 2. Dynamic extraction from agent record fields
    deps: List[AgentDependency] = []
    seen: set = set()

    # Always add platform Python runtime
    deps.append(AgentDependency(
        id=f"dep-rt-{agent_id[:8]}",
        agent_id=agent_id,
        dependency_name="Python 3.12 Runtime",
        dependency_type="runtime",
        required=True,
        detected_from="platform_config"
    ))
    seen.add("Python 3.12 Runtime")

    # Extract tools from agent.tools
    tools_list = getattr(agent, "tools", []) or []
    for t in tools_list:
        t_name = t.name if hasattr(t, "name") else (t.get("name") if isinstance(t, dict) else "")
        if t_name and t_name not in seen:
            seen.add(t_name)
            deps.append(AgentDependency(
                id=f"dep-tool-{uuid.uuid4().hex[:6]}",
                agent_id=agent_id,
                dependency_name=t_name,
                dependency_type="tool",
                required=True,
                detected_from="source_code_ast"
            ))

    # Extract declared dependencies from agent.dependencies
    dep_list = getattr(agent, "dependencies", []) or []
    for d in dep_list:
        d_name = d.name if hasattr(d, "name") else (d.get("name") if isinstance(d, dict) else "")
        d_req = d.required if hasattr(d, "required") else (d.get("required", True) if isinstance(d, dict) else True)
        d_type = d.type if hasattr(d, "type") else (d.get("type", "credential") if isinstance(d, dict) else "credential")
        if d_name and d_name not in seen:
            seen.add(d_name)
            deps.append(AgentDependency(
                id=f"dep-cred-{uuid.uuid4().hex[:6]}",
                agent_id=agent_id,
                dependency_name=d_name,
                dependency_type=d_type or "credential",
                required=d_req,
                detected_from="environment_manifest"
            ))

    # Extract detected secrets from agent.runtime_manifest
    manifest = getattr(agent, "runtime_manifest", {}) or {}
    detected_secrets = manifest.get("detected_secrets", []) if isinstance(manifest, dict) else []
    for sec in detected_secrets:
        sec_name = sec.get("name") if isinstance(sec, dict) else getattr(sec, "name", "")
        sec_req = sec.get("required", True) if isinstance(sec, dict) else getattr(sec, "required", True)
        if sec_name and sec_name not in seen:
            seen.add(sec_name)
            deps.append(AgentDependency(
                id=f"dep-sec-{uuid.uuid4().hex[:6]}",
                agent_id=agent_id,
                dependency_name=sec_name,
                dependency_type="credential",
                required=sec_req,
                detected_from="environment_variable"
            ))

    # Save to store for persistence if possible
    for dep in deps:
        try:
            store.save_agent_dependency(dep)
        except Exception:
            pass

    return deps


@router.get("/platform/resources", response_model=List[PlatformResource])
def list_platform_resources():
    """List all platform-provided sandbox/mock resources."""
    try:
        return store.list_platform_resources()
    except Exception:
        return [
            PlatformResource(
                id="res-py312",
                name="Python 3.12 Sandbox Container",
                capability="PYTHON_RUNTIME",
                resource_type="container",
                status="active",
                endpoint="docker://agent-sandbox-py312"
            ),
            PlatformResource(
                id="res-mock-gateway",
                name="Tool Gateway Mock Proxy",
                capability="API_MOCK",
                resource_type="mock_server",
                status="active",
                endpoint="http://localhost:8000/mock-gateway"
            )
        ]


@router.get("/agents/{agent_id}/bindings", response_model=List[DependencyBinding])
def get_agent_bindings(agent_id: str):
    """List all dependency bindings (resolutions) for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        return []

    # Try stored bindings first
    try:
        stored = store.get_dependency_bindings(agent_id)
        if stored:
            return stored
    except Exception:
        pass

    # Dynamic extraction of bindings
    deps = get_agent_dependencies(agent_id)
    bindings: List[DependencyBinding] = []

    for dep in deps:
        if dep.dependency_type in ("runtime", "tool"):
            status_val = "ready"
            res_type = "platform_sandbox"
        elif dep.required:
            status_val = "user_credential_required"
            res_type = "user_credential"
        else:
            status_val = "ready_with_fallback"
            res_type = "optional_credential"

        b = DependencyBinding(
            id=f"bind-{uuid.uuid4().hex[:6]}",
            agent_id=agent_id,
            dependency_name=dep.dependency_name,
            resolution_type=res_type,
            status=status_val,
            created_at=_now()
        )
        bindings.append(b)
        try:
            store.save_dependency_binding(b)
        except Exception:
            pass

    return bindings


class UpdateBindingsRequest(BaseModel):
    bindings: List[DependencyBinding]


@router.post("/agents/{agent_id}/bindings", response_model=List[DependencyBinding])
def update_agent_bindings(agent_id: str, payload: UpdateBindingsRequest):
    """Create or update dependency bindings for an agent (user provides credentials / custom endpoints)."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    for binding in payload.bindings:
        binding.agent_id = agent_id
        if not binding.id:
            binding.id = f"bind-{uuid.uuid4().hex[:8]}"
        if not binding.created_at:
            binding.created_at = _now()
        try:
            store.save_dependency_binding(binding)
        except Exception:
            pass
    return get_agent_bindings(agent_id)
