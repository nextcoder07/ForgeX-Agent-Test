"""
Dependency Resolution & Execution Mode API Router.
Exposes endpoints for inspecting detected agent model dependencies, available modes,
and resolving execution bindings before launching sandbox runs.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.models.dependency_model import (
    DependencyResolverRequest,
    DependencyResolverResult,
    AgentModelDependency,
    ExecutionModelBinding,
    SystemCredentialItem,
    SessionCredentialPrompt,
    ProvideCredentialsRequest,
    ExecutionMode,
)
from app.services.store import store
from app.core.dependencies.dependency_resolver import DependencyResolver

router = APIRouter(prefix="/dependencies", tags=["Dependencies & Resolution"])

# In-memory custom user system credentials override cache
_USER_SYSTEM_CREDENTIALS: Dict[str, str] = {}


@router.get("/system-credentials", response_model=List[SystemCredentialItem])
def get_platform_system_credentials():
    """Retrieve default platform system API keys and their active configuration status."""
    return DependencyResolver.get_system_credentials(_USER_SYSTEM_CREDENTIALS)


@router.post("/system-credentials", response_model=List[SystemCredentialItem])
def update_platform_system_credentials(payload: ProvideCredentialsRequest):
    """Update or override custom platform system API keys."""
    for k, v in payload.credentials.items():
        if v:
            _USER_SYSTEM_CREDENTIALS[k.upper()] = v
    return DependencyResolver.get_system_credentials(_USER_SYSTEM_CREDENTIALS)


@router.get("/agents/{agent_id}/required-credentials", response_model=SessionCredentialPrompt)
def get_agent_required_credentials(
    agent_id: str,
    mode: Optional[ExecutionMode] = Query(default=ExecutionMode.FAITHFUL)
):
    """Retrieve mode-specific required API key demands for an agent before execution."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    return DependencyResolver.evaluate_execution_credential_demands(
        agent=agent,
        provided_secrets=_USER_SYSTEM_CREDENTIALS,
        mode=mode or ExecutionMode.FAITHFUL
    )


@router.post("/resolve", response_model=DependencyResolverResult)
def resolve_agent_dependencies(payload: DependencyResolverRequest):
    """Resolve available execution modes (Faithful, Compatible, Simulation) and bind execution model."""
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    combined_secrets = {**_USER_SYSTEM_CREDENTIALS, **payload.provided_secrets}

    result = DependencyResolver.resolve_mode(
        agent=agent,
        requested_mode=payload.requested_mode,
        provided_secrets=combined_secrets
    )

    # Persist detected dependencies & binding in store
    for dep in result.detected_model_dependencies:
        store.save_agent_dependency_model(dep)

    if result.active_binding:
        store.save_execution_model_binding(result.active_binding)

    return result


from app.models.execution_requirement import AgentRequirementsReport
from app.core.dependencies.requirement_resolver import RequirementResolver


@router.get("/agents/{agent_id}/models", response_model=List[AgentModelDependency])
def get_agent_model_dependencies(agent_id: str):
    """Retrieve all detected model dependencies for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    result = DependencyResolver.resolve_mode(agent=agent, provided_secrets=_USER_SYSTEM_CREDENTIALS)
    return result.detected_model_dependencies


@router.get("/requirements/{agent_id}", response_model=AgentRequirementsReport)
def get_agent_requirements_report(agent_id: str):
    """Retrieve the unified 6-stage requirement resolution report for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    return RequirementResolver.resolve_agent_requirements(agent=agent, user_overrides=_USER_SYSTEM_CREDENTIALS)


from app.core.dependencies.setup_orchestrator import SetupOrchestrator
from app.models.execution import SetupReadinessRecord


@router.get("/agents/{agent_id}/setup-readiness", response_model=SetupReadinessRecord)
def get_agent_setup_readiness(agent_id: str):
    """Retrieve current pre-execution SetupReadinessRecord for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    return SetupOrchestrator.get_or_create_setup_readiness(agent_id)


@router.post("/agents/{agent_id}/run-setup", response_model=SetupReadinessRecord)
def run_agent_automatic_setup(agent_id: str):
    """Run full automatic environment setup, dependency package installation, and prerequisite verification."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    return SetupOrchestrator.run_automatic_setup(agent_id, provided_secrets=_USER_SYSTEM_CREDENTIALS)

