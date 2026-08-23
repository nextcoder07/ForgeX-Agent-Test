"""Runtime Interceptor - Emits normalized 4-layer ExecutionAction records for process spawns, timeouts, and errors."""
import uuid
import datetime as dt
from typing import Any, Dict
from app.models.execution import ExecutionAction


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RuntimeInterceptor:
    @staticmethod
    def intercept_event(
        session_id: str,
        sequence: int,
        event_kind: str,  # "PROCESS_SPAWN", "TIMEOUT", "CRASH", "UNCATCH_EXCEPTION"
        details: Dict[str, Any],
        allowed: bool = True,
        policy_reason: str = None
    ) -> ExecutionAction:
        act_id = f"act-{uuid.uuid4().hex[:8]}"
        pol_decision = "ALLOW" if allowed else "BLOCK"
        res_status = "SUCCESS" if allowed and event_kind == "PROCESS_SPAWN" else ("TIMEOUT" if event_kind == "TIMEOUT" else "ERROR")

        return ExecutionAction(
            id=act_id,
            action_id=act_id,
            execution_session_id=session_id,
            sequence=sequence,
            action_type="PROCESS_SPAWN" if event_kind == "PROCESS_SPAWN" else "RUNTIME_EVENT",
            target=event_kind,
            action_attempt={"payload": details, "target": event_kind},
            policy_decision={"decision": pol_decision, "reason": policy_reason or f"Runtime event {event_kind} observed"},
            execution_result={"status": res_status, "executed": allowed},
            side_effect={"detected": False, "details": None},
            attempt_payload=details,
            policy_reason=policy_reason,
            executed=allowed,
            result_status=res_status,
            side_effect_detected=False,
            timestamp=_now()
        )
