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

    def get_trajectory(self) -> List[ExecutionStep]:
        with self._lock:
            return list(self.steps)
