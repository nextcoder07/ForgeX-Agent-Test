"""
Scenario Coverage Gap Engine.
Detects unexercised agent tools, category deficits, and recommends targeted test plans.
"""

from __future__ import annotations

from typing import Dict, List
from app.models.agent import AgentRecord
from app.models.scenario import Scenario, CoverageGapReport, ScenarioCategory


def compute_coverage_gaps(
    agent: AgentRecord,
    scenarios: List[Scenario]
) -> CoverageGapReport:
    total_tools = len(agent.tools)
    all_tool_names = {t.name for t in agent.tools}

    exercised_tools = set()
    category_counts: Dict[str, int] = {cat.value: 0 for cat in ScenarioCategory}

    for sc in scenarios:
        category_counts[sc.category.value] = category_counts.get(sc.category.value, 0) + 1
        for cap in sc.required_capabilities:
            for t in agent.tools:
                if t.canonical_capability == cap or t.name.lower() == cap.lower():
                    exercised_tools.add(t.name)

    unexercised = list(all_tool_names - exercised_tools)
    total_scenarios = len(scenarios) if scenarios else 1

    category_coverage = {
        cat: min(100.0, round((count / max(1, total_scenarios * 0.12)) * 100.0, 1))
        for cat, count in category_counts.items()
    }

    coverage_pct = round((len(exercised_tools) / max(1, total_tools)) * 100.0, 1)

    gaps: List[str] = []
    if unexercised:
        gaps.append(f"{len(unexercised)} tool(s) never exercised in test suite: {', '.join(unexercised)}")

    for cat, score in category_coverage.items():
        if score < 50.0:
            gaps.append(f"Low test depth in '{cat.upper()}' category ({score}% coverage)")

    return CoverageGapReport(
        total_tools=total_tools,
        exercised_tools=len(exercised_tools),
        unexercised_tools=unexercised,
        category_coverage=category_coverage,
        overall_coverage_pct=coverage_pct,
        gaps_detected=gaps
    )
