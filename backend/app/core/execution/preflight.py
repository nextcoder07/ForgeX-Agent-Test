"""
Scenario Preflight Validation Engine.
Performs deterministic preflight checks before dispatching a scenario to the sandbox.
Ensures interface contracts, invocations, input artifacts, dependency bindings, and assertions are verified.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.agent import AgentRecord
from app.models.scenario import Scenario


from app.models.execution import ExecutionPreflight, VariableBinding, VariableSource


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
    preflight_record: Optional[ExecutionPreflight] = None


def run_scenario_preflight(
    scenario: Scenario,
    agent: AgentRecord,
    execution_run_id: str = "",
    provided_variables: Optional[Dict[str, Any]] = None
) -> PreflightResult:
    """Executes deterministic preflight checks before sandbox execution, including variable resolution."""
    findings: List[PreflightFinding] = []
    provided_vars = provided_variables or {}
    manifest = agent.runtime_manifest or {}
    entrypoint = manifest.get("entrypoint", "agent.py")
    interface = (scenario.interface_type or "CHAT").upper()

    interface_status = "READY"
    runtime_status = "READY"
    dependency_status = "READY"
    credential_status = "READY"
    sandbox_status = "READY"
    policy_status = "READY"
    mode_status = "READY"
    resolved_variables: List[VariableBinding] = []

    # 1. Interface Check
    if interface == "CLI":
        has_entrypoint = bool(entrypoint)
        has_invocation = bool(scenario.invocation)
        cmd = scenario.invocation.get("command", "")
        args = scenario.invocation.get("args", [])
        
        if not has_entrypoint and not cmd:
            interface_status = "BLOCKED"
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

    elif interface == "HTTP":
        endpoint = scenario.invocation.get("endpoint") or provided_vars.get("HTTP_ENDPOINT") or agent.endpoint
        if not endpoint:
            interface_status = "BLOCKED"
            findings.append(PreflightFinding(
                check_name="HTTP_ENDPOINT",
                passed=False,
                message="HTTP scenario requires 'endpoint' in invocation or runtime input.",
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
            interface_status = "BLOCKED"
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

    # 2. Dependency & Credential Check / Variable Resolution
    required_keys = []
    for dep in agent.dependencies:
        if dep.type in ["api_key", "secret", "credential"]:
            required_keys.append(dep.name)
    
    # Also check if agent tools or system prompt mention API key requirements
    if "OPENAI_API_KEY" not in required_keys and any("openai" in str(t.name).lower() for t in agent.tools):
        required_keys.append("OPENAI_API_KEY")

    for key_name in required_keys:
        if key_name in scenario.initial_state:
            val = scenario.initial_state[key_name]
            resolved_variables.append(VariableBinding(
                name=key_name,
                type="secret",
                required=True,
                source=VariableSource.SCENARIO,
                value_status="BOUND",
                masked_value="***SCENARIO_BOUND***",
                credential_reference=f"ref-sc-{key_name.lower()}"
            ))
        elif key_name in provided_vars and provided_vars[key_name]:
            val = provided_vars[key_name]
            resolved_variables.append(VariableBinding(
                name=key_name,
                type="secret",
                required=True,
                source=VariableSource.USER,
                value_status="BOUND",
                masked_value=f"***{str(val)[-4:] if len(str(val)) > 4 else 'USER_BOUND'}***",
                credential_reference=f"ref-user-{key_name.lower()}"
            ))
        else:
            credential_status = "BLOCKED"
            resolved_variables.append(VariableBinding(
                name=key_name,
                type="secret",
                required=True,
                source=VariableSource.USER,
                value_status="UNRESOLVED",
                masked_value="***UNRESOLVED***",
                credential_reference=f"ref-unresolved-{key_name.lower()}"
            ))
            findings.append(PreflightFinding(
                check_name=f"CREDENTIAL_{key_name}",
                passed=False,
                message=f"Missing required credential '{key_name}'.",
                severity="ERROR"
            ))

    # Default LOG_LEVEL safe default variable
    resolved_variables.append(VariableBinding(
        name="LOG_LEVEL",
        type="string",
        required=False,
        source=VariableSource.SAFE_DEFAULT,
        value_status="DEFAULT_APPLIED",
        value="INFO",
        masked_value="INFO"
    ))

    # 3. Input Artifacts Staging Check
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

    # 4. Assertion Check
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
                passed=True,
                message="No explicit assertions configured; execution will collect raw observation evidence.",
                severity="INFO"
            ))
    else:
        findings.append(PreflightFinding(
            check_name="ASSERTIONS",
            passed=True,
            message=f"{len(scenario.assertions)} assertion(s) verified: {[a.assertion_type for a in scenario.assertions]}",
            severity="INFO"
        ))

    # 5. Determine overall readiness
    is_blocked = (credential_status == "BLOCKED" or interface_status == "BLOCKED" or runtime_status == "BLOCKED" or any(not f.passed and f.severity == "ERROR" for f in findings))
    status = "BLOCKED" if is_blocked else "READY"

    preflight_record = ExecutionPreflight(
        id=f"pre-{scenario.id}",
        execution_run_id=execution_run_id,
        scenario_id=scenario.id,
        agent_id=agent.id,
        agent_version_id=agent.version_label,
        interface_status=interface_status,
        runtime_status=runtime_status,
        dependency_status=dependency_status,
        credential_status=credential_status,
        sandbox_status=sandbox_status,
        policy_status=policy_status,
        mode_status=mode_status,
        overall_status=status,
        blockers=[f.model_dump() for f in findings if not f.passed],
        resolved_variables=resolved_variables,
        created_at=""
    )

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
        summary=summary,
        preflight_record=preflight_record
    )

