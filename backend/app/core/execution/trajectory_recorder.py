import datetime as dt
import uuid
import threading
from typing import Dict, Any, List, Optional
from app.models.execution import ExecutionStep
from app.services.store import store

def _now() -> str:
    return dt.datetime.utcnow().isoformat()

class TrajectoryRecorder:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._step_counter = 0
        self._lock = threading.Lock()
        self.steps: List[ExecutionStep] = []

    def record_step(
        self,
        event_type: str,
        actor: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionStep:
        """Appends a sequential step event to the session trajectory."""
        with self._lock:
            self._step_counter += 1
            step = ExecutionStep(
                id=f"step-{uuid.uuid4().hex[:8]}",
                execution_session_id=self.session_id,
                step_number=self._step_counter,
                event_type=event_type,
                actor=actor,
                input_data=input_data or {},
                output_data=output_data or {},
                metadata=metadata or {},
                created_at=_now()
            )
            self.steps.append(step)
            try:
                store.save_execution_step(step)
            except Exception:
                pass
            return step

    def record_workflow_node_entered(self, node_id: str, input_state: Optional[Dict[str, Any]] = None) -> ExecutionStep:
        return self.record_step("WORKFLOW_NODE_ENTERED", actor="workflow", input_data={"node_id": node_id, "state": input_state or {}})

    def record_workflow_node_exited(self, node_id: str, output_state: Optional[Dict[str, Any]] = None) -> ExecutionStep:
        return self.record_step("WORKFLOW_NODE_EXITED", actor="workflow", output_data={"node_id": node_id, "state": output_state or {}})

    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any], status: str = "SUCCESS") -> ExecutionStep:
        return self.record_step("TOOL_CALL_RESULT", actor="agent", input_data={"tool": tool_name, "args": arguments}, output_data=result, metadata={"status": status})

    def record_llm_call(self, provider: str, model: str, prompt_summary: str, response: str) -> ExecutionStep:
        return self.record_step("LLM_CALL_RESULT", actor="llm", input_data={"provider": provider, "model": model, "prompt": prompt_summary}, output_data={"response": response})

    def record_sandbox_event(self, event_type: str, details: Dict[str, Any]) -> ExecutionStep:
        return self.record_step(event_type, actor="sandbox", input_data=details)

    def record_network_event(self, url: str, method: str, status_code: int, latency_ms: float) -> ExecutionStep:
        return self.record_step("NETWORK_RESPONSE", actor="network", input_data={"url": url, "method": method}, output_data={"status_code": status_code, "latency_ms": latency_ms})

    def get_trajectory(self) -> List[ExecutionStep]:
        with self._lock:
            return list(self.steps)
