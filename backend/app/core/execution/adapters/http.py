"""HTTP Interface Adapter."""
from typing import Any, Dict, List
from app.models.execution import ExecutionStep, ExecutionEventType


class HTTPAdapter:
    @staticmethod
    def format_input(scenario: Any) -> Dict[str, Any]:
        inv = getattr(scenario, "invocation", {}) or {}
        endpoint = inv.get("endpoint", "/api/v1/agent")
        method = inv.get("method", "POST")
        headers = inv.get("headers", {"Content-Type": "application/json"})
        body = scenario.initial_state if hasattr(scenario, "initial_state") else {}
        return {
            "endpoint": endpoint,
            "method": method,
            "headers": headers,
            "body": body,
        }

    @staticmethod
    def build_events(session_id: str, formatted_input: Dict[str, Any]) -> List[ExecutionStep]:
        return [
            ExecutionStep(
                id="step-http-req",
                execution_session_id=session_id,
                step_number=1,
                event_type=ExecutionEventType.NETWORK_REQUEST.value,
                actor="user",
                payload=formatted_input,
                created_at=""
            )
        ]
