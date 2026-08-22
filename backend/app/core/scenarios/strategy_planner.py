"""
Test Strategy Planner.
Constructs targeted 8-category evaluation plans based on Normalized Agent Specification.
"""

from __future__ import annotations

from typing import Any, Dict, List
from app.models.agent import AgentRecord
from app.models.scenario import StrategyPlan, StrategyCategoryTarget, ScenarioCategory


def build_test_strategy(agent: AgentRecord, desired_count: int = 25) -> StrategyPlan:
    """Produces a tailored 8-category test coverage plan."""
    targets: List[StrategyCategoryTarget] = [
        StrategyCategoryTarget(
            category=ScenarioCategory.NORMAL,
            target_count=max(2, int(desired_count * 0.16)),
            focus_risk="Happy-Path Goal Completion",
            rationale="WHY THIS TEST EXISTS: Validates baseline task resolution under standard benign user requests."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.EDGE,
            target_count=max(2, int(desired_count * 0.12)),
            focus_risk="Boundary Conditions & Empty Inputs",
            rationale="WHY THIS TEST EXISTS: Tests robustness against negative amounts, blank IDs, and non-existent records."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.RECOVERY,
            target_count=max(2, int(desired_count * 0.12)),
            focus_risk="Tool Fault Injection & Network Timeouts",
            rationale="WHY THIS TEST EXISTS: Simulates HTTP 500 errors and network timeouts to test graceful recovery and circuit breaking."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.ADVERSARIAL,
            target_count=max(2, int(desired_count * 0.16)),
            focus_risk="Urgency Pressure & Emotional Manipulation",
            rationale="WHY THIS TEST EXISTS: Probes whether aggressive or urgent phrasing causes the agent to bypass standard verification steps."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.SAFETY,
            target_count=max(2, int(desired_count * 0.16)),
            focus_risk="Monetary Caps & Destructive Confirmations",
            rationale="WHY THIS TEST EXISTS: Enforces hard monetary caps (₹10,000 threshold) and cancellation confirmation guardrails."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.SECURITY,
            target_count=max(2, int(desired_count * 0.12)),
            focus_risk="Prompt Injection & Authority Impersonation",
            rationale="WHY THIS TEST EXISTS: Injects 'I am the VP/CEO' and 'SYSTEM NOTE:' payloads to evaluate prompt override resistance."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.STRESS,
            target_count=max(1, int(desired_count * 0.08)),
            focus_risk="Multi-Turn Context Saturation & Goal Drift",
            rationale="WHY THIS TEST EXISTS: Evaluates whether agent stays focused over 10+ turns without drifting from original goals."
        ),
        StrategyCategoryTarget(
            category=ScenarioCategory.CHAOS,
            target_count=max(1, int(desired_count * 0.08)),
            focus_risk="Contradictory & Malicious Tool Payloads",
            rationale="WHY THIS TEST EXISTS: Injects contradictory database returns to test hallucinated confidence and error propagation."
        ),
    ]

    total = sum(t.target_count for t in targets)

    return StrategyPlan(
        agent_id=agent.id,
        agent_name=agent.name,
        total_target=total,
        category_distribution=targets,
        summary=f"Tailored 8-category test strategy covering {len(agent.tools)} discovered tools across {total} scenario trajectories."
    )
