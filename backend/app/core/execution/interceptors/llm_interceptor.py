"""LLM Interceptor - Emits normalized 4-layer ExecutionAction records for LLM model calls."""
import uuid
import datetime as dt
from typing import Any, Dict
from app.models.execution import ExecutionAction


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class LLMInterceptor:
    @staticmethod
    def intercept_call(
        session_id: str,
        sequence: int,
        model_name: str,
        messages_count: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        substitution_applied: bool = False,
        original_model: str = None,
        latency_ms: float = 0.0
    ) -> ExecutionAction:
        act_id = f"act-{uuid.uuid4().hex[:8]}"
        attempt_payload = {
            "model": original_model or model_name,
            "messages_count": messages_count,
            "substitution_requested": substitution_applied
        }
        policy_reason = f"Model substituted from {original_model} to {model_name}" if substitution_applied else "LLM access allowed"

        return ExecutionAction(
            id=act_id,
            action_id=act_id,
            execution_session_id=session_id,
            sequence=sequence,
            action_type="LLM_CALL",
            target=model_name,
            action_attempt={"payload": attempt_payload, "target": model_name},
            policy_decision={"decision": "ALLOW", "reason": policy_reason},
            execution_result={"status": "SUCCESS", "executed": True, "input_tokens": input_tokens, "output_tokens": output_tokens, "latency_ms": latency_ms},
            side_effect={"detected": False, "details": None},
            attempt_payload=attempt_payload,
            policy_reason=policy_reason,
            executed=True,
            result_status="SUCCESS",
            side_effect_detected=False,
            timestamp=_now()
        )
