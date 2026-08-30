from app.services.store import Store


def test_clear_execution_data_for_agent_removes_prior_runs_for_same_agent():
    store = Store()

    agent_id = "agent-exec-replace"
    first_run_id = "exec-old-1"
    second_run_id = "exec-old-2"

    store.execution_jobs[first_run_id] = type("Job", (), {"id": first_run_id, "agent_id": agent_id})()
    store.execution_jobs[second_run_id] = type("Job", (), {"id": second_run_id, "agent_id": agent_id})()
    store.execution_runs[first_run_id] = type("Run", (), {"id": first_run_id, "agent_id": agent_id})()
    store.execution_runs[second_run_id] = type("Run", (), {"id": second_run_id, "agent_id": agent_id})()
    store.traces[first_run_id] = ["old-trace"]
    store.traces[second_run_id] = ["old-trace-2"]

    session_a = type("Session", (), {"id": "sess-a", "execution_run_id": first_run_id})()
    session_b = type("Session", (), {"id": "sess-b", "execution_run_id": second_run_id})()
    store.execution_sessions[session_a.id] = session_a
    store.execution_sessions[session_b.id] = session_b

    store.clear_execution_data_for_agent(agent_id)

    assert first_run_id not in store.execution_jobs
    assert second_run_id not in store.execution_jobs
    assert first_run_id not in store.execution_runs
    assert second_run_id not in store.execution_runs
    assert first_run_id not in store.traces
    assert second_run_id not in store.traces
    assert "sess-a" not in store.execution_sessions
    assert "sess-b" not in store.execution_sessions
