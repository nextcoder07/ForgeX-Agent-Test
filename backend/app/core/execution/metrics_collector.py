import datetime as dt
import uuid
from typing import List, Dict, Any
from app.models.execution import ExecutionMetrics, ExecutionStep, ToolCallRecord
from app.services.store import store

def _now() -> str:
    return dt.datetime.utcnow().isoformat()

class MetricsCollector:
    def __init__(self, session_id: str):
        self.session_id = session_id

    def compute_metrics(
        self,
        steps: List[ExecutionStep],
        tool_calls: List[ToolCallRecord],
        total_latency_ms: float,
        tokens_used: int = 0
    ) -> ExecutionMetrics:
        failed_tools_count = sum(1 for tc in tool_calls if tc.status != "SUCCESS")
        
        # Estimate cost ($0.0001 per 1k tokens baseline)
        cost = round((tokens_used / 1000.0) * 0.0001, 6)

        metrics = ExecutionMetrics(
            id=f"met-{uuid.uuid4().hex[:8]}",
            execution_session_id=self.session_id,
            steps_count=len(steps),
            tool_calls_count=len(tool_calls),
            failed_tools=failed_tools_count,
            tokens_used=tokens_used,
            latency_ms=total_latency_ms,
            cost=cost,
            created_at=_now()
        )
        try:
            store.save_execution_metrics(metrics)
        except Exception:
            pass
        return metrics
