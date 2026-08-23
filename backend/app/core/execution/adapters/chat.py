"""Chat Interface Adapter."""
from typing import Any, Dict, List
from app.models.execution import ExecutionStep, ExecutionEventType


class ChatAdapter:
    @staticmethod
    def format_input(scenario: Any) -> Dict[str, Any]:
        messages = scenario.user_messages if hasattr(scenario, "user_messages") and scenario.user_messages else ["Hello"]
        return {"messages": messages}

    @staticmethod
    def build_events(session_id: str, formatted_input: Dict[str, Any]) -> List[ExecutionStep]:
        events = []
        for idx, msg in enumerate(formatted_input.get("messages", [])):
            events.append(
                ExecutionStep(
                    id=f"step-chat-{idx+1}",
                    execution_session_id=session_id,
                    step_number=idx + 1,
                    event_type=ExecutionEventType.USER_INPUT.value,
                    actor="user",
                    payload={"message": msg},
                    created_at=""
                )
            )
        return events
