"""Function Interface Adapter."""
from typing import Any, Dict, List
from app.models.execution import ExecutionStep, ExecutionEventType


class FunctionAdapter:
    @staticmethod
    def format_input(scenario: Any) -> Dict[str, Any]:
        inv = getattr(scenario, "invocation", {}) or {}
        function_name = inv.get("function_name", "run")
        kwargs = scenario.initial_state if hasattr(scenario, "initial_state") else {}
        return {
            "function_name": function_name,
            "kwargs": kwargs
        }

    @staticmethod
    def build_events(session_id: str, formatted_input: Dict[str, Any]) -> List[ExecutionStep]:
        return [
            ExecutionStep(
                id="step-func-inv",
                execution_session_id=session_id,
                step_number=1,
                event_type=ExecutionEventType.TOOL_INVOCATION.value,
                actor="user",
                payload=formatted_input,
                created_at=""
            )
        ]
