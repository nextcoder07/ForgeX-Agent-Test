"""Batch Interface Adapter."""
from typing import Any, Dict, List
from app.models.execution import ExecutionStep, ExecutionEventType


class BatchAdapter:
    @staticmethod
    def format_input(scenario: Any) -> Dict[str, Any]:
        inv = getattr(scenario, "invocation", {}) or {}
        batch_items = inv.get("batch_items", [scenario.initial_state if hasattr(scenario, "initial_state") else {}])
        return {"batch_items": batch_items}

    @staticmethod
    def build_events(session_id: str, formatted_input: Dict[str, Any]) -> List[ExecutionStep]:
        return [
            ExecutionStep(
                id="step-batch-start",
                execution_session_id=session_id,
                step_number=1,
                event_type=ExecutionEventType.AGENT_ACTION.value,
                actor="system",
                payload=formatted_input,
                created_at=""
            )
        ]
