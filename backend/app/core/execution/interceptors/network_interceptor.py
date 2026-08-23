"""Network Interceptor - Emits normalized 4-layer ExecutionAction records for outbound network attempts."""
import uuid
import datetime as dt
from typing import Any, Dict
from app.models.execution import ExecutionAction


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class NetworkInterceptor:
    @staticmethod
    def intercept_request(
        session_id: str,
        sequence: int,
        host: str,
        method: str,
        path: str,
        allowed: bool = True,
        policy_reason: str = None,
        response_status: int = 200,
        side_effect_occurred: bool = False
    ) -> ExecutionAction:
        act_id = f"act-{uuid.uuid4().hex[:8]}"
        pol_decision = "ALLOW" if allowed else "BLOCK"
        res_status = "SUCCESS" if (allowed and response_status < 400) else ("BLOCKED_POLICY" if not allowed else "ERROR")

        return ExecutionAction(
            id=act_id,
            action_id=act_id,
            execution_session_id=session_id,
            sequence=sequence,
            action_type="NETWORK_REQUEST",
            target=f"{method} {host}{path}",
            action_attempt={"payload": {"host": host, "method": method, "path": path}, "target": host},
            policy_decision={"decision": pol_decision, "reason": policy_reason or ("Domain allowlist permitted request" if allowed else "Outbound network sandbox default DENY policy")},
            execution_result={"status": res_status, "executed": allowed, "response_status": response_status if allowed else None},
            side_effect={"detected": side_effect_occurred, "details": {"host": host, "method": method, "path": path} if side_effect_occurred else None},
            attempt_payload={"host": host, "method": method, "path": path},
            policy_reason=policy_reason,
            executed=allowed,
            result_status=res_status,
            side_effect_detected=side_effect_occurred,
            timestamp=_now()
        )
