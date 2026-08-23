import os
import time
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class AIKey:
    def __init__(self, key_id: str, value: str, api_name: str, model_name: str):
        self.key_id = key_id
        self.value = value         # The actual API key value (secret)
        self.api_name = api_name.lower()
        self.model_name = model_name
        self.status = "AVAILABLE"  # "AVAILABLE", "STOPPED", "COOLDOWN"
        self.failure_count = 0
        self.last_error = ""
        self.last_used_at = 0.0
        self.cooldown_until = 0.0

    def to_safe_dict(self) -> Dict[str, Any]:
        """Expose key status safely without exposing raw key secrets."""
        return {
            "key_id": self.key_id,
            "api_name": self.api_name,
            "model_name": self.model_name,
            "status": self.status,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "last_used_at": self.last_used_at,
            "cooldown_until": self.cooldown_until
        }

class UnifiedKeyManager:
    """A single thread-safe manager for ALL AI keys across ALL providers."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(UnifiedKeyManager, cls).__new__(cls, *args, **kwargs)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, cooldown_seconds: int = 120):
        if self._initialized:
            return
        self.keys: List[AIKey] = []
        self.cooldown_seconds = cooldown_seconds
        self.load_keys()
        self._initialized = True

    def load_keys(self):
        """Loads all AI API keys dynamically from environment variables."""
        self.keys.clear()
        
        # 1. Load the new universal AI_API_KEY_n format
        for index in range(1, 100):
            value = os.getenv(f"AI_API_KEY_{index}", "").strip()
            if not value:
                continue
            api_name = os.getenv(f"AI_API_NAME_{index}", "").strip().lower()
            model_name = os.getenv(f"AI_MODEL_{index}", "").strip()
            
            if not api_name or not model_name:
                logger.warning(f"AI_API_KEY_{index} ignored: AI_API_NAME_{index} and AI_MODEL_{index} are required")
                continue
                
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
        if gemini_main and not any(k.value == gemini_main for k in self.keys):
            self.keys.append(AIKey(
                key_id="Gemini Legacy Key Main",
                value=gemini_main,
                api_name="gemini",
                model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            ))
            logger.info("Registered GEMINI_API_KEY as 'Gemini Legacy Key Main'")

        for idx in range(1, 10):
            gemini_val = os.getenv(f"GEMINI_API_KEY_{idx}", "").strip()
            if gemini_val and not any(k.value == gemini_val for k in self.keys):
                self.keys.append(AIKey(
                    key_id=f"Gemini Legacy Key {idx}",
                    value=gemini_val,
                    api_name="gemini",
                    model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                ))

        # 3. Legacy / explicit fallback for OPENROUTER_API_KEY or OTHERAI_API_KEY
        openrouter_main = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("OTHERAI_API_KEY", "").strip()
        openrouter_model = os.getenv("OPENROUTER_MODEL", "").strip() or os.getenv("OTHERAI_MODEL", "openai/gpt-4o-mini")
        if openrouter_main and not any(k.value == openrouter_main for k in self.keys):
            self.keys.append(AIKey(
                key_id="OpenRouter Main Key",
                value=openrouter_main,
                api_name="openrouter",
                model_name=openrouter_model
            ))
            logger.info(f"Registered OpenRouter Key ('{openrouter_model}')")

        for idx in range(1, 10):
            other_val = os.getenv(f"OPENROUTER_API_KEY_{idx}", "").strip() or os.getenv(f"OTHERAI_API_KEY_{idx}", "").strip()
            if other_val and not any(k.value == other_val for k in self.keys):
                self.keys.append(AIKey(
                    key_id=f"OpenRouter Secondary Key {idx}",
                    value=other_val,
                    api_name="openrouter",
                    model_name=openrouter_model
                ))

        # 4. Standalone / local Ollama registration (OLLAMA_BASE_URL & OLLAMA_MODEL)
        ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip() or "http://localhost:11434"
        ollama_model = os.getenv("OLLAMA_MODEL", "").strip() or "qwen2.5-coder:7b"
        if (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_MODEL")) and not any(k.api_name == "ollama" and k.value == ollama_url for k in self.keys):
            self.keys.append(AIKey(
                key_id="Ollama Local Server",
                value=ollama_url,
                api_name="ollama",
                model_name=ollama_model
            ))
            logger.info(f"Registered Ollama Local Server ({ollama_url} - {ollama_model})")

        if not self.keys:
            logger.warning("No API keys configured in environment!")

    def get_all_keys_status(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._check_cooldowns_unlocked()
            return [k.to_safe_dict() for k in self.keys]

    def _check_cooldowns_unlocked(self):
        now = time.time()
        for k in self.keys:
            if k.status == "COOLDOWN" and now >= k.cooldown_until:
                k.status = "AVAILABLE"
                logger.info(f"{k.key_id} cooldown expired. Reset to AVAILABLE.")

    def select_key(self, api_name: Optional[str] = None) -> Optional[AIKey]:
        """Selects the next eligible key. Optionally filter by api_name."""
        with self._lock:
            self._check_cooldowns_unlocked()
            
            eligible = [k for k in self.keys if k.status == "AVAILABLE"]
            if api_name:
                eligible = [k for k in eligible if k.api_name == api_name.lower()]
                
            if not eligible:
                return None
            
            # Always select the first eligible key to maintain strict priority order
            selected = eligible[0]
            selected.last_used_at = time.time()
            return selected

    def mark_key_failed(self, key_id: str, error_type: str, error_msg: str):
        with self._lock:
            for k in self.keys:
                if k.key_id == key_id:
                    k.failure_count += 1
                    k.last_error = error_msg
                    
                    if error_type in ("INVALID_KEY", "AUTHENTICATION_ERROR"):
                        k.status = "STOPPED"
                        logger.error(f"{k.key_id} permanently stopped due to authentication failure.")
                    elif error_type == "QUOTA_EXHAUSTED":
                        k.status = "COOLDOWN"
                        k.cooldown_until = time.time() + 600
                        logger.warning(f"{k.key_id} placed on long cooldown (600s) due to quota limit.")
                    else:
                        k.status = "COOLDOWN"
                        k.cooldown_until = time.time() + 30
                        logger.warning(f"{k.key_id} placed on short cooldown (30s) due to temporary issue: {error_type}")
                    break

    def mark_key_success(self, key_id: str):
        with self._lock:
            for k in self.keys:
                if k.key_id == key_id:
                    k.failure_count = 0
                    if k.status not in ("STOPPED", "COOLDOWN"):
                        k.status = "AVAILABLE"
                    break

class ConversationSession:
    def __init__(self, conversation_id: str, system_prompt: str = ""):
        self.conversation_id = conversation_id
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, str]] = []
        self.summary: str = ""
        self.last_active_key_id: Optional[str] = None
        self.created_at = time.time()

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > 16:
            self._compact_history()

    def _compact_history(self):
        logger.info(f"Compacting history for conversation {self.conversation_id}")
        if not self.summary:
            middle = self.messages[2:-4]
            summary_items = [f"{t['role'].upper()}: {t['content'][:100]}" for t in middle]
            self.summary = "Rolling summary of previous steps: " + " | ".join(summary_items)
            
        compacted = []
        compacted.extend(self.messages[:2])
        compacted.append({"role": "user", "content": f"[CONTINUITY CONTEXT SUMMARY: {self.summary}]"})
        compacted.extend(self.messages[-4:])
        self.messages = compacted

class SessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SessionManager, cls).__new__(cls, *args, **kwargs)
                cls._instance.sessions = {}
            return cls._instance

    def get_or_create_session(self, conversation_id: str, system_prompt: str = "") -> ConversationSession:
        with self._lock:
            if conversation_id not in self.sessions:
                self.sessions[conversation_id] = ConversationSession(conversation_id, system_prompt)
            return self.sessions[conversation_id]

class ErrorCategory:
    KEY_SPECIFIC = "KEY_SPECIFIC"       
    PROJECT_QUOTA = "PROJECT_QUOTA"     
    PERMANENT_ERROR = "PERMANENT_ERROR" 

def classify_error(e: Exception) -> tuple[str, str]:
    err_str = str(e).lower()
    status_code = getattr(e, "code", getattr(e, "status_code", None))

    if (
        "generaterequestsperday" in err_str
        or "perproject" in err_str
        or "daily" in err_str
        or "free_tier_requests" in err_str
        or "quota exceeded for metric" in err_str
    ):
        return "PROJECT_QUOTA_EXHAUSTED", ErrorCategory.PROJECT_QUOTA

    if status_code == 429 or "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
        return "QUOTA_EXHAUSTED", ErrorCategory.KEY_SPECIFIC

    elif status_code == 401 or "401" in err_str or "unauthenticated" in err_str or "invalid authentication" in err_str or "api key not valid" in err_str:
        return "INVALID_KEY", ErrorCategory.KEY_SPECIFIC

    elif status_code == 403 or "403" in err_str or "permission denied" in err_str:
        return "AUTHENTICATION_ERROR", ErrorCategory.KEY_SPECIFIC

    elif status_code == 400 or "400" in err_str or "invalid argument" in err_str:
        if "safety" in err_str or "blocked" in err_str:
            return "SAFETY_POLICY_ERROR", ErrorCategory.PERMANENT_ERROR
        return "INVALID_REQUEST", ErrorCategory.PERMANENT_ERROR

    elif status_code == 404 or "404" in err_str or "not found" in err_str:
        return "MODEL_NOT_FOUND", ErrorCategory.PERMANENT_ERROR

    elif status_code in (500, 502, 503, 504) or "500" in err_str or "503" in err_str or "unavailable" in err_str or "internal error" in err_str:
        return "TEMPORARY_SERVER_ERROR", ErrorCategory.KEY_SPECIFIC

    elif "timeout" in err_str or "connection" in err_str or "network" in err_str:
        return "NETWORK_ERROR", ErrorCategory.KEY_SPECIFIC

    return "UNKNOWN_ERROR", ErrorCategory.KEY_SPECIFIC

def is_rotation_eligible(error_category: str) -> bool:
    return error_category in (ErrorCategory.KEY_SPECIFIC, ErrorCategory.PROJECT_QUOTA)

class TestAgentKeyManager:
    """Manages dedicated API keys strictly reserved for test agents in compatible mode."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TestAgentKeyManager, cls).__new__(cls, *args, **kwargs)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, cooldown_seconds: int = 120):
        if self._initialized:
            return
        self.keys: List[AIKey] = []
        self.cooldown_seconds = cooldown_seconds
        self.load_keys()
        self._initialized = True

    def load_keys(self):
        self.keys.clear()
        main_key = os.getenv("TEST_AGENT_GEMINI_API_KEY", "")
        if main_key:
            self.keys.append(AIKey(key_id="Test Agent Key 1", value=main_key, api_name="gemini", model_name="gemini-2.5-flash"))
            
        for idx in range(1, 10):
            key_val = os.getenv(f"TEST_AGENT_GEMINI_API_KEY_{idx}", "")
            if key_val and not any(k.value == key_val for k in self.keys):
                self.keys.append(AIKey(key_id=f"Test Agent Key {idx+1}", value=key_val, api_name="gemini", model_name="gemini-2.5-flash"))

    def select_key(self) -> Optional[AIKey]:
        with self._lock:
            now = time.time()
            for k in self.keys:
                if k.status == "COOLDOWN" and now >= k.cooldown_until:
                    k.status = "AVAILABLE"

            eligible = [k for k in self.keys if k.status == "AVAILABLE"]
            if not eligible:
                return None

            selected = min(eligible, key=lambda x: x.last_used_at)
            selected.last_used_at = time.time()
            return selected

    def mark_key_failed(self, key_id: str, error_type: str, error_msg: str):
        with self._lock:
            for k in self.keys:
                if k.key_id == key_id:
                    k.failure_count += 1
                    k.last_error = error_msg
                    if error_type in ("INVALID_KEY", "AUTHENTICATION_ERROR"):
                        k.status = "STOPPED"
                    elif error_type == "QUOTA_EXHAUSTED":
                        k.status = "COOLDOWN"
                        k.cooldown_until = time.time() + 600
                    else:
                        k.status = "COOLDOWN"
                        k.cooldown_until = time.time() + 30
                    break

    def mark_key_success(self, key_id: str):
        with self._lock:
            for k in self.keys:
                if k.key_id == key_id:
                    k.failure_count = 0
                    if k.status not in ("STOPPED", "COOLDOWN"):
                        k.status = "AVAILABLE"
                    break
