"""
Model Connections API.
Endpoints to connect, list, test, and manage local LLMs (Ollama, vLLM, LM Studio, OpenAI-compatible)
and platform endpoints.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.model_connection import ModelConnection, ModelConnectionTestRequest, ModelConnectionTestResult
from app.core.models_training.model_connection_manager import ModelConnectionManager
from app.services.store import store
from app.services.activity_log import activity_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["Model Connections"])
manager = ModelConnectionManager()


@router.get("/connections", response_model=List[ModelConnection])
async def list_connections(role: Optional[str] = Query(None, description="Filter by role: platform_ai, test_agent_ai, user_connected_model")):
    """List all registered model connections."""
    conns = store.list_model_connections()
    if role:
        conns = [c for c in conns if c.role == role]
    return conns


@router.post("/connections", response_model=ModelConnection)
async def create_connection(conn: ModelConnection):
    """Register a new local or remote model connection."""
    # Test connection health on registration
    test_res = await manager.test_connection(
        provider=conn.provider,
        base_url=conn.base_url,
        model_identifier=conn.model_identifier,
        api_key=conn.api_key
    )
    conn.health_status = test_res.status
    conn.latency_ms = test_res.latency_ms
    conn.supports_structured_json = test_res.supports_json

    store.save_model_connection(conn)
    activity_log.emit(
        category="RUNTIME",
        action="MODEL_CONNECTED",
        detail=f"Connected model {conn.name} ({conn.provider} - {conn.model_identifier}). Status: {conn.health_status}",
        status="success" if test_res.success else "warning"
    )
    return conn


@router.post("/connections/test", response_model=ModelConnectionTestResult)
async def test_connection_endpoint(req: ModelConnectionTestRequest):
    """Tests reachability, chat completion, and structured JSON output for a model endpoint."""
    return await manager.test_connection(
        provider=req.provider,
        base_url=req.base_url,
        model_identifier=req.model_identifier,
        api_key=req.api_key
    )


@router.post("/connections/{conn_id}/set-active", response_model=ModelConnection)
async def set_active_connection(conn_id: str):
    """Set a specific model connection as the active primary model."""
    conns = store.list_model_connections()
    target_conn = None
    for c in conns:
        if c.id == conn_id:
            c.is_active = True
            target_conn = c
            store.save_model_connection(c)
        elif c.is_active:
            c.is_active = False
            store.save_model_connection(c)
            
    if not target_conn:
        raise HTTPException(status_code=404, detail="Model connection not found")
        
    activity_log.emit(
        category="RUNTIME",
        action="MODEL_ACTIVATED",
        detail=f"Model connection '{target_conn.name}' ({target_conn.provider} - {target_conn.model_identifier}) is now ACTIVE.",
        status="success"
    )
    return target_conn


@router.put("/connections/{conn_id}", response_model=ModelConnection)
async def update_connection(conn_id: str, payload: ModelConnection):
    """Update/edit an existing model connection."""
    existing = store.get_model_connection(conn_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Model connection not found")

    # Retest connection health on update
    test_res = await manager.test_connection(
        provider=payload.provider,
        base_url=payload.base_url,
        model_identifier=payload.model_identifier,
        api_key=payload.api_key
    )
    payload.id = conn_id
    payload.health_status = test_res.status
    payload.latency_ms = test_res.latency_ms
    payload.supports_structured_json = test_res.supports_json

    store.save_model_connection(payload)
    activity_log.emit(
        category="RUNTIME",
        action="MODEL_UPDATED",
        detail=f"Updated model connection '{payload.name}' ({payload.provider} - {payload.model_identifier}). Status: {payload.health_status}",
        status="success" if test_res.success else "warning"
    )
    return payload


@router.get("/agent-bindings/{agent_id}")
async def get_agent_model_bindings(agent_id: str):
    """Get the detected multi-model requirements and active bindings for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    code_text = " ".join(agent.source_files.values()) if agent.source_files else ""

    # Call DependencyDetector to get all dynamic model dependencies
    from app.core.intake.dependency_detector import DependencyDetector
    detected_deps = DependencyDetector.detect_model_dependencies(agent_id, code_text, [])

    # Get stored bindings if any in runtime_manifest
    stored_bindings = agent.runtime_manifest.get("model_bindings", {})

    slots = []
    for idx, dep in enumerate(detected_deps):
        # Extract variable name from detected_from, e.g. "Line assignment to router_llm" -> "router_llm"
        var_name = "llm_client"
        if "assignment to" in dep.detected_from:
            var_name = dep.detected_from.split("assignment to")[-1].strip()
        elif "import" in dep.detected_from:
            var_name = f"imported_{dep.provider}_llm"

        slot_id = var_name
        env_var_name = f"{dep.provider.upper()}_API_KEY" if dep.provider else "OPENAI_API_KEY"
        slots.append({
            "slot_id": slot_id,
            "name": f"AI Position: {var_name}",
            "code_variable": var_name,
            "env_var": env_var_name,
            "description": f"Code Variable: '{var_name}' | Injects Env: {env_var_name} | Provider: {dep.provider.upper()} (default: {dep.model_name}).",
            "explanation": f"In code, variable '{var_name}' is initialized using {dep.provider.upper()} SDK. Connecting an API key populates {env_var_name} for this instance.",
            "detected_from_source": dep.model_name,
            "bound_connection_id": stored_bindings.get(slot_id, "system_default"),
            "category": "INFERENCE"
        })

    # Add the platform safety critic/evaluator slot
    slots.append({
        "slot_id": "critic_llm",
        "name": "AI Position: critic_llm (Safety Judge)",
        "code_variable": "critic_llm",
        "env_var": "PLATFORM_SAFETY_LLM",
        "description": "Platform safety evaluator LLM auditing multi-turn sandbox traces against constitutional rules.",
        "explanation": "Platform-level safety judge that evaluates multi-turn trace outputs against agent constitution guardrails.",
        "detected_from_source": "gemini-2.5-flash",
        "bound_connection_id": stored_bindings.get("critic_llm", "system_default"),
        "category": "EVALUATION"
    })

    # Check for available trained model adapters for this agent
    available_adapters = [mv.model_dump() for mv in store.list_model_versions(agent_id)]
    if available_adapters:
        slots.append({
            "slot_id": "trained_adapter",
            "name": "AI Position: trained_adapter (Fine-Tuned Checkpoint)",
            "description": "Custom trained weights with specialized alignment from Stage 8 Training.",
            "detected_from_source": available_adapters[0]["adapter_name"],
            "bound_connection_id": stored_bindings.get("trained_adapter", "none"),
            "category": "TRAINED_WEIGHTS"
        })

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "slots": slots,
        "available_adapters": available_adapters
    }


@router.post("/agent-bindings/{agent_id}")
async def update_agent_model_bindings(agent_id: str, bindings: dict):
    """Save multi-model slot assignments for an agent."""
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.runtime_manifest:
        agent.runtime_manifest = {}
    
    agent.runtime_manifest["model_bindings"] = bindings
    store.save_agent(agent)

    activity_log.emit(
        category="RUNTIME",
        action="MODEL_BINDINGS_UPDATED",
        detail=f"Updated multi-model slot bindings for agent '{agent.name}'.",
        status="success"
    )
    return {"status": "success", "agent_id": agent.id, "bindings": bindings}


@router.delete("/connections/{conn_id}")
async def delete_connection(conn_id: str):
    """Delete a registered model connection."""
    conn = store.get_model_connection(conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Model connection not found")
    store.delete_model_connection(conn_id)
    return {"status": "deleted", "id": conn_id}
