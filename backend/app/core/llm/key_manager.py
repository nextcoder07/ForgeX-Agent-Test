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
    """Manages all registered AI API keys with LRU round-robin rotation and cooldowns."""
    _instance: Optional[UnifiedKeyManager] = None

    def __new__(cls) -> UnifiedKeyManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.keys = []
            cls._instance.load_keys()
        return cls._instance

    def load_keys(self) -> None:
        """Loads all AI API keys dynamically from environment variables."""
        self.keys.clear()
        
        # 1. Load universal AI_API_KEY_n format
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
                    model_name=model_name
                ))
                logger.info(f"Registered {display_id} ({api_name} - {model_name})")

        # 2. Legacy fallback for GEMINI_API_KEY and GEMINI_API_KEY_n
        gemini_main = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()

        if gemini_main and not any(k.value == gemini_main for k in self.keys):
            self.keys.append(AIKey(
                key_id="Gemini Legacy Key Main",
                value=gemini_main,
                api_name="gemini",
                model_name=gemini_model
            ))
            logger.info(f"Registered GEMINI_API_KEY as 'Gemini Legacy Key Main' ({gemini_model})")

        for idx in range(1, 10):
            gemini_val = os.getenv(f"GEMINI_API_KEY_{idx}", "").strip()
            if gemini_val and not any(k.value == gemini_val for k in self.keys):
                self.keys.append(AIKey(
                    key_id=f"Gemini Legacy Key {idx}",
                    value=gemini_val,
                    api_name="gemini",
                    model_name=gemini_model
                ))

        # 3. Fallback for OPENROUTER_API_KEY
        openrouter_main = os.getenv("OPENROUTER_API_KEY", "").strip()
        openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
        if openrouter_main and not any(k.value == openrouter_main for k in self.keys):
            self.keys.append(AIKey(
                key_id="OpenRouter Main Key",
                value=openrouter_main,
                api_name="openrouter",
                model_name=openrouter_model
            ))

        # 4. Ollama Local Endpoint
        ollama_endpoint = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")).strip()
        ollama_model = os.getenv("OLLAMA_DEFAULT_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")).strip()
        self.keys.append(AIKey(
            key_id="Ollama Local Server",
            value=ollama_endpoint,
            api_name="ollama",
            model_name=ollama_model
        ))
        logger.info(f"Registered Ollama Local Server ({ollama_endpoint} - {ollama_model})")

    def select_key(self, api_name: Optional[str] = None) -> Optional[AIKey]:
        """Selects the best available key using LRU (Least-Recently-Used) round-robin."""
        now = time.time()
        eligible = [
            k for k in self.keys
            if k.is_available and (api_name is None or k.api_name.lower() == api_name.lower())
        ]
        if not eligible:
            # Check for keys whose cooldown has expired
            for k in self.keys:
                if k.cooldown_until > 0 and now >= k.cooldown_until:
                    k.cooldown_until = 0.0
                    k.failure_count = 0
                    if api_name is None or k.api_name.lower() == api_name.lower():
                        eligible.append(k)

        if not eligible:
            return None

        # Prioritize cloud keys over local ollama, and sort by least-recently-used
        eligible.sort(key=lambda k: (1 if k.api_name in ("ollama", "local") else 0, k.last_used_at))
        chosen = eligible[0]
        chosen.last_used_at = now
        chosen.total_calls += 1
        return chosen

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
                # Set cooldown to 180s on server timeout / rate-limit
                k.cooldown_until = now + 180.0
                logger.warning(f"Key '{key_id}' placed on cooldown (180s) due to failure: {error}")
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
    if "429" in err_str or "quota" in err_str or "rate" in err_str:
        return "RATE_LIMITED", "RATE_LIMITED"
    if "504" in err_str or "gateway" in err_str or "timeout" in err_str:
        return "SERVER_ERROR", "SERVER_ERROR"
    if "404" in err_str or "not found" in err_str:
        return "MODEL_NOT_FOUND", "MODEL_NOT_FOUND"
    if "401" in err_str or "unauthorized" in err_str or "invalid api key" in err_str:
        return "AUTHENTICATION_ERROR", "AUTHENTICATION_ERROR"
    return "UNKNOWN", "UNKNOWN"


def is_rotation_eligible(err: Any) -> bool:
    if isinstance(err, tuple):
        category = err[1]
    else:
        category = str(err)
    return category in ("RATE_LIMITED", "SERVER_ERROR", "AUTHENTICATION_ERROR", "UNKNOWN")
