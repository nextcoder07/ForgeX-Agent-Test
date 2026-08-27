"""
Model Connection and Provider Specification.
Supports local models (Ollama, vLLM, LM Studio, OpenAI-compatible local endpoints, custom HTTP)
and platform/test agent AI endpoints.
"""

from __future__ import annotations
import uuid
import datetime as dt
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class ModelConnection(BaseModel):
    id: str = Field(default_factory=lambda: f"model-conn-{uuid.uuid4().hex[:8]}")
    name: str
    owner_type: str = "USER"  # "FORGEX" | "USER"
    connection_type: str = "LOCAL_OLLAMA"  # "MANAGED_API", "USER_API", "LOCAL_OLLAMA", "LOCAL_VLLM", "LOCAL_LM_STUDIO", "CUSTOM_OPENAI_COMPATIBLE"
    provider: str = "ollama"  # ollama, vllm, lm_studio, openai_compatible, custom_http, huggingface
    base_url: str = "http://localhost:11434/v1"  # e.g., http://localhost:11434/v1 or http://localhost:8000/v1
    api_key: Optional[str] = None
    model_identifier: str = "qwen2.5-coder:7b"  # e.g., qwen2.5-coder:7b, llama3.1:8b, mistral:7b
    role: str = "test_agent_ai"  # platform_ai, test_agent_ai, user_connected_model
    context_window: int = 8192
    
    # Capabilities & Training Flags
    supports_structured_json: bool = True
    supports_tools: bool = True
    training_capability: str = "QLORA_4BIT"  # "QLORA_4BIT", "SFT_LORA", "DPO", "NONE"
    model_weight_access: str = "AVAILABLE"  # "AVAILABLE", "UNAVAILABLE"
    
    is_active: bool = True
    is_local: bool = True
    health_status: str = "UNKNOWN"  # HEALTHY, UNREACHABLE, ERROR, UNKNOWN
    last_ping_at: Optional[str] = None
    latency_ms: Optional[float] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelConnectionTestRequest(BaseModel):
    provider: str
    base_url: str
    model_identifier: str
    api_key: Optional[str] = None


class ModelConnectionTestResult(BaseModel):
    success: bool
    status: str
    message: str
    latency_ms: Optional[float] = None
    supports_chat: bool = False
    supports_json: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)
