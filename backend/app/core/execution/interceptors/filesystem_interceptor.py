"""Filesystem Interceptor - Emits normalized 4-layer ExecutionAction records for file I/O."""
import uuid
import datetime as dt
from typing import Any, Dict
from app.models.execution import ExecutionAction


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class FilesystemInterceptor:
    @staticmethod
    def intercept_operation(
        session_id: str,
        sequence: int,
        operation: str,  # "READ", "WRITE", "DELETE"
        path: str,
        content_length: int = 0,
        allowed: bool = True,
        policy_reason: str = None,
        side_effect_occurred: bool = False
    ) -> ExecutionAction:
        act_id = f"act-{uuid.uuid4().hex[:8]}"
        pol_decision = "ALLOW" if allowed else "BLOCK"
        res_status = "SUCCESS" if allowed else "BLOCKED_POLICY"

        return ExecutionAction(
            id=act_id,
            action_id=act_id,
            execution_session_id=session_id,
            sequence=sequence,
            action_type="FILE_OPERATION",
            target=path,
            action_attempt={"payload": {"operation": operation, "path": path, "size": content_length}, "target": path},
            policy_decision={"decision": pol_decision, "reason": policy_reason or ("Filesystem operation permitted" if allowed else "Read-only workspace constraint")},
            execution_result={"status": res_status, "executed": allowed},
            side_effect={"detected": side_effect_occurred, "details": {"operation": operation, "path": path} if side_effect_occurred else None},
            attempt_payload={"operation": operation, "path": path},
            policy_reason=policy_reason,
            executed=allowed,
            result_status=res_status,
            side_effect_detected=side_effect_occurred,
            timestamp=_now()
        )
