import time
from typing import Dict, Any, List, Optional
from app.models.execution import ToolCallRecord

class ActionTracker:
    def __init__(self):
        self.tool_calls: List[ToolCallRecord] = []
        self.gateway_actions: List[Dict[str, Any]] = []

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        latency_ms: float,
        gateway_action: str = "ALLOWED",
        status: str = "SUCCESS",
        injected_fault: Optional[str] = None
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            id=f"toolcall-{len(self.tool_calls) + 1}",
            sequence=len(self.tool_calls) + 1,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            latency_ms=latency_ms,
            status=status,
            routing_decision=gateway_action,
            injected_fault=injected_fault
        )
        self.tool_calls.append(record)
        self.gateway_actions.append({
            "sequence": record.sequence,
            "tool_name": tool_name,
            "gateway_action": gateway_action,
            "status": status,
            "timestamp": time.time()
        })
        return record

    def get_action_sequence(self) -> List[str]:
        return [tc.tool_name for tc in self.tool_calls]
