"""Event Interface Adapter."""
from typing import Any, Dict, List
from app.models.execution import ExecutionStep, ExecutionEventType


class EventAdapter:
    @staticmethod
    def format_input(scenario: Any) -> Dict[str, Any]:
        inv = getattr(scenario, "invocation", {}) or {}
        event_name = inv.get("event_name", "ORDER_CREATED")
        payload = scenario.initial_state if hasattr(scenario, "initial_state") else {}
        return {"event_name": event_name, "payload": payload}

    @staticmethod
    def build_events(session_id: str, formatted_input: Dict[str, Any]) -> List[ExecutionStep]:
        return [
            ExecutionStep(
                id="step-evt-inj",
                execution_session_id=session_id,
                step_number=1,
                event_type=ExecutionEventType.AGENT_ACTION.value,
                actor="environment",
                payload=formatted_input,
                created_at=""
            )
        ]
