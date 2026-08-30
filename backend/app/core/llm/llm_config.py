"""
LLM Configuration Module.
Central configuration for LLM providers (Gemini, OpenRouter, Ollama) and fallback logic.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class LLMConfig:
    PROVIDER = os.getenv("PLATFORM_LLM_PROVIDER", "hybrid")
    # Central configuration for model name, default to gemini-3.6-flash or qwen2.5-coder:7b
    MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    GEMINI_MODEL = MODEL
    OLLAMA_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:7b")
    OLLAMA_ENDPOINT = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Low temperature optimal for code and JSON structured outputs
    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2"))
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "4096"))
    # Default to no timeout so the LLM can run freely unless a caller explicitly sets LLM_TIMEOUT_SECONDS.
    REQUEST_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "0") or 0)

    @staticmethod
    def request_timeout_for_httpx() -> Optional[float]:
        """Returns None when timeout is disabled; otherwise a positive float in seconds."""
        timeout = LLMConfig.REQUEST_TIMEOUT_SECONDS
        if timeout <= 0:
            return None
        return float(timeout)

