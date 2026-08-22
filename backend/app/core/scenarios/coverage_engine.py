"""
Scenario Coverage Gap Engine.
Computes multi-surface behavioral coverage across Interface, Workflow, Services,
Capabilities, Invariants, Failure Surfaces, and Categories.
"""

from __future__ import annotations

from typing import Dict, List, Set
from app.models.agent import AgentRecord
from app.models.scenario import Scenario, CoverageGapReport, ScenarioCategory


def compute_coverage_gaps(
    agent: AgentRecord,
    scenarios: List[Scenario]
) -> CoverageGapReport:
    total_tools = len(agent.tools)
    all_tool_names = {t.name for t in agent.tools}
    exercised_tools: Set[str] = set()

    # Category distribution
    category_counts: Dict[str, int] = {cat.value: 0 for cat in ScenarioCategory}
    
    # Behavioral surfaces
    tested_capabilities: Set[str] = set()
    tested_services: Set[str] = set()
    tested_failure_surfaces: Set[str] = set()
    tested_invariants: Set[str] = set()
    tested_interfaces: Set[str] = set()

    for sc in scenarios:
        category_counts[sc.category.value] = category_counts.get(sc.category.value, 0) + 1
        
        # Tools
        for cap in sc.required_capabilities:
            tested_capabilities.add(cap.upper())
            for t in agent.tools:
                if t.canonical_capability == cap or t.name.lower() == cap.lower():
                    exercised_tools.add(t.name)
                    
        # Services
        for s in sc.required_services:
            tested_services.add(s.upper())
            
        # Failure Surfaces & Invariants
        if sc.target_failure_surface:
            tested_failure_surfaces.add(sc.target_failure_surface)
        if sc.target_invariant:
            tested_invariants.add(sc.target_invariant)
            
        # Interface
        if sc.interface_type:
            tested_interfaces.add(sc.interface_type.upper())

    unexercised_tools = list(all_tool_names - exercised_tools)
    total_scenarios = len(scenarios) if scenarios else 1

    # Category coverage percentages
    category_coverage = {
        cat: min(100.0, round((count / max(1, total_scenarios * 0.12)) * 100.0, 1))
        for cat, count in category_counts.items()
    }

    # Dimensions
    tool_cov = round((len(exercised_tools) / max(1, total_tools)) * 100.0, 1) if total_tools > 0 else 100.0
    cap_cov = round(min(100.0, len(tested_capabilities) / max(1, len(agent.tools) or 1) * 100.0), 1)
    interface_cov = 100.0 if len(tested_interfaces) > 0 else 0.0
    failure_cov = round(min(100.0, len(tested_failure_surfaces) / max(1, 4) * 100.0), 1)
    invariant_cov = round(min(100.0, len(tested_invariants) / max(1, 3) * 100.0), 1)
    category_avg = round(sum(category_coverage.values()) / max(1, len(category_coverage)), 1)

    # Composite overall coverage score
    if total_tools > 0:
        overall_pct = round(tool_cov * 0.3 + category_avg * 0.3 + failure_cov * 0.2 + interface_cov * 0.2, 1)
    else:
        overall_pct = round(category_avg * 0.4 + failure_cov * 0.3 + interface_cov * 0.3, 1)

    gaps: List[str] = []
    if unexercised_tools:
        gaps.append(f"{len(unexercised_tools)} tool(s) never exercised in test suite: {', '.join(unexercised_tools)}")

    if not tested_interfaces:
        gaps.append("Interface contract has not been exercised by any test scenario.")

    for cat, score in category_coverage.items():
        if score < 50.0:
            gaps.append(f"Low test depth in '{cat.upper()}' category ({score}% coverage)")

    return CoverageGapReport(
        total_tools=total_tools,
        exercised_tools=len(exercised_tools),
        unexercised_tools=unexercised_tools,
        interface_coverage_pct=interface_cov,
        capability_coverage_pct=cap_cov,
        failure_surface_coverage_pct=failure_cov,
        invariant_coverage_pct=invariant_cov,
        category_coverage=category_coverage,
        overall_coverage_pct=min(100.0, max(0.0, overall_pct)),
        gaps_detected=gaps
    )
