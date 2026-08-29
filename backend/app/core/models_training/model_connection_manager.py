"""
Model Connection Manager.
Handles registration, health checking, capability testing, and invocation
for local endpoints (Ollama, vLLM, LM Studio, OpenAI-compatible, Custom HTTP)
and remote model providers.
"""

from __future__ import annotations

import time
import httpx
import logging
from typing import Dict, Any, Optional, List
from app.models.model_connection import ModelConnection, ModelConnectionTestResult

logger = logging.getLogger(__name__)


class ModelConnectionManager:
    """Manages local and remote model connections, runs health checks and latency tests."""

    async def test_connection(
        self,
        provider: str,
        base_url: str,
        model_identifier: str,
        api_key: Optional[str] = None
    ) -> ModelConnectionTestResult:
        """Pings endpoint, tests chat completion and structured JSON formatting across all providers."""
        provider_lower = (provider or "gemini").lower().strip()

        DEFAULT_PROVIDER_URLS = {
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "groq": "https://api.groq.com/openai/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "ollama": "http://localhost:11434/v1",
            "lm_studio": "http://localhost:1234/v1",
            "vllm": "http://localhost:8000/v1",
        }

        if not base_url or not base_url.strip():
            base_url = DEFAULT_PROVIDER_URLS.get(provider_lower, "https://generativelanguage.googleapis.com/v1beta")

        clean_base = base_url.strip().rstrip("/")
        start_time = time.time()
        latency_ms = 0.0

        try:
            async with httpx.AsyncClient(trust_env=False, timeout=25.0) as client:
                content = ""


                
                # 1. GOOGLE GEMINI NATIVE & OPENAI-COMPATIBLE
                if provider_lower == "gemini" or "generativelanguage.googleapis.com" in clean_base:
                    model_name = (model_identifier or "gemini-3.6-flash").strip()
                    # Check if base_url is openai-compatible or native
                    if "openai" in clean_base or clean_base.endswith("/v1"):
                        chat_url = f"{clean_base}/chat/completions" if not clean_base.endswith("/chat/completions") else clean_base
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}" if api_key else ""
                        }
                        payload = {
                            "model": model_name,
                            "messages": [{"role": "user", "content": "Respond strictly with JSON: {\"status\": \"ok\", \"ping\": \"pong\"}"}],
                            "temperature": 0.0,
                            "max_tokens": 50
                        }
                        chat_resp = await client.post(chat_url, json=payload, headers=headers)
                    else:
                        model_path = model_name if model_name.startswith("models/") else f"models/{model_name}"
                        chat_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
                        params = {"key": api_key} if api_key else {}
                        headers = {"Content-Type": "application/json"}
                        payload = {
                            "contents": [{"parts": [{"text": "Respond strictly with JSON: {\"status\": \"ok\", \"ping\": \"pong\"}"}]}],
                            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 50}
                        }
                        chat_resp = await client.post(chat_url, params=params, json=payload, headers=headers)

                    latency_ms = (time.time() - start_time) * 1000.0

                    if chat_resp.status_code in (200, 201):
                        body = chat_resp.json()
                        content = "ok"
                        if "candidates" in body and len(body["candidates"]) > 0:
                            content = body["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        elif "choices" in body and len(body["choices"]) > 0:
                            content = body["choices"][0].get("message", {}).get("content", "")
                        
                        supports_json = "status" in content or "ok" in content.lower() or "pong" in content.lower()
                        return ModelConnectionTestResult(
                            success=True,
                            status="HEALTHY",
                            message=f"Connected to Google Gemini ({model_name}) in {latency_ms:.1f}ms",
                            latency_ms=round(latency_ms, 2),
                            supports_chat=True,
                            supports_json=supports_json,
                            details={"sample_response": content[:150], "provider": "Google Gemini", "requested_model": model_name}
                        )
                    else:
                        try:
                            err_json = chat_resp.json()
                            err_text = err_json.get("error", {}).get("message") or chat_resp.text[:200]
                        except Exception:
                            err_text = chat_resp.text[:200]

                        return ModelConnectionTestResult(
                            success=False,
                            status="ERROR",
                            message=f"Gemini API ({model_name}) returned HTTP {chat_resp.status_code}: {err_text}. Ensure API key is valid.",
                            latency_ms=round(latency_ms, 2),
                            supports_chat=False,
                            supports_json=False,
                            details={"http_status": chat_resp.status_code, "model_tested": model_name}
                        )

                # 2. ANTHROPIC CLAUDE NATIVE
                elif provider_lower == "anthropic" or "api.anthropic.com" in clean_base:
                    chat_url = f"{clean_base}/messages" if not clean_base.endswith("/messages") else clean_base
                    headers = {
                        "Content-Type": "application/json",
                        "x-api-key": api_key or "",
                        "anthropic-version": "2023-06-01"
                    }
                    payload = {
                        "model": model_identifier or "claude-3-5-sonnet-20241022",
                        "max_tokens": 50,
                        "messages": [{"role": "user", "content": "Respond strictly with JSON: {\"status\": \"ok\", \"ping\": \"pong\"}"}]
                    }
                    chat_resp = await client.post(chat_url, json=payload, headers=headers)
                    latency_ms = (time.time() - start_time) * 1000.0

                    if chat_resp.status_code in (200, 201):
                        body = chat_resp.json()
                        content = body.get("content", [{}])[0].get("text", "")
                        return ModelConnectionTestResult(
                            success=True,
                            status="HEALTHY",
                            message=f"Connected to Anthropic ({model_identifier}) in {latency_ms:.1f}ms",
                            latency_ms=round(latency_ms, 2),
                            supports_chat=True,
                            supports_json=True,
                            details={"sample_response": content[:150], "provider": "Anthropic"}
                        )
                    else:
                        return ModelConnectionTestResult(
                            success=False,
                            status="ERROR",
                            message=f"Anthropic returned HTTP {chat_resp.status_code}: {chat_resp.text[:180]}",
                            latency_ms=round(latency_ms, 2),
                            supports_chat=False,
                            supports_json=False,
                            details={"http_status": chat_resp.status_code}
                        )

                # 3. LOCAL ML MODELS (OLLAMA / LM STUDIO / VLLM) AND CLOUD APIS (OPENAI / OPENROUTER / GROQ / DEEPSEEK)
                else:
                    is_local = provider_lower in ["ollama", "lm_studio", "vllm"] or "localhost" in clean_base or "127.0.0.1" in clean_base
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    if provider_lower == "openrouter" or "openrouter.ai" in clean_base:
                        headers["HTTP-Referer"] = "https://forgex.dev"
                        headers["X-Title"] = "ForgeX Agent Platform"

                    chat_url = f"{clean_base}/chat/completions"
                    if provider_lower == "ollama" and not clean_base.endswith("/v1"):
                        chat_url = f"{clean_base}/api/chat"

                    # 3A. For local models, check model availability first via catalog endpoint
                    if is_local:
                        models_endpoint = f"{clean_base}/models" if clean_base.endswith("/v1") else f"{clean_base}/api/tags"
                        try:
                            cat_resp = await client.get(models_endpoint, timeout=5.0)
                            if cat_resp.status_code == 200:
                                cat_data = cat_resp.json()
                                # Extract list of local model names
                                installed_models = []
                                if "data" in cat_data and isinstance(cat_data["data"], list):
                                    installed_models = [m.get("id", "") for m in cat_data["data"]]
                                elif "models" in cat_data and isinstance(cat_data["models"], list):
                                    installed_models = [m.get("name", "") or m.get("model", "") for m in cat_data["models"]]

                                # Normalize model search (e.g. qwen2.5-coder:3b)
                                target_norm = (model_identifier or "").lower().strip()
                                match_found = any(target_norm in m.lower() or m.lower() in target_norm for m in installed_models if m)

                                if installed_models and not match_found and target_norm:
                                    avail_str = ", ".join(installed_models[:5])
                                    return ModelConnectionTestResult(
                                        success=False,
                                        status="MODEL_NOT_FOUND",
                                        message=f"Local server is reachable at {clean_base}, but model '{model_identifier}' is not pulled. Available local models: [{avail_str}]. Run 'ollama pull {model_identifier}' to download it.",
                                        latency_ms=round((time.time() - start_time) * 1000.0, 2),
                                        supports_chat=False,
                                        supports_json=False,
                                        details={"installed_models": installed_models}
                                    )
                        except Exception as e:
                            logger.debug(f"Catalog check skipped for {clean_base}: {e}")

                    # 3B. Perform lightweight inference ping
                    model_target = model_identifier or ("llama3.2" if is_local else "gpt-4o-mini")
                    if (provider_lower == "openrouter" or "openrouter.ai" in clean_base) and "/" not in model_target:
                        model_target = f"openai/{model_target}"

                    test_payload: Dict[str, Any] = {
                        "model": model_target,
                        "messages": [
                            {"role": "user", "content": "Respond strictly with JSON: {\"status\": \"ok\", \"ping\": \"pong\"}"}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 50
                    }

                    chat_resp = await client.post(chat_url, json=test_payload, headers=headers)
                    latency_ms = (time.time() - start_time) * 1000.0

                    if chat_resp.status_code in (200, 201):
                        body = chat_resp.json()
                        content = ""
                        if "choices" in body and len(body["choices"]) > 0:
                            content = body["choices"][0].get("message", {}).get("content", "")
                        elif "message" in body:
                            content = body["message"].get("content", "")

                        supports_json = "status" in content or "ok" in content.lower() or "pong" in content.lower()

                        return ModelConnectionTestResult(
                            success=True,
                            status="HEALTHY",
                            message=f"Connected to {provider.upper()} ({model_identifier}) in {latency_ms:.1f}ms",
                            latency_ms=round(latency_ms, 2),
                            supports_chat=True,
                            supports_json=supports_json,
                            details={"sample_response": content[:150], "endpoint": clean_base}
                        )
                    else:
                        code = chat_resp.status_code
                        err_preview = chat_resp.text.strip()
                        if "<html" in err_preview.lower() or "<!doctype" in err_preview.lower():
                            err_clean = f"HTTP {code} ({chat_resp.reason_phrase or 'Gateway Error'})"
                        else:
                            err_clean = err_preview[:150]

                        # Context-aware error message tailored to local vs cloud
                        if is_local:
                            if code == 504:
                                msg = f"Local server returned HTTP 504 (Gateway Timeout). Ollama or local engine timed out loading model '{model_identifier}' into RAM/GPU VRAM. Ensure sufficient system resources are available."
                            elif code == 404:
                                msg = f"Local model '{model_identifier}' or endpoint not found (HTTP 404) at {clean_base}. Run 'ollama pull {model_identifier}' to download the model weights."
                            else:
                                msg = f"Local server returned HTTP {code}: {err_clean}."
                        else:
                            if code in (401, 403):
                                msg = f"Authentication failed (HTTP {code}). Check your API Key for {provider.upper()}."
                            elif code == 404:
                                msg = f"Model '{model_identifier}' or endpoint not found (HTTP 404). Verify model identifier."
                            elif code == 504:
                                msg = f"Gateway Timeout (HTTP 504) connecting to {provider.upper()} endpoint."
                            else:
                                msg = f"Endpoint returned {err_clean}. Verify model identifier and API key."

                        return ModelConnectionTestResult(
                            success=False,
                            status="ERROR",
                            message=msg,
                            latency_ms=round(latency_ms, 2),
                            supports_chat=False,
                            supports_json=False,
                            details={"http_status": code, "raw_response": err_preview[:200]}
                        )

        except httpx.ConnectError:
            return ModelConnectionTestResult(
                success=False,
                status="UNREACHABLE",
                message=f"Could not connect to {clean_base}. Ensure the local model server (Ollama/LM Studio) or API endpoint is running and reachable.",
                supports_chat=False,
                supports_json=False,
                details={"error_type": "ConnectError", "target_url": clean_base}
            )
        except httpx.TimeoutException:
            return ModelConnectionTestResult(
                success=False,
                status="TIMEOUT",
                message=f"Connection to {clean_base} timed out after 25 seconds. Local model server or cloud API may be slow or loading weights.",
                supports_chat=False,
                supports_json=False,
                details={"error_type": "Timeout"}
            )

        except Exception as ex:
            return ModelConnectionTestResult(
                success=False,
                status="ERROR",
                message=f"Error connecting to model: {str(ex)}",
                supports_chat=False,
                supports_json=False,
                details={"exception": str(ex)}
            )
