"""
Unified Key Manager & AI Rotation Provider.
Supports dynamic loading of AI_API_KEY_1..AI_API_KEY_n, OPENROUTER_API_KEY, GEMINI_API_KEY,
Ollama Local Server, and Least-Recently-Used (LRU) round-robin key rotation.
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class AIKey:
    key_id: str
    value: str
    api_name: str
    model_name: str
    priority: int = 100
    is_active: bool = True
    cooldown_until: float = 0.0
    failure_count: int = 0
    total_calls: int = 0
    total_tokens: int = 0
    last_used_at: float = 0.0
    consecutive_successes: int = 0

    @property
    def is_available(self) -> bool:
        return self.is_active and time.time() >= self.cooldown_until


class UnifiedKeyManager:
    """Manages all registered AI API keys with strict sequential priority (1 -> 2 -> 3...), cooldowns, and stage-specific fallbacks."""
    _instance: Optional[UnifiedKeyManager] = None

    def __new__(cls) -> UnifiedKeyManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.keys = []
            cls._instance.meta_keys = []
            cls._instance.load_keys()
        return cls._instance

    def load_keys(self) -> None:
        """Loads all AI API keys dynamically from environment variables in strict priority order."""
        self.keys.clear()
        self.meta_keys.clear()
        
        # 1. Load universal AI_API_KEY_n format for the 4 Platform Stages in strict priority order (1, 2, 3...)
        for index in range(1, 100):
            value = os.getenv(f"AI_API_KEY_{index}", "").strip()
            if not value:
                continue
            api_name = os.getenv(f"AI_API_NAME_{index}", "gemini").strip().lower()
            model_name = os.getenv(f"AI_MODEL_{index}", "").strip()
            if not model_name:
                model_name = "gemini-3.6-flash" if api_name in ("gemini", "google") else "openai/gpt-4o-mini"

            if not any(k.value == value for k in self.keys):
                display_id = f"AI API Key {index}"
                self.keys.append(AIKey(
                    key_id=display_id,
                    value=value,
                    api_name=api_name,
                    model_name=model_name,
                    priority=index
                ))
                logger.info(f"Registered {display_id} (priority={index}, {api_name} - {model_name})")

        # 2. Legacy fallback for GEMINI_API_KEY and GEMINI_API_KEY_n
        gemini_main = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()

        if gemini_main and not any(k.value == gemini_main for k in self.keys):
            self.keys.append(AIKey(
                key_id="Gemini Legacy Key Main",
                value=gemini_main,
                api_name="gemini",
                model_name=gemini_model,
                priority=100
            ))
            logger.info(f"Registered GEMINI_API_KEY as 'Gemini Legacy Key Main' ({gemini_model})")

        for idx in range(1, 10):
            gemini_val = os.getenv(f"GEMINI_API_KEY_{idx}", "").strip()
            if gemini_val and not any(k.value == gemini_val for k in self.keys):
                self.keys.append(AIKey(
                    key_id=f"Gemini Legacy Key {idx}",
                    value=gemini_val,
                    api_name="gemini",
                    model_name=gemini_model,
                    priority=100 + idx
                ))

        # 3. Fallback for OPENROUTER_API_KEY
        openrouter_main = os.getenv("OPENROUTER_API_KEY", "").strip()
        openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
        if openrouter_main and not any(k.value == openrouter_main for k in self.keys):
            self.keys.append(AIKey(
                key_id="OpenRouter Main Key",
                value=openrouter_main,
                api_name="openrouter",
                model_name=openrouter_model,
                priority=200
            ))

        # 4. Ollama Local Endpoint for Stage Fallbacks
        ollama_endpoint = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")).strip()
        ollama_model = os.getenv("OLLAMA_DEFAULT_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")).strip()
        self.keys.append(AIKey(
            key_id="Ollama Local Server",
            value=ollama_endpoint,
            api_name="ollama",
            model_name=ollama_model
        ))
        logger.info(f"Registered Ollama Local Server ({ollama_endpoint} - {ollama_model})")

        # 5. Independent Meta-Evaluator Keys (Rotation Pool + Dedicated Ollama Fallback)
        for idx in range(1, 20):
            meta_val = os.getenv(f"META_EVALUATOR_API_KEY_{idx}", "").strip()
            if not meta_val:
                continue
            m_provider = os.getenv(f"META_EVALUATOR_PROVIDER_{idx}", "gemini").strip().lower()
            m_model = os.getenv(f"META_EVALUATOR_MODEL_{idx}", "gemini-3.6-flash").strip()
            self.meta_keys.append(AIKey(
                key_id=f"Meta Evaluator Key {idx}",
                value=meta_val,
                api_name=m_provider,
                model_name=m_model
            ))

        meta_single = os.getenv("META_EVALUATOR_API_KEY", "").strip()
        if meta_single and not any(k.value == meta_single for k in self.meta_keys):
            m_provider = os.getenv("META_EVALUATOR_PROVIDER", "gemini").strip().lower()
            m_model = os.getenv("META_EVALUATOR_MODEL", "gemini-3.6-flash").strip()
            self.meta_keys.append(AIKey(
                key_id="Meta Evaluator Primary Key",
                value=meta_single,
                api_name=m_provider,
                model_name=m_model
            ))

        # Meta Evaluator Dedicated Local Ollama Fallback
        meta_ollama_model = os.getenv("META_EVALUATOR_OLLAMA_MODEL", "qwen2.5-coder:7b").strip()
        self.meta_keys.append(AIKey(
            key_id="Meta Evaluator Ollama Fallback",
            value=ollama_endpoint,
            api_name="ollama",
            model_name=meta_ollama_model
        ))
        logger.info(f"Registered Meta Evaluator Ollama Fallback ({ollama_endpoint} - {meta_ollama_model})")

    @classmethod
    def get_stage_fallback_model(cls, stage_name: str) -> str:
        """Returns the dedicated trainable local model / adapter for a given stage."""
        stage_clean = stage_name.lower().replace("-", "_")
        if "intake" in stage_clean or "analysis" in stage_clean:
            return os.getenv("OLLAMA_INTAKE_MODEL", "qwen2.5-coder:7b").strip()
        elif "scenario" in stage_clean:
            return os.getenv("OLLAMA_SCENARIO_MODEL", "qwen2.5-coder:7b").strip()
        elif "observer" in stage_clean or "execution" in stage_clean:
            return os.getenv("OLLAMA_OBSERVER_MODEL", "qwen2.5-coder:7b").strip()
        elif "repair" in stage_clean or "fix" in stage_clean or "improvement" in stage_clean:
            return os.getenv("OLLAMA_REPAIR_MODEL", "qwen2.5-coder:7b").strip()
        elif "meta" in stage_clean or "evaluator" in stage_clean or "judge" in stage_clean:
            return os.getenv("META_EVALUATOR_OLLAMA_MODEL", "qwen2.5-coder:7b").strip()
        return os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b").strip()

    def select_key(self, api_name: Optional[str] = None) -> Optional[AIKey]:
        """Selects the best available key using LRU (Least-Recently-Used) round-robin."""
        return self._select_from_pool(self.keys, api_name)

    def select_meta_key(self, api_name: Optional[str] = None) -> Optional[AIKey]:
        """Selects the best available key for the independent Meta-Evaluator."""
        chosen = self._select_from_pool(self.meta_keys, api_name)
        if chosen is None:
            # Fallback to general pool if no dedicated meta key configured
            return self.select_key(api_name)
        return chosen

    def _select_from_pool(self, pool: List[AIKey], api_name: Optional[str] = None) -> Optional[AIKey]:
        now = time.time()
        
        # 1. Reset any keys whose cooldown time has expired
        for k in pool:
            if k.cooldown_until > 0 and now >= k.cooldown_until:
                k.cooldown_until = 0.0
                k.failure_count = 0

        # 2. Simple sequential traversal: check cloud keys in exact order (1 -> 2 -> 3 -> ... -> N)
        cloud_keys = [
            k for k in pool 
            if k.api_name not in ("ollama", "local") and (api_name is None or k.api_name.lower() == api_name.lower())
        ]
        cloud_keys.sort(key=lambda k: k.priority)

        for k in cloud_keys:
            if k.is_available:
                k.last_used_at = now
                k.total_calls += 1
                return k

        # 3. If all cloud keys are exhausted/on cooldown, select local Ollama LLM
        local_keys = [
            k for k in pool 
            if k.api_name in ("ollama", "local") and (api_name is None or k.api_name.lower() == api_name.lower())
        ]
        for k in local_keys:
            if k.is_available:
                k.last_used_at = now
                k.total_calls += 1
                return k

        return None

    def report_success(self, key_id: str, tokens: int = 0) -> None:
        for k in self.keys:
            if k.key_id == key_id:
                k.failure_count = 0
                k.consecutive_successes += 1
                k.total_tokens += tokens
                break

    def mark_key_success(self, key_id: str, tokens: int = 0) -> None:
        self.report_success(key_id, tokens)

    def report_failure(self, key_id: str, error: Any = None) -> None:
        now = time.time()
        for k in self.keys:
            if k.key_id == key_id:
                k.failure_count += 1
                k.consecutive_successes = 0
                err_type, _ = classify_error(error)
                if err_type == "AUTHENTICATION_ERROR":
                    k.is_active = False
                    k.cooldown_until = now + 86400.0  # Deactivate invalid key for 24h
                    logger.warning(f"Key '{key_id}' permanently deactivated due to authentication failure (401/Invalid Key). Rotating to next available key.")
                else:
                    cooldown_secs = 60.0 if err_type == "RATE_LIMITED" else 30.0
                    k.cooldown_until = now + cooldown_secs
                    logger.warning(f"Key '{key_id}' placed on cooldown ({cooldown_secs}s) due to failure: {error}")
                break


    def mark_key_failed(self, key_id: str, error_type: str = "ERROR", error_msg: str = "") -> None:
        self.report_failure(key_id, f"{error_type}: {error_msg}")


class SessionManager:
    """Helper for managing user / stage AI session keys."""
    def __init__(self):
        self.manager = UnifiedKeyManager()

    def get_key(self, api_name: Optional[str] = None) -> Optional[AIKey]:
        return self.manager.select_key(api_name)


def classify_error(err: Any) -> tuple[str, str]:
    """Classifies an error into (error_type, error_category)."""
    err_str = str(err).lower()
    if "401" in err_str or "unauthenticated" in err_str or "unauthorized" in err_str or "invalid api key" in err_str or "invalid_api_key" in err_str:
        return "AUTHENTICATION_ERROR", "AUTHENTICATION_ERROR"
    if "429" in err_str or "quota" in err_str or "rate" in err_str or "resource_exhausted" in err_str:
        return "RATE_LIMITED", "RATE_LIMITED"
    if "504" in err_str or "gateway" in err_str or "timeout" in err_str or "timed out" in err_str:
        return "SERVER_ERROR", "SERVER_ERROR"
    if "404" in err_str or "not found" in err_str:
        return "MODEL_NOT_FOUND", "MODEL_NOT_FOUND"
    return "UNKNOWN", "UNKNOWN"


def is_rotation_eligible(err: Any) -> bool:
    if isinstance(err, tuple):
        category = err[1]
    else:
        category = str(err)
    return category in ("RATE_LIMITED", "SERVER_ERROR", "AUTHENTICATION_ERROR", "UNKNOWN")


class TestAgentKeyManager:
    """Provides active AI and tool credentials for sandboxed test agents."""
    def __init__(self):
        self.mgr = UnifiedKeyManager()

    def get_active_test_credentials(self) -> Dict[str, str]:
        creds: Dict[str, str] = {}
        
        # 1. Check direct env keys
        for k in ["OPENAI_API_KEY", "GEMINI_API_KEY", "TEST_AGENT_GEMINI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "TAVILY_API_KEY", "NEWS_API_KEY", "STRIPE_TEST_KEY"]:
            val = os.getenv(k, "").strip()
            if val and not val.startswith("your_") and not val.endswith("_here"):
                creds[k] = val

        # 2. Check UnifiedKeyManager keys
        for key in self.mgr.keys:
            if key.is_active and key.value:
                if key.api_name in ("gemini", "google") and "GEMINI_API_KEY" not in creds:
                    creds["GEMINI_API_KEY"] = key.value
                    creds["TEST_AGENT_GEMINI_API_KEY"] = key.value
                elif key.api_name == "openrouter":
                    if "OPENROUTER_API_KEY" not in creds:
                        creds["OPENROUTER_API_KEY"] = key.value
                    if "OPENAI_API_KEY" not in creds:
                        creds["OPENAI_API_KEY"] = key.value
                        creds["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
                elif key.api_name == "openai" and "OPENAI_API_KEY" not in creds:
                    creds["OPENAI_API_KEY"] = key.value

        # Fallback if OPENAI_API_KEY still not found but OpenRouter is available
        if "OPENAI_API_KEY" not in creds and "OPENROUTER_API_KEY" in creds:
            creds["OPENAI_API_KEY"] = creds["OPENROUTER_API_KEY"]
            creds["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"

        return creds

