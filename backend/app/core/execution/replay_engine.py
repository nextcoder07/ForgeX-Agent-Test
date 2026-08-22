from typing import Dict, Any, List, Optional
from app.models.execution import ExecutionStep, ExecutionSession
from app.services.store import store

class ReplayEngine:
    """
    Kaggle-Style Replay Engine.
    Reconstructs an execution session trajectory step-by-step from event-sourcing records
    to perform deterministic regression testing and benchmark comparisons.
    """
    @staticmethod
    def fetch_trajectory(session_id: str) -> List[ExecutionStep]:
        return store.get_execution_steps(session_id)

    @staticmethod
    def replay_session(session_id: str) -> Dict[str, Any]:
        session = store.get_execution_session(session_id)
        if not session:
            return {"error": f"Execution session '{session_id}' not found", "reconstructed": False}

        steps = store.get_execution_steps(session_id)
        metrics = store.get_execution_metrics(session_id)

        events_summary = []
        for step in steps:
            events_summary.append({
                "step": step.step_number,
                "actor": step.actor,
                "event_type": step.event_type,
                "input": step.input_data,
                "output": step.output_data,
                "timestamp": step.created_at
            })

        return {
            "session_id": session_id,
            "agent_version_id": session.agent_version_id,
            "scenario_id": session.scenario_id,
            "status": session.status,
            "total_steps": len(steps),
            "reconstructed": True,
            "events_summary": events_summary,
            "metrics": metrics.dict() if metrics else None
        }
