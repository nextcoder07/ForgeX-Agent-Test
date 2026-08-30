"""
Agent Configuration, Encrypted Credentials & Setup State API Router.
Enforces multi-tenant user ownership, server-side encryption at rest,
and persistent configuration state in Supabase PostgreSQL.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status

from app.core.auth import get_current_user, UserRecord
from app.models.agent_config import (
    AgentConfigurationRecord,
    AgentCredentialRecord,
    AgentSetupStateRecord,
    CredentialStatusItem,
    SaveAgentCredentialRequest,
    ValidateCredentialRequest,
    ValidateCredentialResponse,
    UpdateAgentConfigurationRequest,
)
from app.core.security.crypto import encrypt_credential, decrypt_credential, mask_credential
from app.services.store import store
from app.services.activity_log import activity_log
from app.core.models_training.model_connection_manager import ModelConnectionManager

router = APIRouter(prefix="/agents", tags=["Agent Configuration & Credentials"])
conn_tester = ModelConnectionManager()


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


@router.get("/{agent_id}/configuration", response_model=AgentConfigurationRecord)
def get_agent_configuration(
    agent_id: str,
    current_user: UserRecord = Depends(get_current_user)
):
    """Retrieve user-scoped persistent configuration for a specific agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    cfg = store.get_agent_configuration(user_id=current_user.user_id, agent_id=agent_id)
    if not cfg:
        # Create default configuration initialized from agent spec / manifest
        manifest = getattr(agent, "runtime_manifest", {}) or {}
        slot_cfgs = manifest.get("slot_configs", {})
        default_mode = "faithful"
        default_provider = "openai"
        default_model = "default"
        if slot_cfgs:
            first_slot = next(iter(slot_cfgs.values()), {})
            default_provider = first_slot.get("provider", "openai")
            default_model = first_slot.get("model_identifier", "default")

        cfg = AgentConfigurationRecord(
            id=f"cfg-{current_user.user_id}-{agent_id}",
            user_id=current_user.user_id,
            agent_id=agent_id,
            execution_mode=default_mode,
            selected_provider=default_provider,
            selected_model=default_model,
            configuration_json={"slot_configs": slot_cfgs}
        )
        store.save_agent_configuration(cfg)

    return cfg


@router.patch("/{agent_id}/configuration", response_model=AgentConfigurationRecord)
def update_agent_configuration(
    agent_id: str,
    payload: UpdateAgentConfigurationRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    """Update user-scoped execution mode, provider, model, or slot configurations for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    cfg = store.get_agent_configuration(user_id=current_user.user_id, agent_id=agent_id)
    if not cfg:
        cfg = AgentConfigurationRecord(
            id=f"cfg-{current_user.user_id}-{agent_id}",
            user_id=current_user.user_id,
            agent_id=agent_id
        )

    if payload.execution_mode is not None:
        cfg.execution_mode = payload.execution_mode
    if payload.selected_provider is not None:
        cfg.selected_provider = payload.selected_provider
    if payload.selected_model is not None:
        cfg.selected_model = payload.selected_model

    current_json = dict(cfg.configuration_json or {})
    if payload.slot_configs is not None:
        current_json["slot_configs"] = payload.slot_configs
    if payload.configuration_json is not None:
        current_json.update(payload.configuration_json)
    cfg.configuration_json = current_json
    cfg.updated_at = _now()

    store.save_agent_configuration(cfg)

    # Invalidate previous setup state to force re-evaluation with updated configuration
    store.invalidate_agent_setup_state(user_id=current_user.user_id, agent_id=agent_id)

    activity_log.emit(
        category="CONFIG",
        action="AGENT_CONFIG_UPDATED",
        detail=f"Updated configuration for agent '{agent.name}' (Mode: {cfg.execution_mode}, Provider: {cfg.selected_provider}).",
        status="success"
    )
    return cfg


@router.get("/{agent_id}/credentials", response_model=List[CredentialStatusItem])
def list_agent_credentials(
    agent_id: str,
    current_user: UserRecord = Depends(get_current_user)
):
    """Retrieve safe metadata for required & saved API credentials for an agent (no raw secrets)."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # 1. Determine detected required keys from agent spec / manifest
    required_keys = set()
    spec = getattr(agent, "agent_spec", {}) or getattr(agent, "spec", {}) or {}
    if spec:
        for d in spec.get("dependencies", []):
            if d.get("name", "").endswith("_KEY"):
                required_keys.add(d["name"].upper())
        for env_var in spec.get("evidence_packet", {}).get("environment_variables", []):
            if env_var.endswith("_KEY"):
                required_keys.add(env_var.upper())

    manifest = getattr(agent, "runtime_manifest", {}) or {}
    for d in manifest.get("detected_model_dependencies", []):
        prov = d.get("provider", "").lower()
        if prov == "openai": required_keys.add("OPENAI_API_KEY")
        elif prov == "tavily": required_keys.add("TAVILY_API_KEY")
        elif prov == "openrouter": required_keys.add("OPENROUTER_API_KEY")
        elif prov == "gemini": required_keys.add("GEMINI_API_KEY")

    cfg = store.get_agent_configuration(user_id=current_user.user_id, agent_id=agent_id)
    if cfg and cfg.configuration_json.get("slot_configs"):
        for slot in cfg.configuration_json["slot_configs"].values():
            prov = slot.get("provider", "").lower()
            if prov == "openrouter": required_keys.add("OPENROUTER_API_KEY")
            elif prov == "openai": required_keys.add("OPENAI_API_KEY")
            elif prov == "gemini": required_keys.add("GEMINI_API_KEY")
            elif prov == "anthropic": required_keys.add("ANTHROPIC_API_KEY")
            elif prov == "groq": required_keys.add("GROQ_API_KEY")

    if not required_keys:
        required_keys.add("OPENAI_API_KEY")

    # 2. Fetch user's saved encrypted credentials for this agent from Supabase
    saved_creds = store.list_agent_credentials(user_id=current_user.user_id, agent_id=agent_id)
    saved_map = {c.credential_name.upper(): c for c in saved_creds if c.is_active}

    # 3. Assemble response items
    items: List[CredentialStatusItem] = []
    all_names = set(required_keys) | set(saved_map.keys())

    for key_name in sorted(all_names):
        saved = saved_map.get(key_name)
        is_req = key_name in required_keys

        if saved:
            items.append(CredentialStatusItem(
                credential_name=key_name,
                credential_type=saved.credential_type,
                provider=saved.provider or key_name.split("_")[0].lower(),
                configured=True,
                validation_status=saved.validation_status or "SAVED",
                source="USER_SAVED",
                masked=saved.masked_value,
                last_validated_at=saved.last_validated_at,
                is_required=is_req
            ))
        else:
            items.append(CredentialStatusItem(
                credential_name=key_name,
                credential_type="api_key",
                provider=key_name.split("_")[0].lower(),
                configured=False,
                validation_status="UNCONFIGURED",
                source="MISSING",
                masked=None,
                last_validated_at=None,
                is_required=is_req
            ))

    return items


@router.post("/{agent_id}/credentials", response_model=CredentialStatusItem)
def save_agent_credential(
    agent_id: str,
    payload: SaveAgentCredentialRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    """Encrypt and save a user-entered API credential for a specific agent in Supabase."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    key_name = payload.credential_name.upper().strip()
    raw_val = payload.credential_value.strip()

    if not raw_val:
        raise HTTPException(status_code=400, detail="Credential value cannot be empty")

    encrypted = encrypt_credential(raw_val)
    masked = mask_credential(raw_val)
    prov = payload.provider or key_name.split("_")[0].lower()

    cred_record = AgentCredentialRecord(
        id=f"cred-{current_user.user_id}-{agent_id}-{key_name.lower().replace('_', '-')}",
        user_id=current_user.user_id,
        agent_id=agent_id,
        credential_name=key_name,
        credential_type=payload.credential_type or "api_key",
        provider=prov,
        encrypted_value=encrypted,
        masked_value=masked,
        validation_status="SAVED",
        last_validated_at=None,
        is_active=True,
        updated_at=_now()
    )

    store.save_agent_credential(cred_record)

    # Invalidate previous setup state since credentials changed
    store.invalidate_agent_setup_state(user_id=current_user.user_id, agent_id=agent_id)

    activity_log.emit(
        category="CREDENTIALS",
        action="CREDENTIAL_SAVED",
        detail=f"Saved encrypted credential {key_name} ({masked}) for agent '{agent.name}'.",
        status="success"
    )

    return CredentialStatusItem(
        credential_name=key_name,
        credential_type=cred_record.credential_type,
        provider=prov,
        configured=True,
        validation_status="SAVED",
        source="USER_SAVED",
        masked=masked,
        last_validated_at=None,
        is_required=True
    )


@router.delete("/{agent_id}/credentials/{credential_name}")
def delete_agent_credential(
    agent_id: str,
    credential_name: str,
    current_user: UserRecord = Depends(get_current_user)
):
    """Deactivate or remove a saved API credential for an agent."""
    key_name = credential_name.upper().strip()
    store.delete_agent_credential(user_id=current_user.user_id, agent_id=agent_id, credential_name=key_name)
    store.invalidate_agent_setup_state(user_id=current_user.user_id, agent_id=agent_id)

    activity_log.emit(
        category="CREDENTIALS",
        action="CREDENTIAL_CLEARED",
        detail=f"Cleared credential {key_name} for agent '{agent_id}'.",
        status="warning"
    )
    return {"status": "cleared", "credential_name": key_name, "agent_id": agent_id}


@router.post("/{agent_id}/credentials/{credential_name}/validate", response_model=ValidateCredentialResponse)
async def validate_agent_credential(
    agent_id: str,
    credential_name: str,
    payload: Optional[ValidateCredentialRequest] = None,
    current_user: UserRecord = Depends(get_current_user)
):
    """Test live connectivity and validation status for a credential."""
    key_name = credential_name.upper().strip()
    raw_key = None

    if payload and payload.credential_value and payload.credential_value.strip():
        raw_key = payload.credential_value.strip()
    else:
        saved = store.get_agent_credential(user_id=current_user.user_id, agent_id=agent_id, credential_name=key_name)
        if saved and saved.encrypted_value:
            raw_key = decrypt_credential(saved.encrypted_value)

    if not raw_key:
        return ValidateCredentialResponse(
            credential_name=key_name,
            status="UNAVAILABLE",
            message="No credential provided or saved in vault."
        )

    provider = key_name.split("_")[0].lower()
    base_url = "https://openrouter.ai/api/v1" if provider == "openrouter" else ("https://api.openai.com/v1" if provider == "openai" else "")

    test_res = await conn_tester.test_connection(
        provider=provider,
        base_url=base_url,
        model_identifier="default",
        api_key=raw_key
    )

    status_str = "VALID" if test_res.success else "INVALID"
    msg = test_res.message or ("Key is active and reachable." if test_res.success else "Key authentication failed.")

    # Update validation status in Supabase if saved
    saved = store.get_agent_credential(user_id=current_user.user_id, agent_id=agent_id, credential_name=key_name)
    if saved:
        saved.validation_status = status_str
        saved.last_validated_at = _now()
        store.save_agent_credential(saved)

    return ValidateCredentialResponse(
        credential_name=key_name,
        status=status_str,
        message=msg,
        latency_ms=test_res.latency_ms or 0.0
    )


@router.get("/{agent_id}/setup/status", response_model=AgentSetupStateRecord)
def get_agent_setup_status(
    agent_id: str,
    current_user: UserRecord = Depends(get_current_user)
):
    """Retrieve persisted setup readiness and blockers for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    state = store.get_agent_setup_state(user_id=current_user.user_id, agent_id=agent_id)
    if not state or state.setup_status == "STALE":
        # Compute fresh preflight
        return compute_and_save_preflight(agent_id=agent_id, user_id=current_user.user_id)

    return state


@router.post("/{agent_id}/setup/preflight", response_model=AgentSetupStateRecord)
def run_agent_setup_preflight(
    agent_id: str,
    current_user: UserRecord = Depends(get_current_user)
):
    """Recompute setup readiness and persist to Supabase."""
    return compute_and_save_preflight(agent_id=agent_id, user_id=current_user.user_id)


def compute_and_save_preflight(agent_id: str, user_id: str) -> AgentSetupStateRecord:
    """Internal helper computing setup readiness and persisting to Supabase."""
    from app.core.dependencies.dependency_resolver import DependencyResolver
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    cfg = store.get_agent_configuration(user_id=user_id, agent_id=agent_id)
    exec_mode = cfg.execution_mode if cfg else "faithful"

    # Load decrypted user credentials for this agent
    saved_creds = store.list_agent_credentials(user_id=user_id, agent_id=agent_id)
    provided_secrets = {c.credential_name.upper(): decrypt_credential(c.encrypted_value) for c in saved_creds if c.is_active}

    # Evaluate demands
    from app.models.dependency_model import ExecutionMode
    mode_enum = ExecutionMode(exec_mode.lower()) if exec_mode.lower() in [e.value for e in ExecutionMode] else ExecutionMode.FAITHFUL
    prompt = DependencyResolver.evaluate_execution_credential_demands(
        agent=agent,
        provided_secrets=provided_secrets,
        mode=mode_enum
    )

    blockers = [r.key_name for r in prompt.requirements if not r.is_fulfilled and not r.is_optional]
    setup_status = "READY" if prompt.all_fulfilled else "NOT_READY"

    reqs_json = [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in prompt.requirements]

    state = AgentSetupStateRecord(
        id=f"setup-{user_id}-{agent_id}",
        user_id=user_id,
        agent_id=agent_id,
        setup_status=setup_status,
        preflight_status=setup_status,
        requirements_json=reqs_json,
        resolved_dependencies_json=[],
        blockers_json=blockers,
        last_checked_at=_now(),
        updated_at=_now()
    )
    store.save_agent_setup_state(state)
    return state
