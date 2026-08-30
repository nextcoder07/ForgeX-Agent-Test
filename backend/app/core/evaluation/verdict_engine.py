"""
Deterministic Verdict & Assertion Evaluation Engine.
Evaluates observed execution trace evidence against scenario assertions.
Produces dual states: execution_status + evaluation_verdict.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.execution import ExecutionTrace, TraceEvent
from app.models.scenario import Scenario, ScenarioAssertion


class AssertionFinding(BaseModel):
    assertion_id: str
    assertion_type: str
    passed: bool
    expected: str
    observed: str
    message: str


class DualVerdictResult(BaseModel):
    execution_status: str  # "BLOCKED", "FAILED", "TIMEOUT", "COMPLETED", "CANCELLED"
    evaluation_verdict: str  # "PASS", "FAIL", "INCONCLUSIVE", "NOT_EVALUABLE"
    findings: List[AssertionFinding] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    total_assertions: int = 0
    summary: str = ""


def evaluate_execution_verdict(
    trace: ExecutionTrace,
    scenario: Scenario
) -> DualVerdictResult:
    """Evaluates observed execution trace evidence deterministically against scenario assertions."""

    # 1. Handle Preflight Blocked State
    if trace.status == "BLOCKED":
        return DualVerdictResult(
            execution_status="BLOCKED",
            evaluation_verdict="NOT_EVALUABLE",
            findings=[],
            passed_count=0,
            failed_count=0,
            total_assertions=len(scenario.assertions or []),
            summary="Preflight blocked. Agent process never started. Execution is NOT_EVALUABLE."
        )

    # Collect Evidence Strings
    stdout_full = ""
    stderr_full = ""
    tool_names_called = set()

    for event in trace.events:
        content = event.content or ""
        if "STDOUT_CHUNK:" in content:
            stdout_full += content.replace("STDOUT_CHUNK:", "").strip() + "\n"
        elif "STDERR_CHUNK:" in content:
            stderr_full += content.replace("STDERR_CHUNK:", "").strip() + "\n"

    for tc in trace.tool_calls:
        tool_names_called.add(tc.tool_name.lower())

    findings: List[AssertionFinding] = []
    passed_count = 0
    failed_count = 0

    # 2. Evaluate Assertions
    for idx, astn in enumerate(scenario.assertions or []):
        astn_id = getattr(astn, "id", f"astn-{idx+1}")
        astn_type = getattr(astn, "assertion_type", "STDOUT_CONTAINS")
        target = getattr(astn, "target", "")
        expected = str(getattr(astn, "expected_value", "") or getattr(astn, "condition", ""))

        passed = False
        observed = ""

        if astn_type in ("STDOUT_CONTAINS", "STDOUT_REGEX"):
            passed = expected.lower() in stdout_full.lower() if expected else True
            observed = stdout_full.strip()[:100] if stdout_full else "No stdout captured"

        elif astn_type == "STDERR_CONTAINS":
            passed = expected.lower() in stderr_full.lower() if expected else True
            observed = stderr_full.strip()[:100] if stderr_full else "No stderr captured"

        elif astn_type in ("TOOL_CALLED", "TOOL_INVOKED"):
            target_tool = (target or expected).lower()
            passed = target_tool in tool_names_called
            observed = f"Called tools: {list(tool_names_called)}"

        elif astn_type == "PROCESS_EXIT_CODE":
            process_exit_event = next((e for e in trace.events if "PROCESS_EXITED:" in e.content), None)
            if process_exit_event:
                exit_code_str = process_exit_event.content.replace("PROCESS_EXITED: Exit code ", "").strip()
                passed = exit_code_str == expected or exit_code_str == "0"
                observed = f"Exit code {exit_code_str}"
            else:
                passed = trace.status == "COMPLETED"
                observed = f"Trace status: {trace.status}"

        elif astn_type == "NO_UNHANDLED_EXCEPTION":
            has_exception = "Traceback (most recent call last)" in stderr_full or "Unhandled exception" in stderr_full
            passed = not has_exception
            observed = "Unhandled exception detected in stderr" if has_exception else "Clean execution"

        else:
            # General fallback check against stdout/events
            passed = expected.lower() in (stdout_full + stderr_full).lower() if expected else True
            observed = f"Observed trace with {len(trace.events)} events"

        if passed:
            passed_count += 1
        else:
            failed_count += 1

        findings.append(AssertionFinding(
            assertion_id=astn_id,
            assertion_type=astn_type,
            passed=passed,
            expected=expected,
            observed=observed,
            message=f"Assertion {astn_type} {'PASSED' if passed else 'FAILED'}"
        ))

    # 3. Compute Final Evaluation Verdict
    if not scenario.assertions:
        verdict = "PASS" if trace.status == "COMPLETED" else "FAIL"
    elif failed_count == 0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    exec_status = trace.status  # "COMPLETED", "FAILED", "TIMEOUT"

    summary = f"Execution {exec_status} with verdict {verdict} ({passed_count}/{len(scenario.assertions or [])} assertions passed)."

    return DualVerdictResult(
        execution_status=exec_status,
        evaluation_verdict=verdict,
        findings=findings,
        passed_count=passed_count,
        failed_count=failed_count,
        total_assertions=len(scenario.assertions or []),
        summary=summary
    )
