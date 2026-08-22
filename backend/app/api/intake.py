"""
Universal Agent Intake & Specification Reconstructor API Router.
"""

from __future__ import annotations

import os
import uuid
import datetime as dt
from typing import Dict, List
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
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
from app.core.llm.gemini_provider import GeminiProvider
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

    Priority:
      1. Platform sandbox/resource (free)
      2. Free API/provider
      3. Adapter/mock/replay
      4. User test credential (ask user)
      5. Block execution
    """
    platform_resources = store.list_platform_resources()
    capability_map = {r.capability: r for r in platform_resources}

    seen_names: set = set()

    # 1. Extract from spec.dependencies
    for dep_def in spec.dependencies:
        dep_name = dep_def.name
        if dep_name in seen_names:
            continue
        seen_names.add(dep_name)

        dep = AgentDependency(
            id=f"dep-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=dep_name,
            dependency_type=dep_def.type,
            required=dep_def.required,
            detected_from=dep_def.detected_from,
        )
        store.save_agent_dependency(dep)

        # Try to match to a platform capability
        cap_key = _DEP_TYPE_TO_CAPABILITY.get(dep_def.type.lower())
        if cap_key and cap_key in capability_map:
            binding = DependencyBinding(
                id=f"bind-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                dependency_name=dep_name,
                resolution_type="platform_sandbox",
                status="ready",
                created_at=_now(),
            )
        elif any(kw in dep_name.lower() for kw in _CREDENTIAL_KEYWORDS):
            binding = DependencyBinding(
                id=f"bind-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                dependency_name=dep_name,
                resolution_type="user_credential",
                status="user_credential_required",
                created_at=_now(),
            )
        else:
            # Attempt generic match by scanning name keywords
            resolved = False
            for keyword, cap in _DEP_TYPE_TO_CAPABILITY.items():
                if keyword in dep_name.lower() and cap in capability_map:
                    binding = DependencyBinding(
                        id=f"bind-{uuid.uuid4().hex[:8]}",
                        agent_id=agent_id,
                        dependency_name=dep_name,
                        resolution_type="platform_sandbox",
                        status="ready",
                        created_at=_now(),
                    )
                    resolved = True
                    break
            if not resolved:
                binding = DependencyBinding(
                    id=f"bind-{uuid.uuid4().hex[:8]}",
                    agent_id=agent_id,
                    dependency_name=dep_name,
                    resolution_type="block",
                    status="unsupported",
                    created_at=_now(),
                )
        store.save_dependency_binding(binding)
        activity_log.emit(
            category="DEPENDENCY",
            action="RESOLVE",
            detail=f"Resolved spec dependency: {dep_name}",
            response_summary=f"Resolved: {binding.resolution_type} ({binding.status})",
            status="success" if binding.status == "ready" else "warning"
        )

    # 2. Extract from capabilities list (e.g. "WEB_SEARCH", "BROWSER")
    for cap in spec.capabilities:
        cap_upper = cap.upper().replace(" ", "_")
        if cap_upper in seen_names:
            continue
        seen_names.add(cap_upper)

        dep = AgentDependency(
            id=f"dep-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=cap,
            dependency_type="tool",
            required=True,
            detected_from="capabilities",
        )
        store.save_agent_dependency(dep)

        if cap_upper in capability_map:
            binding = DependencyBinding(
                id=f"bind-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                dependency_name=cap,
                resolution_type="platform_sandbox",
                status="ready",
                created_at=_now(),
            )
        else:
            binding = DependencyBinding(
                id=f"bind-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                dependency_name=cap,
                resolution_type="user_credential",
                status="user_credential_required",
                created_at=_now(),
            )
        store.save_dependency_binding(binding)
        activity_log.emit(
            category="DEPENDENCY",
            action="RESOLVE",
            detail=f"Resolved capability dependency: {cap}",
            response_summary=f"Resolved: {binding.resolution_type} ({binding.status})",
            status="success" if binding.status == "ready" else "warning"
        )

    # 3. Always add a runtime dependency
    runtime_name = "Python 3.12 Runtime"
    if runtime_name not in seen_names:
        dep = AgentDependency(
            id=f"dep-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=runtime_name,
            dependency_type="runtime",
            required=True,
            detected_from="config",
        )
        store.save_agent_dependency(dep)
        binding = DependencyBinding(
            id=f"bind-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            dependency_name=runtime_name,
            resolution_type="platform_sandbox",
            status="ready",
            created_at=_now(),
        )
        store.save_dependency_binding(binding)
        activity_log.emit(
            category="DEPENDENCY",
            action="RESOLVE",
            detail=f"Resolved runtime: {runtime_name}",
            response_summary=f"Resolved: {binding.resolution_type} ({binding.status})",
            status="success"
        )


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

    llm = GeminiProvider()
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

    activity_log.emit(
        category="INTAKE",
        action="SPEC_RECONSTRUCT",
        detail="Reconstructed normalized spec using Gemini semantic analysis.",
        status="success"
    )

    # Save pipeline snapshot
    run_snap = tracker.get_run_snapshot()
    store.save_pipeline_run(run_snap)
    result.pipeline_run_id = run_snap.id

    activity_log.emit(
        category="INTAKE",
        action="ANALYZE_COMPLETE",
        detail=f"Analysis complete for {result.normalized_spec.identity.get('name')}.",
        response_summary=f"Tools: {len(result.normalized_spec.tools)} | Confidence: {result.confidence_score}%",
        status="success"
    )

    return result


@router.post("/register-spec", response_model=AgentRecord)
async def register_normalized_spec(payload: RegisterSpecRequest):
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

    rec = AgentRecord(
        id=agent_id,
        name=chosen_name or agent_id,
        display_name=chosen_name,
        source_name=registered_name,
        description=inferred_desc,
        domain=spec.identity.get("domain", "general"),
        system_prompt="\n".join(spec.instructions),
        tools=spec.tools,
        dependencies=spec.dependencies,
        constitution=spec.constitution,
        endpoint=payload.endpoint_url,
        version_label="v1.0-discovered",
        artifact_id=payload.artifact.artifact_id if payload.artifact else None,
        artifact_hash=payload.artifact.artifact_hash if payload.artifact else None,
        source_files=payload.source_files,
        runtime_manifest=spec.runtime_manifest,
        execution_status=spec.execution_status,
        input_type=payload.artifact.input_type if payload.artifact else "package",
        created_at=_now()
    )
    store.save_agent(rec)
    if payload.artifact:
        store.save_agent_artifact(rec, payload.artifact, payload.source_files)

    # --- Auto-extract dependencies and resolve bindings ---
    _resolve_dependencies_for_agent(rec.id, spec)

    # --- Auto-build and persist SandboxSpecification ---
    try:
        from app.core.sandbox.sandbox_manager import build_sandbox_specification_for_agent
        build_sandbox_specification_for_agent(rec)
    except Exception as e:
        logger.warning(f"Error auto-building sandbox specification: {e}")

    activity_log.emit(
        category="INTAKE",
        action="REGISTER",
        detail=f"Registered agent spec & created SandboxSpecification: {chosen_name}",
        response_summary=f"Agent ID: {agent_id} | Domain: {rec.domain} | Tools: {len(rec.tools)}",
        status="success"
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
    """List all detected dependencies for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return store.get_agent_dependencies(agent_id)


@router.get("/platform/resources", response_model=List[PlatformResource])
def list_platform_resources():
    """List all platform-provided sandbox/mock resources."""
    return store.list_platform_resources()


@router.get("/agents/{agent_id}/bindings", response_model=List[DependencyBinding])
def get_agent_bindings(agent_id: str):
    """List all dependency bindings (resolutions) for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return store.get_dependency_bindings(agent_id)


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
        store.save_dependency_binding(binding)
    return store.get_dependency_bindings(agent_id)
