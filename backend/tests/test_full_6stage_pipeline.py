from app.api.pipeline import _new_run


def test_full_pipeline_has_six_stages_and_matching_telemetry_ids():
    run = _new_run("agent-test", "Test Agent")

    assert run.total_stages == 6
    assert len(run.stages) == 6
    assert [stage.stage_name for stage in run.stages] == [
        "intake",
        "scenarios",
        "dependencies",
        "execution",
        "evaluation",
        "remediation",
    ]
    assert len({stage.id for stage in run.stages}) == 6


def test_pipeline_stages_start_queued_with_zero_metrics():
    run = _new_run("agent-test", "Test Agent")

    assert all(stage.status == "queued" for stage in run.stages)
    assert all(stage.progress_pct == 0 for stage in run.stages)
    assert all(stage.duration_ms == 0 for stage in run.stages)
