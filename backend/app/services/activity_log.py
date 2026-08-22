import datetime as dt
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ActivityEvent(BaseModel):
    id: str
    timestamp: str
    category: str  # "LLM", "GATEWAY", "DEPENDENCY", "SANDBOX", "INTAKE", "EVALUATION"
    action: str    # e.g. "REQUEST", "RESPONSE", "TOOL_CALL", "RESOLVE"
    detail: str    # e.g. "gemini-3.6-flash | system prompt analysis"
    request_summary: Optional[str] = None
    response_summary: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str = "success"  # "success", "warning", "error", "security_alert"

class ActivityLog:
    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self.events: List[ActivityEvent] = []

    def emit(
        self,
        category: str,
        action: str,
        detail: str,
        request_summary: Optional[str] = None,
        response_summary: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: str = "success",
    ):
        event = ActivityEvent(
            id=str(uuid.uuid4()),
            timestamp=dt.datetime.utcnow().isoformat() + "Z",
            category=category,
            action=action,
            detail=detail,
            request_summary=request_summary,
            response_summary=response_summary,
            duration_ms=duration_ms,
            status=status,
        )
        self.events.append(event)
        if len(self.events) > self.max_size:
            self.events.pop(0)

        # Print to backend console with color formatting
        self._console_print(event)

    def get_events(self, limit: int = 50, since: Optional[str] = None) -> List[ActivityEvent]:
        filtered = self.events
        if since:
            filtered = [e for e in filtered if e.timestamp > since]
        return filtered[-limit:]

    def _console_print(self, event: ActivityEvent):
        # ANSI Escape codes for colored logs
        colors = {
            "LLM": "\033[94m",       # Blue
            "GATEWAY": "\033[93m",   # Yellow
            "DEPENDENCY": "\033[92m",# Green
            "SANDBOX": "\033[95m",   # Magenta
            "INTAKE": "\033[96m",    # Cyan
            "EVALUATION": "\033[91m",# Red
        }
        reset = "\033[0m"
        bold = "\033[1m"
        
        cat_color = colors.get(event.category, "\033[37m")  # Default white
        
        # Format string
        dur_str = f" | {event.duration_ms:.1f}ms" if event.duration_ms is not None else ""
        status_symbol = "[OK]"
        if event.status == "warning":
            status_symbol = "[WARN]"
        elif event.status == "error":
            status_symbol = "[ERR]"
        elif event.status == "security_alert":
            status_symbol = "[SEC]"

        try:
            print(
                f"{cat_color}{bold}[{event.category}:{event.action}]{reset} "
                f"{event.detail}{dur_str} ({status_symbol} {event.status}){reset}"
            )
            if event.request_summary:
                print(f"   {cat_color}-> Req Summary:{reset} {event.request_summary[:160]}")
            if event.response_summary:
                print(f"   {cat_color}<- Res Summary:{reset} {event.response_summary[:160]}")
        except Exception:
            # Fallback if terminal completely chokes on colors
            print(f"[{event.category}:{event.action}] {event.detail}{dur_str} ({status_symbol} {event.status})")

activity_log = ActivityLog()
