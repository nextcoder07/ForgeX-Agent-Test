"""
Multi-Turn Scenario Generation Engine with Fault Injection Mapping.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List
from app.models.agent import AgentRecord
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    FaultInjection,
    ScenarioAssertion,
    StrategyPlan
)
from app.core.llm.base import LLMProvider


async def generate_scenarios_for_agent(
    agent: AgentRecord,
    strategy: StrategyPlan,
    llm: LLMProvider
) -> List[Scenario]:
    """Generates concrete multi-turn test scenarios covering each category in the strategy plan using LLM intelligence."""
    # 1. Construct serialized NormalizedAgentSpec for LLM context
    agent_spec: Dict[str, Any] = {
        "id": agent.id,
        "name": agent.name,
        "domain": agent.domain,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters_schema": t.parameters_schema,
                "risk": t.risk.value if hasattr(t.risk, "value") else str(t.risk),
                "is_destructive": t.is_destructive,
                "requires_confirmation": t.requires_confirmation,
                "requires_authorization": t.requires_authorization,
                "max_amount": t.max_amount,
                "canonical_capability": t.canonical_capability,
                "side_effect_type": t.side_effect_type,
            }
            for t in agent.tools
        ],
        "constitution": {
            "goals": agent.constitution.goals,
            "never_rules": agent.constitution.never_rules,
            "always_rules": agent.constitution.always_rules,
            "escalation_rules": agent.constitution.escalation_rules,
            "data_policies": agent.constitution.data_policies,
        },
        "dependencies": [
            {"id": d.id, "name": d.name, "type": d.type, "required": d.required}
            for d in agent.dependencies
        ]
    }

    strategy_dict: Dict[str, Any] = {
        "agent_name": strategy.agent_name,
        "total_target": strategy.total_target,
        "summary": strategy.summary,
        "category_distribution": [
            {
                "category": t.category.value if hasattr(t.category, "value") else str(t.category),
                "target_count": t.target_count,
                "focus_risk": t.focus_risk,
                "rationale": t.rationale,
            }
            for t in strategy.category_distribution
        ]
    }

    # 2. Call LLM to generate scenarios
    raw_scenarios = await llm.generate_scenarios(agent_spec, strategy_dict)
    scenarios: List[Scenario] = []

    # 3. Parse and validate each scenario object
    for raw in raw_scenarios:
        try:
            cat_str = str(raw.get("category", "normal")).lower()
            try:
                category = ScenarioCategory(cat_str)
            except ValueError:
                category = ScenarioCategory.NORMAL

            sc_id = f"SC-{category.value[:3].upper()}-{uuid.uuid4().hex[:6]}"

            # Parse fault injections
            faults: List[FaultInjection] = []
            for f in raw.get("fault_injections", []):
                if isinstance(f, dict) and f.get("target_tool"):
                    faults.append(FaultInjection(
                        target_tool=f["target_tool"],
                        fault_type=f.get("fault_type", "timeout"),
                        occurrence=f.get("occurrence", 1),
                        parameters=f.get("parameters", {})
                    ))

            # Parse assertions
            assertions: List[ScenarioAssertion] = []
            for a in raw.get("assertions", []):
                if isinstance(a, dict) and a.get("assertion_type"):
                    assertions.append(ScenarioAssertion(
                        assertion_type=a["assertion_type"],
                        target=a.get("target", ""),
                        expected_value=a.get("expected_value"),
                        description=a.get("description", "")
                    ))

            user_messages = raw.get("user_messages", [])
            if isinstance(user_messages, str):
                user_messages = [user_messages]
            elif not isinstance(user_messages, list) or len(user_messages) == 0:
                user_messages = [f"Execute test task for {agent.name}"]

            scenario = Scenario(
                id=sc_id,
                agent_id=agent.id,
                version=1,
                category=category,
                title=raw.get("title", f"{category.value.title()} Test"),
                purpose=raw.get("purpose", f"Evaluate agent behavior under {category.value} conditions."),
                user_messages=user_messages,
                initial_state=raw.get("initial_state", {}),
                required_capabilities=raw.get("required_capabilities", [t.name.upper() for t in agent.tools[:2]]),
                fault_injections=faults,
                assertions=assertions,
                safety_constraints=raw.get("safety_constraints", agent.constitution.never_rules),
                rationale=raw.get("rationale", f"Validates {category.value} risk resilience for {agent.name}."),
            )
            scenarios.append(scenario)
        except Exception as err:
            continue

    # 4. Fallback if LLM output was empty or failed validation
    if not scenarios:
        for cat_target in strategy.category_distribution:
            for idx in range(cat_target.target_count):
                primary_tool = agent.tools[0].name if agent.tools else "process_task"
                sc_id = f"SC-{cat_target.category.value[:3].upper()}-{uuid.uuid4().hex[:6]}"
                scenarios.append(Scenario(
                    id=sc_id,
                    agent_id=agent.id,
                    version=1,
                    category=cat_target.category,
                    title=f"{cat_target.category.value.title()} Test for {primary_tool} #{idx + 1}",
                    purpose=f"Evaluate {primary_tool} against {cat_target.focus_risk}.",
                    user_messages=[f"Please execute {primary_tool} for request #{idx + 1}."],
                    initial_state={"test_idx": idx + 1},
                    required_capabilities=[primary_tool.upper()],
                    fault_injections=[],
                    assertions=[ScenarioAssertion(assertion_type="TOOL_CALLED_WITH", target=primary_tool)],
                    safety_constraints=agent.constitution.never_rules,
                    rationale=cat_target.rationale,
                ))

    return scenarios

