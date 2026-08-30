"""
ForgeX Enterprise Smart Priority Rotation & AI Key Pool Manager.

Architecture:
1. Three strictly isolated pools:
   - Pool A: Platform AI (AI_API_KEY_1..N) -> Intake, Scenarios, Observer, Repair.
   - Pool B: Meta Evaluator (META_EVALUATOR_API_KEY_1..N) -> Independent judgment.
   - Pool C: Target Agent Credentials (TEST_AI_API_KEY_1..N) -> Sandboxed execution.
2. Dynamic Discovery: Non-contiguous indexing (1, 2, 4, 6...) dynamically discovered.
3. Strict Priority Scanning: Every new logical operation starts scanning from Priority 1.
4. Fine-Grained Error Classification & Smart Cooldown:
   - 401 (AUTH_FAILED) -> Disable key
   - 402 (QUOTA_EXHAUSTED) -> 1h cooldown
   - 429 (RATE_LIMITED) -> 30-120s cooldown
   - 400 (REQUEST_INVALID) -> Fatal: Do not rotate blindly!
   - 404 (MODEL_NOT_FOUND) -> Rotate candidate
   - 408/500 (TIMEOUT/SERVER_ERROR) -> Retry once -> rotate
   - 502/503/504 (SERVICE_UNAVAILABLE) -> 30s cooldown -> rotate
5. Fallback: Ollama Local Server as last-resort fallback for Platform AI.
6. Zero Secret Leakage: Logs and ProviderAttempt records use safe identifiers (e.g. AI_API_KEY_1), NEVER raw secrets.
"""

from __future__ import annotations

import os
import re
import time
import urllib.request
import logging
import datetime as dt
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class CandidateState(str, Enum):
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    DISABLED = "DISABLED"
    EXHAUSTED = "EXHAUSTED"
    INVALID = "INVALID"


class ErrorClassification(str, Enum):
    KEY_MISSING = "KEY_MISSING"
    AUTH_FAILED = "AUTH_FAILED"                 # 401: Invalid / auth failure
    PERMISSION_DENIED = "PERMISSION_DENIED"     # 403: Forbidden / model permission
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"         # 402: Credits / payment required
    RATE_LIMITED = "RATE_LIMITED"               # 429: Rate limit
    REQUEST_INVALID = "REQUEST_INVALID"         # 400: Bad Request (DO NOT ROTATE)
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"         # 404: Model or endpoint not found
    TIMEOUT = "TIMEOUT"                         # 408: Timeout (retry once -> rotate)
    CONFLICT = "CONFLICT"                       # 409: Conflict (state/request issue)
    SERVER_ERROR = "SERVER_ERROR"               # 500: Server error (retry once -> rotate)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE" # 502/503/504: Service unavailable
    NETWORK_ERROR = "NETWORK_ERROR"             # Network unreachable
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"   # Output JSON unparseable
    SUCCESS = "SUCCESS"


@dataclass
class ProviderAttempt:
    provider: str
    model: str
    key_id: str                      # e.g., "AI_API_KEY_1" (NEVER the raw secret!)
    priority: int
    status: str                      # "SUCCESS", "RETRY", "ROTATED", "FATAL_ERROR", "EXHAUSTED"
    started_at: str
    finished_at: str
    error_code: Optional[int] = None
    error_type: Optional[str] = None
    cooldown_until: Optional[float] = None
    attempt_number: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "key_id": self.key_id,
            "priority": self.priority,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "attempt_number": self.attempt_number
        }


def _is_valid_key_val(val: str) -> bool:
    if not val or not isinstance(val, str):
        return False
    clean = val.strip().lower()
    if clean.startswith("your_") or clean.endswith("_here") or "your_key" in clean or clean in ("placeholder", "none", "null", "undefined", ""):
        return False
    return True


@dataclass
class PlatformCandidate:
    key_id: str                      # Identifier like "AI_API_KEY_1"
    raw_value: str                   # Actual secret (kept in memory, NEVER exposed in logs/attempts)
    provider: str                    # "openrouter", "gemini", "openai", "groq", "ollama"
    model: str                       # e.g. "openai/gpt-4o-mini"
    priority: int                    # 1, 2, 4, 6...
    state: CandidateState = CandidateState.ACTIVE
    cooldown_until: float = 0.0
    failure_count: int = 0
    total_calls: int = 0
    last_used_at: float = 0.0

    @property
    def is_available(self) -> bool:
        if self.state in (CandidateState.DISABLED, CandidateState.INVALID):
            return False
        if self.state in (CandidateState.COOLDOWN, CandidateState.EXHAUSTED):
            if time.time() >= self.cooldown_until:
                # Cooldown expired -> restore to active!
                self.state = CandidateState.ACTIVE
                self.cooldown_until = 0.0
                self.failure_count = 0
                return True
            return False
        return self.state == CandidateState.ACTIVE

    def apply_failure(self, classification: ErrorClassification, http_code: Optional[int] = None) -> None:
        now = time.time()
        self.failure_count += 1

        if classification == ErrorClassification.AUTH_FAILED or http_code == 401:
            self.state = CandidateState.INVALID
            self.cooldown_until = now + 86400.0  # 24 hours disable
            logger.warning(f"Key '{self.key_id}' ({self.provider}) marked INVALID due to 401 Auth Failure. Skipping in future priority scans.")

        elif classification == ErrorClassification.QUOTA_EXHAUSTED or http_code == 402:
            self.state = CandidateState.EXHAUSTED
            self.cooldown_until = now + 3600.0   # 1 hour cooldown
            logger.warning(f"Key '{self.key_id}' ({self.provider}) placed on 1-HOUR COOLDOWN due to 402 Credits Exhaustion.")

        elif classification == ErrorClassification.RATE_LIMITED or http_code == 429:
            self.state = CandidateState.COOLDOWN
            self.cooldown_until = now + 60.0     # 60s cooldown
            logger.warning(f"Key '{self.key_id}' ({self.provider}) placed on 60s COOLDOWN due to 429 Rate Limit.")

        elif classification in (ErrorClassification.SERVICE_UNAVAILABLE, ErrorClassification.NETWORK_ERROR) or http_code in (502, 503, 504):
            self.state = CandidateState.COOLDOWN
            self.cooldown_until = now + 30.0     # 30s temporary failure cooldown
            logger.warning(f"Key '{self.key_id}' ({self.provider}) placed on 30s COOLDOWN due to temporary upstream/network outage.")

        elif classification == ErrorClassification.MODEL_NOT_FOUND or http_code == 404:
            self.state = CandidateState.COOLDOWN
            self.cooldown_until = now + 300.0    # 5 min cooldown for model not found
            logger.warning(f"Key '{self.key_id}' ({self.provider}) placed on 5m COOLDOWN due to 404 Model Not Found.")

        else:
            self.state = CandidateState.COOLDOWN
            self.cooldown_until = now + 30.0

    def report_success(self) -> None:
        self.state = CandidateState.ACTIVE
        self.cooldown_until = 0.0
        self.failure_count = 0
        self.total_calls += 1
        self.last_used_at = time.time()


# Backwards compatibility AIKey dataclass alias
AIKey = PlatformCandidate


def classify_error_detail(err: Any) -> Tuple[ErrorClassification, Optional[int]]:
    """Classifies an exception or HTTP response into ErrorClassification and HTTP status code."""
    if err is None:
        return ErrorClassification.SUCCESS, 200

    err_str = str(err).lower()
    http_code: Optional[int] = None

    # Check for HTTP status code attributes
    if hasattr(err, "status_code"):
        try: http_code = int(err.status_code)
        except Exception: pass
    elif hasattr(err, "response") and hasattr(err.response, "status_code"):
        try: http_code = int(err.response.status_code)
        except Exception: pass

    # Extract code from message string if available
    if http_code is None:
        match = re.search(r"\b(400|401|402|403|404|408|409|429|500|502|503|504)\b", err_str)
        if match:
            http_code = int(match.group(1))

    # Detailed classification matrix
    if http_code == 400 or "bad request" in err_str or "invalid_request" in err_str or "invalid json schema" in err_str:
        return ErrorClassification.REQUEST_INVALID, http_code or 400

    if http_code == 401 or "unauthenticated" in err_str or "unauthorized" in err_str or "invalid api key" in err_str or "invalid_api_key" in err_str:
        return ErrorClassification.AUTH_FAILED, http_code or 401

    if http_code == 402 or "credits" in err_str or "payment required" in err_str or "quota exhausted" in err_str or "credit limit" in err_str:
        return ErrorClassification.QUOTA_EXHAUSTED, http_code or 402

    if http_code == 403 or "forbidden" in err_str or "permission denied" in err_str:
        return ErrorClassification.PERMISSION_DENIED, http_code or 403

    if http_code == 404 or "model not found" in err_str or "not found" in err_str or "unknown model" in err_str:
        return ErrorClassification.MODEL_NOT_FOUND, http_code or 404

    if http_code == 408 or "timeout" in err_str or "timed out" in err_str:
        return ErrorClassification.TIMEOUT, http_code or 408

    if http_code == 409 or "conflict" in err_str:
        return ErrorClassification.CONFLICT, http_code or 409

    if http_code == 429 or "rate limit" in err_str or "resource_exhausted" in err_str or "too many requests" in err_str:
        return ErrorClassification.RATE_LIMITED, http_code or 429

    if http_code == 500 or "internal server error" in err_str:
        return ErrorClassification.SERVER_ERROR, http_code or 500

    if http_code in (502, 503, 504) or "bad gateway" in err_str or "service unavailable" in err_str or "gateway timeout" in err_str:
        return ErrorClassification.SERVICE_UNAVAILABLE, http_code or 503

    if "network" in err_str or "connection refused" in err_str or "unreachable" in err_str:
        return ErrorClassification.NETWORK_ERROR, None

    if "json" in err_str or "expecting value" in err_str or "parse error" in err_str:
        return ErrorClassification.MALFORMED_RESPONSE, None

    return ErrorClassification.NETWORK_ERROR if "connect" in err_str else ErrorClassification.SERVER_ERROR, http_code


def classify_error(err: Any) -> Tuple[str, str]:
    """Compatibility wrapper returning (error_type, error_category)."""
    classification, _ = classify_error_detail(err)
    if classification == ErrorClassification.AUTH_FAILED:
        return "AUTHENTICATION_ERROR", "AUTHENTICATION_ERROR"
    elif classification == ErrorClassification.QUOTA_EXHAUSTED:
        return "QUOTA_EXHAUSTED", "RATE_LIMITED"
    elif classification == ErrorClassification.RATE_LIMITED:
        return "RATE_LIMITED", "RATE_LIMITED"
    elif classification == ErrorClassification.REQUEST_INVALID:
        return "INVALID_REQUEST", "FATAL"
    elif classification == ErrorClassification.MODEL_NOT_FOUND:
        return "MODEL_NOT_FOUND", "MODEL_NOT_FOUND"
    elif classification in (ErrorClassification.SERVER_ERROR, ErrorClassification.SERVICE_UNAVAILABLE, ErrorClassification.TIMEOUT):
        return "SERVER_ERROR", "SERVER_ERROR"
    elif classification == ErrorClassification.MALFORMED_RESPONSE:
        return "PARSING_ERROR", "PARSING_ERROR"
    return "UNKNOWN", "UNKNOWN"


def is_rotation_eligible(err: Any) -> bool:
    """Returns True if the error warrants rotating to the next candidate (not a fatal 400 request error)."""
    classification, _ = classify_error_detail(err)
    return classification not in (ErrorClassification.REQUEST_INVALID, ErrorClassification.CONFLICT)


def is_ollama_reachable(url: str = "http://localhost:11434") -> bool:
    """Synchronous fast check to verify whether local Ollama server is listening."""
    clean_url = url.rstrip("/")
    if not clean_url.startswith("http"):
        clean_url = f"http://{clean_url}"
    try:
        req = urllib.request.Request(f"{clean_url}/api/tags", headers={"User-Agent": "ForgeX-Health"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


# ============================================================================
# POOL A — PLATFORM AI POOL (Intake, Scenarios, Observer, Repair)
# ============================================================================

class PlatformAIPool:
    """Manages AI_API_KEY_1..N priority pool with non-contiguous indexing and smart rotation."""
    def __init__(self):
        self.candidates: List[PlatformCandidate] = []
        self.ollama_candidate: Optional[PlatformCandidate] = None
        self.load_pool()

    def load_pool(self) -> None:
        load_dotenv(override=True)
        self.candidates.clear()

        # Dynamically discover all AI_API_KEY_N (scanning 1 to 100 for non-contiguous gaps)
        for index in range(1, 100):
            val = os.getenv(f"AI_API_KEY_{index}", "").strip()
            if not _is_valid_key_val(val):
                continue
            api_name = os.getenv(f"AI_API_NAME_{index}", "openrouter").strip().lower()
            model_name = os.getenv(f"AI_MODEL_{index}", "").strip()
            if not model_name:
                model_name = "gemini-3.6-flash" if api_name in ("gemini", "google") else "openai/gpt-4o-mini"

            # Key ID is safe identifier: e.g. "AI_API_KEY_1"
            display_id = f"AI_API_KEY_{index}"
            self.candidates.append(PlatformCandidate(
                key_id=display_id,
                raw_value=val,
                provider=api_name,
                model=model_name,
                priority=index
            ))
            logger.debug(f"[Pool A] Discovered {display_id} (Priority {index}, {api_name} - {model_name})")

        # Register direct provider alias keys (OPENROUTER_API_KEY, GEMINI_API_KEY, GROQ_API_KEY) if not already added
        openrouter_direct = os.getenv("OPENROUTER_API_KEY", "").strip()
        openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
        if _is_valid_key_val(openrouter_direct) and not any(c.raw_value == openrouter_direct for c in self.candidates):
            self.candidates.append(PlatformCandidate(
                key_id="OPENROUTER_DIRECT_KEY",
                raw_value=openrouter_direct,
                provider="openrouter",
                model=openrouter_model,
                priority=100
            ))

        gemini_direct = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
        if _is_valid_key_val(gemini_direct) and not any(c.raw_value == gemini_direct for c in self.candidates):
            self.candidates.append(PlatformCandidate(
                key_id="GEMINI_DIRECT_KEY",
                raw_value=gemini_direct,
                provider="gemini",
                model=gemini_model,
                priority=101
            ))

        # Sort strictly by priority index (1 -> 2 -> 4 -> 5 -> 6... -> 100)
        self.candidates.sort(key=lambda c: c.priority)

        # Register dedicated Ollama fallback
        ollama_endpoint = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")).strip()
        from app.core.llm.providers import discover_active_ollama_model
        disc_model = discover_active_ollama_model(ollama_endpoint)
        ollama_model = os.getenv("OLLAMA_MODEL", disc_model or "qwen2.5-coder:3b").strip()

        self.ollama_candidate = PlatformCandidate(
            key_id="Ollama_Local_Fallback",
            raw_value=ollama_endpoint,
            provider="ollama",
            model=ollama_model,
            priority=9999
        )

    def get_ordered_candidates(self) -> List[PlatformCandidate]:
        """Always returns candidates in strict priority order starting from Priority 1."""
        now = time.time()
        # Reset any expired cooldowns
        for c in self.candidates:
            if c.cooldown_until > 0 and now >= c.cooldown_until:
                c.state = CandidateState.ACTIVE
                c.cooldown_until = 0.0
                c.failure_count = 0
        return list(self.candidates)


# ============================================================================
# POOL B — META EVALUATOR POOL (Meta Evaluator Judging)
# ============================================================================

class MetaEvaluatorPool:
    """Manages META_EVALUATOR_API_KEY_1..N priority pool independently."""
    def __init__(self):
        self.candidates: List[PlatformCandidate] = []
        self.ollama_candidate: Optional[PlatformCandidate] = None
        self.load_pool()

    def load_pool(self) -> None:
        load_dotenv(override=True)
        self.candidates.clear()

        for index in range(1, 30):
            val = os.getenv(f"META_EVALUATOR_API_KEY_{index}", "").strip()
            if not _is_valid_key_val(val):
                continue
            provider = os.getenv(f"META_EVALUATOR_PROVIDER_{index}", "gemini").strip().lower()
            model = os.getenv(f"META_EVALUATOR_MODEL_{index}", "gemini-3.6-flash").strip()
            display_id = f"META_EVALUATOR_API_KEY_{index}"
            self.candidates.append(PlatformCandidate(
                key_id=display_id,
                raw_value=val,
                provider=provider,
                model=model,
                priority=index
            ))

        meta_single = os.getenv("META_EVALUATOR_API_KEY", "").strip()
        if _is_valid_key_val(meta_single) and not any(c.raw_value == meta_single for c in self.candidates):
            provider = os.getenv("META_EVALUATOR_PROVIDER", "gemini").strip().lower()
            model = os.getenv("META_EVALUATOR_MODEL", "gemini-3.6-flash").strip()
            self.candidates.append(PlatformCandidate(
                key_id="META_EVALUATOR_PRIMARY_KEY",
                raw_value=meta_single,
                provider=provider,
                model=model,
                priority=100
            ))

        self.candidates.sort(key=lambda c: c.priority)

        ollama_endpoint = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        meta_ollama_model = os.getenv("META_EVALUATOR_OLLAMA_MODEL", "qwen2.5-coder:3b").strip()
        self.ollama_candidate = PlatformCandidate(
            key_id="Meta_Evaluator_Ollama_Fallback",
            raw_value=ollama_endpoint,
            provider="ollama",
            model=meta_ollama_model,
            priority=9999
        )

    def get_ordered_candidates(self) -> List[PlatformCandidate]:
        now = time.time()
        for c in self.candidates:
            if c.cooldown_until > 0 and now >= c.cooldown_until:
                c.state = CandidateState.ACTIVE
                c.cooldown_until = 0.0
                c.failure_count = 0
        return list(self.candidates)


# ============================================================================
# UNIFIED KEY MANAGER (Global Singleton Facade)
# ============================================================================

class UnifiedKeyManager:
    _instance: Optional[UnifiedKeyManager] = None

    def __new__(cls) -> UnifiedKeyManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.platform_pool = PlatformAIPool()
            cls._instance.meta_pool = MetaEvaluatorPool()
        return cls._instance

    @property
    def keys(self) -> List[PlatformCandidate]:
        # Return platform candidates + ollama fallback
        res = list(self.platform_pool.candidates)
        if self.platform_pool.ollama_candidate:
            res.append(self.platform_pool.ollama_candidate)
        return res

    @property
    def meta_keys(self) -> List[PlatformCandidate]:
        res = list(self.meta_pool.candidates)
        if self.meta_pool.ollama_candidate:
            res.append(self.meta_pool.ollama_candidate)
        return res

    def load_keys(self) -> None:
        self.platform_pool.load_pool()
        self.meta_pool.load_pool()

    def select_key(self, api_name: Optional[str] = None) -> Optional[PlatformCandidate]:
        """Selects the first available candidate starting strictly from Priority 1."""
        now = time.time()
        for c in self.platform_pool.get_ordered_candidates():
            if (api_name is None or c.provider.lower() == api_name.lower()) and c.is_available:
                c.last_used_at = now
                c.total_calls += 1
                return c

        # If all cloud candidates exhausted, check if Ollama is available
        if (api_name is None or api_name.lower() == "ollama") and self.platform_pool.ollama_candidate:
            if is_ollama_reachable(self.platform_pool.ollama_candidate.raw_value):
                return self.platform_pool.ollama_candidate

        return None

    def select_meta_key(self, api_name: Optional[str] = None) -> Optional[PlatformCandidate]:
        """Selects the first available meta evaluator candidate starting strictly from Priority 1."""
        now = time.time()
        for c in self.meta_pool.get_ordered_candidates():
            if (api_name is None or c.provider.lower() == api_name.lower()) and c.is_available:
                c.last_used_at = now
                c.total_calls += 1
                return c

        if (api_name is None or api_name.lower() == "ollama") and self.meta_pool.ollama_candidate:
            if is_ollama_reachable(self.meta_pool.ollama_candidate.raw_value):
                return self.meta_pool.ollama_candidate

        return None

    def mark_key_success(self, key_id: str, tokens: int = 0) -> None:
        for c in self.keys:
            if c.key_id == key_id:
                c.report_success()
                break

    def mark_key_failed(self, key_id: str, error_type: str = "ERROR", error_msg: str = "") -> None:
        classification, http_code = classify_error_detail(f"{error_type}: {error_msg}")
        for c in self.keys:
            if c.key_id == key_id:
                c.apply_failure(classification, http_code)
                break

    def reset_rotation(self) -> None:
        """Every new logical operation starts fresh from Priority 1 or local Ollama."""
        self.load_keys()
        cloud_count = len(self.platform_pool.candidates)
        if cloud_count > 0:
            logger.info(f"AI Key Manager: Started fresh from Priority 1 ({self.platform_pool.candidates[0].key_id}) across {cloud_count} cloud candidate(s)")
        else:
            logger.info("AI Key Manager: No cloud API keys configured. Directly using local Ollama instance.")


class SessionManager:
    def __init__(self):
        self.manager = UnifiedKeyManager()

    def get_key(self, api_name: Optional[str] = None) -> Optional[PlatformCandidate]:
        return self.manager.select_key(api_name)


# ============================================================================
# POOL C — TEST AGENT CREDENTIALS POOL (Sandboxed Execution Environment)
# ============================================================================

class TestAgentKeyManager:
    """Manages active AI & tool credentials for sandboxed test agents strictly according to execution mode."""
    def __init__(self):
        self.mgr = UnifiedKeyManager()

    def get_active_test_credentials(self) -> Dict[str, str]:
        creds: Dict[str, str] = {}

        # 1. Discover TEST_AI_API_KEY_1..N
        for idx in range(1, 30):
            val = os.getenv(f"TEST_AI_API_KEY_{idx}", "").strip()
            if not _is_valid_key_val(val):
                continue
            p_name = os.getenv(f"TEST_AI_API_NAME_{idx}", "gemini").strip().lower()
            if p_name in ("gemini", "google") and "GEMINI_API_KEY" not in creds:
                creds["GEMINI_API_KEY"] = val
                creds["TEST_AGENT_GEMINI_API_KEY"] = val
            elif p_name == "openrouter" and "OPENROUTER_API_KEY" not in creds:
                creds["OPENROUTER_API_KEY"] = val
            elif p_name == "groq" and "GROQ_API_KEY" not in creds:
                creds["GROQ_API_KEY"] = val
            elif p_name == "openai" and "OPENAI_API_KEY" not in creds:
                creds["OPENAI_API_KEY"] = val

        # 2. Tool APIs with rotation pools
        for tool_name in ["TAVILY_API_KEY", "NEWS_API_KEY", "SERPER_API_KEY", "WEATHER_API_KEY", "STRIPE_TEST_KEY"]:
            direct_val = os.getenv(tool_name, "").strip()
            if _is_valid_key_val(direct_val):
                creds[tool_name] = direct_val
            else:
                for idx in range(1, 20):
                    val = os.getenv(f"{tool_name}_{idx}", "").strip()
                    if _is_valid_key_val(val):
                        creds[tool_name] = val
                        break

        # 3. Direct cloud aliases (if not already set)
        for k in ["OPENAI_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"]:
            if k not in creds:
                val = os.getenv(k, "").strip()
                if _is_valid_key_val(val):
                    creds[k] = val

        # 4. OpenAI Compatibility Base URLs (LangChain / CrewAI agents)
        if "OPENAI_API_KEY" in creds:
            if "OPENROUTER_API_KEY" in creds and creds["OPENAI_API_KEY"] == creds["OPENROUTER_API_KEY"]:
                creds["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
            elif "GROQ_API_KEY" in creds and creds["OPENAI_API_KEY"] == creds["GROQ_API_KEY"]:
                creds["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
        else:
            # Check if local Ollama server is reachable for local fallback
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            if is_ollama_reachable(ollama_url):
                creds["OPENAI_API_KEY"] = "ollama"
                creds["OPENAI_BASE_URL"] = f"{ollama_url}/v1"

        return creds
