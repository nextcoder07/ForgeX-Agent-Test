"""Tool Interceptor - Emits normalized 4-layer ExecutionAction records for tool calls."""
import uuid
import datetime as dt
from typing import Any, Dict
from app.models.execution import ExecutionAction


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class ToolInterceptor:
    @staticmethod
    def intercept_call(
        session_id: str,
        sequence: int,
        tool_name: str,
        arguments: Dict[str, Any],
        routing_decision: str,
        policy_reason: str = None,
        result: Any = None,
        result_status: str = "SUCCESS",
        side_effect_occurred: bool = False,
        side_effect_details: Dict[str, Any] = None
    ) -> ExecutionAction:
        act_id = f"act-{uuid.uuid4().hex[:8]}"
        is_blocked = (routing_decision == "BLOCK" or result_status == "BLOCKED_POLICY")
        pol_decision = "BLOCK" if is_blocked else ("REDIRECT" if routing_decision == "REDIRECT" else "ALLOW")

        return ExecutionAction(
            id=act_id,
            action_id=act_id,
            execution_session_id=session_id,
            sequence=sequence,
            action_type="TOOL_CALL",
            target=tool_name,
            action_attempt={"payload": arguments, "target": tool_name},
            policy_decision={"decision": pol_decision, "reason": policy_reason},
            execution_result={"status": result_status, "executed": not is_blocked, "result": result},
            side_effect={"detected": side_effect_occurred, "details": side_effect_details},
            attempt_payload=arguments,
            policy_reason=policy_reason,
            executed=not is_blocked,
            result_status=result_status,
            side_effect_detected=side_effect_occurred,
            side_effect_details=side_effect_details,
            timestamp=_now()
        )
