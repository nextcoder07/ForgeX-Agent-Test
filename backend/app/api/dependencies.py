"""
Dependency Resolution & Execution Mode API Router.
Exposes endpoints for inspecting detected agent model dependencies, available modes,
and resolving execution bindings before launching sandbox runs.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from app.models.dependency_model import (
    DependencyResolverRequest,
    DependencyResolverResult,
    AgentModelDependency,
    ExecutionModelBinding,
)
from app.services.store import store
from app.core.dependencies.dependency_resolver import DependencyResolver

router = APIRouter(prefix="/dependencies", tags=["Dependencies & Resolution"])


@router.post("/resolve", response_model=DependencyResolverResult)
def resolve_agent_dependencies(payload: DependencyResolverRequest):
    """Resolve available execution modes (Faithful, Compatible, Simulation) and bind execution model."""
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    result = DependencyResolver.resolve_mode(
        agent=agent,
        requested_mode=payload.requested_mode,
        provided_secrets=payload.provided_secrets
    )

    # Persist detected dependencies & binding in store
    for dep in result.detected_model_dependencies:
        store.save_agent_dependency_model(dep)

    if result.active_binding:
        store.save_execution_model_binding(result.active_binding)

    return result


@router.get("/agents/{agent_id}/models", response_model=List[AgentModelDependency])
def get_agent_model_dependencies(agent_id: str):
    """Retrieve all detected model dependencies for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    result = DependencyResolver.resolve_mode(agent=agent)
    return result.detected_model_dependencies
