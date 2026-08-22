import time
from typing import Dict, Any, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.core.execution.trajectory_recorder import TrajectoryRecorder
from app.core.execution.action_tracker import ActionTracker
from app.core.execution.state_tracker import StateTracker
from app.core.sandbox.runner import run_scenario_in_sandbox

async def run_agent_in_environment(
    agent: AgentRecord,
    scenario: Scenario,
    recorder: TrajectoryRecorder,
    action_tracker: ActionTracker,
    state_tracker: StateTracker,
    provided_secrets: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Runs the agent inside the controlled sandbox environment while logging trajectory steps."""
    
    # 1. Record USER_INPUT event
    for turn_idx, msg in enumerate(scenario.user_messages):
        recorder.record_step(
            event_type="USER_INPUT",
            actor="user",
            input_data={"turn": turn_idx + 1, "message": msg}
        )

    start_t = time.time()
    # 2. Execute scenario via sandboxed runner with provided secrets
    trace = run_scenario_in_sandbox(agent, scenario, provided_secrets=provided_secrets)
    dur_ms = (time.time() - start_t) * 1000.0

    # 3. Log actions & state changes into trajectory recorder
    for tc in trace.tool_calls:
        action_tracker.record_tool_call(
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            result=tc.result,
            latency_ms=tc.latency_ms,
            gateway_action=tc.routing_decision,
            status=tc.status,
            injected_fault=tc.injected_fault
        )
        recorder.record_step(
            event_type="TOOL_CALL",
            actor="agent",
            input_data={"tool": tc.tool_name, "arguments": tc.arguments},
            output_data={"result": tc.result, "status": tc.status},
            metadata={"latency_ms": tc.latency_ms, "gateway": tc.routing_decision}
        )

    for sc in trace.state_changes:
        state_tracker.update_state(sc.resource_type, sc.resource_id, sc.field, sc.after_value)
        recorder.record_step(
            event_type="STATE_CHANGE",
            actor="environment",
            input_data={"resource_type": sc.resource_type, "field": sc.field, "before": sc.before_value},
            output_data={"after": sc.after_value}
        )

    # 4. Final output step
    final_output = trace.events[-1].content if trace.events else "Scenario execution completed."
    recorder.record_step(
        event_type="FINAL_RESPONSE",
        actor="agent",
        output_data={"response": final_output}
    )

    return {
        "trace": trace,
        "duration_ms": dur_ms,
        "final_output": final_output
    }
