"""
LLM Health Check & Model Probe API Endpoint.
Exposes real-time health, loaded key counts, active model, and connectivity status
without leaking sensitive API key secrets.
"""

from __future__ import annotations

import time
import os
from typing import Any, Dict
from fastapi import APIRouter
from app.core.llm.gemini_provider import LLMGenerationError
from app.core.llm.key_manager import GeminiKeyManager, OtherAIKeyManager
from app.core.llm.providers import get_platform_provider

router = APIRouter(prefix="/llm", tags=["LLM Health"])


@router.get("/health")
async def get_llm_health() -> Dict[str, Any]:
    """Probes the Google Gemini API to verify active model and key validity."""
    provider_name = os.getenv("PLATFORM_LLM_PROVIDER", "gemini").lower()
    key_mgr = OtherAIKeyManager() if provider_name in ("openrouter", "otherai", "open-router") else GeminiKeyManager()
    keys_status = key_mgr.get_all_keys_status()
    provider = get_platform_provider()

    available_keys = [k for k in keys_status if k["status"] == "AVAILABLE"]
    cooldown_keys = [k for k in keys_status if k["status"] == "COOLDOWN"]
    stopped_keys = [k for k in keys_status if k["status"] == "STOPPED"]

    health_info: Dict[str, Any] = {
        "status": "UNHEALTHY",
        "provider": provider_name,
        "configured_model": provider.model_name,
        "total_keys_configured": len(keys_status),
        "available_keys_count": len(available_keys),
        "cooldown_keys_count": len(cooldown_keys),
        "stopped_keys_count": len(stopped_keys),
        "keys": keys_status,
        "probe_latency_ms": None,
        "probe_error": None
    }

    if not key_mgr.keys:
        health_info["probe_error"] = f"No API keys configured for provider '{provider_name}'"
        return health_info

    # Perform minimal ping probe
    t0 = time.time()
    try:
        raw_res = await provider.generate(
            system="You are a health probe.",
            user='Respond with JSON: {"status": "ok"}',
            temperature=0.0,
            stage="HEALTH_PROBE"
        )
        latency = (time.time() - t0) * 1000.0
        health_info["status"] = "HEALTHY"
        health_info["probe_latency_ms"] = round(latency, 2)
    except LLMGenerationError as err:
        health_info["probe_error"] = err.to_dict()
    except Exception as e:
        health_info["probe_error"] = {"error": str(e)}

    return health_info
