from typing import Dict, Any, List
from app.models.execution import StateChange

class StateTracker:
    def __init__(self, initial_state: Dict[str, Any] = None):
        self.initial_state = initial_state or {}
        self.current_state = dict(self.initial_state)
        self.state_changes: List[StateChange] = []

    def update_state(self, resource_type: str, resource_id: str, field: str, new_value: Any) -> StateChange:
        before_val = self.current_state.get(field)
        self.current_state[field] = new_value
        change = StateChange(
            resource_type=resource_type,
            resource_id=resource_id,
            field=field,
            before_value=before_val,
            after_value=new_value
        )
        self.state_changes.append(change)
        return change

    def get_state_snapshot(self) -> Dict[str, Any]:
        return dict(self.current_state)
