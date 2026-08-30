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
from app.core.auth import get_current_user, UserRecord
from fastapi import Depends

router = APIRouter(prefix="/dependencies", tags=["Dependencies & Resolution"])

# In-memory custom user system credentials override cache mapped by user_id
_USER_SYSTEM_CREDENTIALS: Dict[str, Dict[str, str]] = {}


def _get_effective_user_credentials(user_id: Optional[str] = None) -> Dict[str, str]:
    """Retrieves user-scoped credentials from user memory, Supabase store, and environment fallback."""
    import os
    uid = user_id or "default_user"
    creds: Dict[str, str] = dict(_USER_SYSTEM_CREDENTIALS.get(uid, {}))

    # Hydrate from Supabase model_connections scoped to user
    try:
        conns = store.list_model_connections()
        for conn in conns:
            api_key = getattr(conn, "api_key", None) or (conn.get("api_key") if isinstance(conn, dict) else None)
            conn_uid = getattr(conn, "user_id", None) or (conn.get("user_id") if isinstance(conn, dict) else None)
            cid = getattr(conn, "id", "") or (conn.get("id", "") if isinstance(conn, dict) else "")
            name = getattr(conn, "name", "") or (conn.get("name", "") if isinstance(conn, dict) else "")
            provider = getattr(conn, "provider", "") or (conn.get("provider", "") if isinstance(conn, dict) else "")

            # Match user-specific connection or unowned platform connection
            is_match = (conn_uid == uid) or cid.startswith(f"conn-{uid}-") or (not conn_uid and not cid.startswith("conn-user-"))

            if is_match and api_key and api_key.strip():
                if name.startswith("User ") and name.replace("User ", "").endswith("_KEY"):
                    k = name.replace("User ", "").upper()
                elif provider:
                    k = f"{provider.upper()}_API_KEY"
                else:
                    k = "OPENAI_API_KEY"
                if k not in creds:
                    creds[k] = api_key.strip()
    except Exception:
        pass

    # Hydrate from Supabase dependency_bindings for agents belonging to user
    try:
        bindings = store.list_dependency_bindings()
        user_agent_ids = {a.id for a in store.list_agents() if getattr(a, "owner_id", None) in (None, uid)}
        for b in bindings:
            agent_id = getattr(b, "agent_id", "") or (b.get("agent_id") if isinstance(b, dict) else "")
            if agent_id in user_agent_ids:
                dep_name = getattr(b, "dependency_name", None) or (b.get("dependency_name") if isinstance(b, dict) else None)
                user_val = getattr(b, "user_value", None) or (b.get("user_value") if isinstance(b, dict) else None)
                if dep_name and user_val and user_val.strip() and dep_name.upper() not in creds:
                    creds[dep_name.upper()] = user_val.strip()
    except Exception:
        pass

    return creds


@router.get("/system-credentials", response_model=List[SystemCredentialItem])
def get_platform_system_credentials(current_user: UserRecord = Depends(get_current_user)):
    """Retrieve platform system API keys and user-configured credentials for active user."""
    effective = _get_effective_user_credentials(user_id=current_user.user_id)
    return DependencyResolver.get_system_credentials(effective)


@router.post("/system-credentials", response_model=List[SystemCredentialItem])
def update_platform_system_credentials(
    payload: ProvideCredentialsRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    """Update or override user-specific API keys, persist per-user in Supabase, and reload active key managers."""
    import logging
    from app.models.model_connection import ModelConnection
    from app.models.intake import DependencyBinding
    logger = logging.getLogger(__name__)
    uid = current_user.user_id

    if uid not in _USER_SYSTEM_CREDENTIALS:
        _USER_SYSTEM_CREDENTIALS[uid] = {}

    for k, v in payload.credentials.items():
        key_upper = k.upper().strip()
        if v and v.strip():
            val_clean = v.strip()
            _USER_SYSTEM_CREDENTIALS[uid][key_upper] = val_clean

            # Persist to Supabase model_connections table scoped to user
            try:
                conn_id = f"conn-{uid}-{key_upper.lower().replace('_', '-')}"
                conn = ModelConnection(
                    id=conn_id,
                    name=f"User {key_upper}",
                    provider=key_upper.split('_')[0].lower(),
                    base_url="https://api.openai.com/v1" if "OPENAI" in key_upper else "",
                    model_identifier="default",
                    api_key=val_clean,
                    role="general",
                    status="active"
                )
                store.save_model_connection(conn)
            except Exception as e:
                logger.debug(f"Could not persist user model connection to Supabase: {e}")

            # Persist to Supabase dependency_bindings for user's agents
            try:
                for agent in store.list_agents():
                    if getattr(agent, "owner_id", None) in (None, uid):
                        bind_id = f"bind-{agent.id}-{key_upper.lower().replace('_', '-')}"
                        binding = DependencyBinding(
                            id=bind_id,
                            agent_id=agent.id,
                            dependency_name=key_upper,
                            resolution_type="user_value",
                            status="ready",
                            user_value=val_clean
                        )
                        store.save_dependency_binding(binding)
            except Exception as e:
                logger.debug(f"Could not persist user dependency binding to Supabase: {e}")

        elif key_upper in _USER_SYSTEM_CREDENTIALS[uid] and (v == "" or v is None):
            _USER_SYSTEM_CREDENTIALS[uid].pop(key_upper, None)
            conn_id = f"conn-{uid}-{key_upper.lower().replace('_', '-')}"
            store.delete_model_connection(conn_id)

    try:
        from app.core.llm.key_manager import UnifiedKeyManager
        UnifiedKeyManager().load_keys()
    except Exception:
        pass

    effective = _get_effective_user_credentials(user_id=uid)
    return DependencyResolver.get_system_credentials(effective)


@router.get("/agents/{agent_id}/required-credentials", response_model=SessionCredentialPrompt)
def get_agent_required_credentials(
    agent_id: str,
    mode: Optional[ExecutionMode] = Query(default=ExecutionMode.FAITHFUL),
    current_user: UserRecord = Depends(get_current_user)
):
    """Retrieve mode-specific required API key demands for an agent before execution for active user."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    effective = _get_effective_user_credentials(user_id=current_user.user_id)
    return DependencyResolver.evaluate_execution_credential_demands(
        agent=agent,
        provided_secrets=effective,
        mode=mode or ExecutionMode.FAITHFUL
    )


@router.post("/resolve", response_model=DependencyResolverResult)
def resolve_agent_dependencies(
    payload: DependencyResolverRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    """Resolve available execution modes (Faithful, Compatible, Simulation) and bind execution model for active user."""
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    effective = _get_effective_user_credentials(user_id=current_user.user_id)
    combined_secrets = {**effective, **payload.provided_secrets}

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

