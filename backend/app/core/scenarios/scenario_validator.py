"""
Deterministic Scenario Validator.
Verifies that all required capabilities, tools, and mock data adapters exist before admission to Scenario Library.
"""

from __future__ import annotations

from typing import List
from app.models.scenario import Scenario
from app.models.agent import AgentRecord


def validate_scenarios_deterministically(
    scenarios: List[Scenario],
    agent: AgentRecord
) -> List[Scenario]:
    """Ensures test scenarios only require tools and capabilities actually present in the agent."""
    agent_tool_names = {t.name.lower() for t in agent.tools}
    agent_capabilities = {t.canonical_capability.upper() for t in agent.tools if t.canonical_capability}

    validated: List[Scenario] = []

    for sc in scenarios:
        if sc.validation_status == "REJECTED_CRITIC":
            validated.append(sc)
            continue

        # Check required capabilities
        all_caps_present = True
        for cap in sc.required_capabilities:
            if cap.upper() not in agent_capabilities and cap.lower() not in agent_tool_names:
                all_caps_present = False
                break

        if not all_caps_present:
            sc.validation_status = "BLOCKED_DEPENDENCY"
            sc.critic_notes = f"Blocked: Requires capabilities ({', '.join(sc.required_capabilities)}) not exposed by agent."
        else:
            sc.validation_status = "VALIDATED"

        validated.append(sc)

    return validated
