from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.models.scenario import Scenario, ScenarioFeasibility
from app.models.agent import AgentRecord


def evaluate_scenario_feasibility(
    scenario: Scenario,
    agent: AgentRecord
) -> ScenarioFeasibility:
    """Performs deterministic feasibility evaluation on a scenario."""
    blockers = []
    manifest = agent.runtime_manifest or {}
    entrypoint = manifest.get("entrypoint", "")
    
    # 1. Interface compatibility
    interface_compatible = True
    if scenario.interface_type == "CLI" and not entrypoint and not agent.tools:
        interface_compatible = False
        blockers.append("CLI scenario requires entrypoint script in runtime manifest.")

    # 2. Invocations & inputs
    inputs_available = True
    if scenario.interface_type == "CLI":
        has_args = bool(scenario.invocation.get("args") or scenario.invocation.get("arguments") or scenario.invocation.get("command"))
        if not has_args and not entrypoint:
            inputs_available = False
            blockers.append("Missing CLI invocation command or arguments.")
    elif scenario.interface_type == "HTTP":
        if not scenario.invocation.get("endpoint") and not scenario.invocation.get("path"):
            inputs_available = False
            blockers.append("Missing HTTP endpoint/path in invocation.")

    # 3. Assertions
    assertions_valid = len(scenario.assertions) > 0
    if not assertions_valid:
        blockers.append("Scenario must contain at least one verifiable assertion.")

    # 4. Tool / capability availability
    agent_tools = {t.name.lower() for t in agent.tools}
    caps_available = True
    for cap in scenario.required_capabilities:
        if cap.lower() not in agent_tools and not any(t.canonical_capability == cap for t in agent.tools):
            caps_available = False
            blockers.append(f"Required capability '{cap}' not exposed by agent.")

    executable = interface_compatible and inputs_available and assertions_valid and caps_available

    return ScenarioFeasibility(
        interface_compatible=interface_compatible,
        inputs_available=inputs_available,
        dependencies_available=caps_available,
        sandbox_supported=True,
        assertions_valid=assertions_valid,
        fault_injection_supported=True,
        executable=executable,
        blockers=blockers
    )


def validate_scenarios_deterministically(
    scenarios: List[Scenario],
    agent: AgentRecord
) -> List[Scenario]:
    """Ensures test scenarios only require tools, capabilities, and interfaces actually supported by the agent."""
    validated: List[Scenario] = []

    for sc in scenarios:
        if sc.validation_status == "REJECTED_CRITIC":
            sc.status = "REJECTED"
            continue

        feasibility = evaluate_scenario_feasibility(sc, agent)
        if feasibility.executable:
            sc.validation_status = "VALIDATED"
            sc.status = "READY"
        else:
            sc.validation_status = "BLOCKED_DEPENDENCY"
            sc.status = "BLOCKED"
            sc.critic_notes = f"Blocked: {'; '.join(feasibility.blockers)}"

        validated.append(sc)

    return validated
