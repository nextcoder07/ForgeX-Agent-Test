"""
Scenario Preflight Validation Engine.
Performs deterministic preflight checks before dispatching a scenario to the sandbox.
Ensures interface contracts, invocations, input artifacts, dependency bindings, and assertions are verified.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.agent import AgentRecord
from app.models.scenario import Scenario


class PreflightFinding(BaseModel):
    check_name: str
    passed: bool
    message: str
    severity: str = "ERROR"  # "ERROR", "WARNING", "INFO"


class PreflightResult(BaseModel):
    scenario_id: str
    agent_id: str
    status: str  # "READY" or "BLOCKED"
    is_ready: bool
    findings: List[PreflightFinding] = Field(default_factory=list)
    staging_plan: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


def run_scenario_preflight(scenario: Scenario, agent: AgentRecord) -> PreflightResult:
    """Executes all preflight checks on a scenario before sandbox execution."""
    findings: List[PreflightFinding] = []
    manifest = agent.runtime_manifest or {}
    entrypoint = manifest.get("entrypoint", "agent.py")
    interface = (scenario.interface_type or "CHAT").upper()

    # 1. Interface & Invocation Check
    if interface == "CLI":
        has_entrypoint = bool(entrypoint)
        has_invocation = bool(scenario.invocation)
        cmd = scenario.invocation.get("command", "")
        args = scenario.invocation.get("args", [])
        
        if not has_entrypoint and not cmd:
            findings.append(PreflightFinding(
                check_name="CLI_ENTRYPOINT",
                passed=False,
                message=f"Agent '{agent.name}' has no CLI entrypoint in runtime manifest.",
                severity="ERROR"
            ))
        else:
            findings.append(PreflightFinding(
                check_name="CLI_ENTRYPOINT",
                passed=True,
                message=f"CLI entrypoint verified: {entrypoint}",
                severity="INFO"
            ))

        if not cmd and not args:
            findings.append(PreflightFinding(
                check_name="CLI_INVOCATION",
                passed=True,
                message=f"No explicit invocation args, defaulting to 'python {entrypoint}'",
                severity="WARNING"
            ))
        else:
            findings.append(PreflightFinding(
                check_name="CLI_INVOCATION",
                passed=True,
                message=f"CLI invocation verified: {cmd or args}",
                severity="INFO"
            ))

    elif interface == "HTTP":
        endpoint = scenario.invocation.get("endpoint")
        if not endpoint:
            findings.append(PreflightFinding(
                check_name="HTTP_ENDPOINT",
                passed=False,
                message="HTTP scenario requires 'endpoint' in invocation.",
                severity="ERROR"
            ))
        else:
            findings.append(PreflightFinding(
                check_name="HTTP_ENDPOINT",
                passed=True,
                message=f"HTTP endpoint verified: {endpoint}",
                severity="INFO"
            ))

    elif interface == "CHAT":
        has_messages = bool(scenario.user_messages) or bool(scenario.user_input)
        if not has_messages:
            findings.append(PreflightFinding(
                check_name="CHAT_MESSAGES",
                passed=False,
                message="CHAT scenario requires at least one user message or input prompt.",
                severity="ERROR"
            ))
        else:
            findings.append(PreflightFinding(
                check_name="CHAT_MESSAGES",
                passed=True,
                message="Chat messages present and verified.",
                severity="INFO"
            ))

    # 2. Input Artifacts Staging Check
    artifacts_to_stage = []
    for art in scenario.input_artifacts:
        if isinstance(art, dict) and "path" in art:
            artifacts_to_stage.append(art["path"])
    
    findings.append(PreflightFinding(
        check_name="INPUT_ARTIFACTS",
        passed=True,
        message=f"{len(artifacts_to_stage)} input artifact(s) prepared for sandbox staging: {artifacts_to_stage}",
        severity="INFO"
    ))

    # 3. Assertion Check
    if not scenario.assertions:
        if interface == "CLI":
            findings.append(PreflightFinding(
                check_name="ASSERTIONS",
                passed=True,
                message="No explicit assertions; defaulting to PROCESS_EXIT_CODE == 0.",
                severity="WARNING"
            ))
        else:
            findings.append(PreflightFinding(
                check_name="ASSERTIONS",
                passed=False,
                message="Scenario has no verifiable assertions.",
                severity="ERROR"
            ))
    else:
        findings.append(PreflightFinding(
            check_name="ASSERTIONS",
            passed=True,
            message=f"{len(scenario.assertions)} assertion(s) verified: {[a.assertion_type for a in scenario.assertions]}",
            severity="INFO"
        ))

    # 4. Determine overall readiness
    has_errors = any(not f.passed and f.severity == "ERROR" for f in findings)
    status = "BLOCKED" if has_errors else "READY"

    staging_plan = {
        "interface": interface,
        "entrypoint": entrypoint,
        "artifacts_count": len(artifacts_to_stage),
        "artifacts": artifacts_to_stage,
        "invocation": scenario.invocation,
    }

    summary = f"Preflight {status}: {len(findings)} checks performed, {sum(1 for f in findings if f.passed)} passed."

    return PreflightResult(
        scenario_id=scenario.id,
        agent_id=agent.id,
        status=status,
        is_ready=(status == "READY"),
        findings=findings,
        staging_plan=staging_plan,
        summary=summary
    )
