"""Database Interceptor - Emits normalized 4-layer ExecutionAction records for DB queries/mutations."""
import uuid
import datetime as dt
from typing import Any, Dict
from app.models.execution import ExecutionAction


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class DatabaseInterceptor:
    @staticmethod
    def intercept_operation(
        session_id: str,
        sequence: int,
        resource_type: str,
        resource_id: str,
        operation: str,  # "QUERY", "INSERT", "UPDATE", "DELETE"
        before_val: Any = None,
        after_val: Any = None,
        allowed: bool = True,
        policy_reason: str = None
    ) -> ExecutionAction:
        act_id = f"act-{uuid.uuid4().hex[:8]}"
        pol_decision = "ALLOW" if allowed else "BLOCK"
        res_status = "SUCCESS" if allowed else "BLOCKED_POLICY"
        side_effect_occurred = allowed and (operation in ["INSERT", "UPDATE", "DELETE"]) and (before_val != after_val)

        return ExecutionAction(
            id=act_id,
            action_id=act_id,
            execution_session_id=session_id,
            sequence=sequence,
            action_type="DATABASE_OPERATION",
            target=f"{operation} {resource_type}:{resource_id}",
            action_attempt={"payload": {"resource_type": resource_type, "resource_id": resource_id, "operation": operation}, "target": resource_type},
            policy_decision={"decision": pol_decision, "reason": policy_reason or ("Database query allowed" if allowed else "Database modification blocked by safety policy")},
            execution_result={"status": res_status, "executed": allowed},
            side_effect={"detected": side_effect_occurred, "details": {"resource": resource_type, "id": resource_id, "before": before_val, "after": after_val} if side_effect_occurred else None},
            attempt_payload={"resource_type": resource_type, "resource_id": resource_id, "operation": operation},
            policy_reason=policy_reason,
            executed=allowed,
            result_status=res_status,
            side_effect_detected=side_effect_occurred,
            timestamp=_now()
        )
