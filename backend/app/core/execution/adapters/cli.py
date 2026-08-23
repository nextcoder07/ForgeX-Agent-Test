"""CLI Interface Adapter."""
from typing import Any, Dict, List
from app.models.execution import ExecutionStep, ExecutionEventType


class CLIAdapter:
    @staticmethod
    def format_input(scenario: Any) -> Dict[str, Any]:
        inv = getattr(scenario, "invocation", {}) or {}
        cmd = inv.get("command", "python agent.py")
        args = inv.get("args", [])
        stdin = scenario.user_input if hasattr(scenario, "user_input") and scenario.user_input else ""
        return {
            "command": cmd,
            "args": args,
            "stdin": stdin,
            "formatted_cli": f"{cmd} {' '.join(args)}".strip()
        }

    @staticmethod
    def build_events(session_id: str, formatted_input: Dict[str, Any]) -> List[ExecutionStep]:
        events = [
            ExecutionStep(
                id=f"step-cli-cmd",
                execution_session_id=session_id,
                step_number=1,
                event_type=ExecutionEventType.CLI_ARGUMENTS.value,
                actor="system",
                payload={"command": formatted_input["command"], "args": formatted_input["args"]},
                created_at=""
            )
        ]
        if formatted_input.get("stdin"):
            events.append(
                ExecutionStep(
                    id=f"step-cli-stdin",
                    execution_session_id=session_id,
                    step_number=2,
                    event_type=ExecutionEventType.STDIN_INPUT.value,
                    actor="user",
                    payload={"stdin": formatted_input["stdin"]},
                    created_at=""
                )
            )
        return events
