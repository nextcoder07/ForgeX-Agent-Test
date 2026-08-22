import os
import time
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class GeminiKey:
    def __init__(self, key_id: str, value: str):
        self.key_id = key_id       # e.g., "Gemini Key 1"
        self.value = value         # The actual API key value (secret)
        self.status = "AVAILABLE"  # "AVAILABLE", "STOPPED", "COOLDOWN"
        self.failure_count = 0
        self.last_error = ""
        self.last_used_at = 0.0
        self.cooldown_until = 0.0

    def to_safe_dict(self) -> Dict[str, Any]:
        """Expose key status safely without exposing raw key secrets."""
        return {
            "key_id": self.key_id,
            "status": self.status,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "last_used_at": self.last_used_at,
            "cooldown_until": self.cooldown_until
        }

class GeminiKeyManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GeminiKeyManager, cls).__new__(cls, *args, **kwargs)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, cooldown_seconds: int = 120):
        if self._initialized:
            return
        self.keys: List[GeminiKey] = []
        self.cooldown_seconds = cooldown_seconds
        self.load_keys()
        self._initialized = True

    def load_keys(self):
        """Loads Gemini API keys dynamically from standard environment variables."""
        self.keys.clear()
        
        # 1. Main key: GEMINI_API_KEY
        main_key = os.getenv("GEMINI_API_KEY", "")
        if main_key:
            self.keys.append(GeminiKey(key_id="Gemini Key 1", value=main_key))
            logger.info("Registered GEMINI_API_KEY as 'Gemini Key 1'")

        # 2. Sequential keys: GEMINI_API_KEY_1, GEMINI_API_KEY_2, etc.
        # We check up to index + 5 gaps dynamically.
        idx = 1
        consecutive_misses = 0
        while consecutive_misses < 5:
            env_var_name = f"GEMINI_API_KEY_{idx}"
            key_val = os.getenv(env_var_name, "")
            if key_val:
                consecutive_misses = 0
                # Prevent duplicate entry if key_1 matches the main key
                if not any(k.value == key_val for k in self.keys):
                    display_id = f"Gemini Key {len(self.keys) + 1}"
                    self.keys.append(GeminiKey(key_id=display_id, value=key_val))
                    logger.info(f"Registered {env_var_name} as '{display_id}'")
            else:
                consecutive_misses += 1
            idx += 1

        if not self.keys:
            logger.warning("No Gemini API keys configured in environment!")

    def get_all_keys_status(self) -> List[Dict[str, Any]]:
        """Returns safe status of all loaded keys (cooldown states updated)."""
        with self._lock:
            self._check_cooldowns_unlocked()
            return [k.to_safe_dict() for k in self.keys]

    def _check_cooldowns_unlocked(self):
        now = time.time()
        for k in self.keys:
            if k.status == "COOLDOWN" and now >= k.cooldown_until:
                k.status = "AVAILABLE"
                logger.info(f"{k.key_id} cooldown expired. Reset to AVAILABLE.")

    def select_key(self) -> Optional[GeminiKey]:
        """Selects the next eligible key using least-used allocation strategy."""
        with self._lock:
            self._check_cooldowns_unlocked()
            
            # Find eligible keys that are strictly AVAILABLE
            eligible = [k for k in self.keys if k.status == "AVAILABLE"]
            if not eligible:
                return None
            
            # Pick least-recently used key
            selected = min(eligible, key=lambda x: x.last_used_at)
            selected.last_used_at = time.time()
            return selected

    def peek_next_key_id(self) -> Optional[str]:
        """Returns the next eligible key without consuming a rotation slot."""
        with self._lock:
            self._check_cooldowns_unlocked()
            eligible = [k for k in self.keys if k.status == "AVAILABLE"]
            if not eligible:
                eligible = [k for k in self.keys if k.status == "COOLDOWN"]
            if not eligible:
                return None
            return min(eligible, key=lambda x: x.last_used_at).key_id

    def mark_key_failed(self, key_id: str, error_type: str, error_msg: str):
        """Transition key to COOLDOWN or STOPPED based on error severity."""
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
                        k.cooldown_until = time.time() + 600  # 10 minutes for rate limits / quota exhausted
                        logger.warning(f"{k.key_id} placed on long cooldown (600s) due to quota limit.")
                    else:
                        k.status = "COOLDOWN"
                        k.cooldown_until = time.time() + 30   # Short 30s cooldown for server/network temporary issues
                        logger.warning(f"{k.key_id} placed on short cooldown (30s) due to temporary issue: {error_type}")
                    break

    def mark_key_success(self, key_id: str):
        """Resets key failure counter on success."""
        with self._lock:
            for k in self.keys:
                if k.key_id == key_id:
                    k.failure_count = 0
                    if k.status not in ("STOPPED", "COOLDOWN"):
                        k.status = "AVAILABLE"
                    break

class GeminiConversationSession:
    def __init__(self, conversation_id: str, system_prompt: str = ""):
        self.conversation_id = conversation_id
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, str]] = []
        self.summary: str = ""
        self.last_active_key_id: Optional[str] = None
        self.created_at = time.time()

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        # If conversation history gets large (> 16 messages), compress older turns
        if len(self.messages) > 16:
            self._compact_history()

    def _compact_history(self):
        """Compact history turns to prevent token bloat while keeping state context."""
        logger.info(f"Compacting history for conversation {self.conversation_id}")
        if not self.summary:
            # Aggregate middle messages to create a rolling summary
            middle = self.messages[2:-4]
            summary_items = [f"{t['role'].upper()}: {t['content'][:100]}" for t in middle]
            self.summary = "Rolling summary of previous steps: " + " | ".join(summary_items)
            
        compacted = []
        compacted.extend(self.messages[:2])  # Keep first 2 messages (often task init)
        compacted.append({"role": "user", "content": f"[CONTINUITY CONTEXT SUMMARY: {self.summary}]"})
        compacted.extend(self.messages[-4:]) # Keep last 4 turns for immediate context
        self.messages = compacted

class GeminiSessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GeminiSessionManager, cls).__new__(cls, *args, **kwargs)
                cls._instance.sessions = {}
            return cls._instance

    def get_or_create_session(self, conversation_id: str, system_prompt: str = "") -> GeminiConversationSession:
        with self._lock:
            if conversation_id not in self.sessions:
                self.sessions[conversation_id] = GeminiConversationSession(conversation_id, system_prompt)
            return self.sessions[conversation_id]

def classify_error(e: Exception) -> str:
    err_str = str(e).lower()
    status_code = getattr(e, "code", getattr(e, "status_code", None))
    
    if status_code == 429 or "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
        return "QUOTA_EXHAUSTED"
    elif status_code == 401 or "401" in err_str or "unauthenticated" in err_str or "invalid authentication" in err_str or "api key not valid" in err_str:
        return "INVALID_KEY"
    elif status_code == 403 or "403" in err_str or "permission denied" in err_str:
        return "AUTHENTICATION_ERROR"
    elif status_code == 400 or "400" in err_str or "invalid argument" in err_str:
        if "safety" in err_str or "blocked" in err_str:
            return "SAFETY_POLICY_ERROR"
        return "INVALID_REQUEST"
    elif status_code == 404 or "404" in err_str or "not found" in err_str:
        return "MODEL_NOT_FOUND"
    elif status_code in (500, 502, 503, 504) or "500" in err_str or "503" in err_str or "unavailable" in err_str or "internal error" in err_str:
        return "TEMPORARY_SERVER_ERROR"
    elif "timeout" in err_str or "connection" in err_str or "network" in err_str:
        return "NETWORK_ERROR"
    return "UNKNOWN_ERROR"

def is_rotation_eligible(error_type: str) -> bool:
    return error_type in (
        "QUOTA_EXHAUSTED",
        "INVALID_KEY",
        "AUTHENTICATION_ERROR",
        "TEMPORARY_SERVER_ERROR",
        "NETWORK_ERROR"
    )


class TestAgentKeyManager:
    """Manages dedicated Gemini API keys strictly reserved for test agents in compatible mode."""
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
        self.keys: List[GeminiKey] = []
        self.cooldown_seconds = cooldown_seconds
        self.load_keys()
        self._initialized = True

    def load_keys(self):
        """Loads Test Agent Gemini API keys dynamically from environment variables."""
        self.keys.clear()
        
        main_key = os.getenv("TEST_AGENT_GEMINI_API_KEY", "")
        if main_key:
            self.keys.append(GeminiKey(key_id="Test Agent Key 1", value=main_key))
            logger.info("Registered TEST_AGENT_GEMINI_API_KEY as 'Test Agent Key 1'")

        idx = 1
        consecutive_misses = 0
        while consecutive_misses < 5:
            env_var_name = f"TEST_AGENT_GEMINI_API_KEY_{idx}"
            key_val = os.getenv(env_var_name, "")
            if key_val:
                consecutive_misses = 0
                if not any(k.value == key_val for k in self.keys):
                    display_id = f"Test Agent Key {len(self.keys) + 1}"
                    self.keys.append(GeminiKey(key_id=display_id, value=key_val))
                    logger.info(f"Registered {env_var_name} as '{display_id}'")
            else:
                consecutive_misses += 1
            idx += 1

    def select_key(self) -> Optional[GeminiKey]:
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
