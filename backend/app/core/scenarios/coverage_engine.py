"""
Scenario Coverage Gap Engine.
Computes multi-surface behavioral coverage across Interface, Workflow, Services,
Capabilities, Invariants, Failure Surfaces, and Categories.
"""

from __future__ import annotations

from typing import Dict, List, Set, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario, CoverageGapReport, ScenarioCategory
from app.core.scenarios.scenario_context import build_scenario_context


def compute_coverage_gaps(
    agent: AgentRecord,
    scenarios: List[Scenario]
) -> CoverageGapReport:
    context = build_scenario_context(agent)
    
    total_tools = len(agent.tools)
    all_tool_names = {t.name for t in agent.tools}
    exercised_tools: Set[str] = set()

    # Category distribution
    category_counts: Dict[str, int] = {cat.value: 0 for cat in ScenarioCategory}
    
    # Behavioral surfaces
    tested_capabilities: Set[str] = set()
    tested_services: Set[str] = set()
    tested_workflow_nodes: Set[str] = set()
    tested_failure_surfaces: Set[str] = set()
    tested_invariants: Set[str] = set()
    tested_interfaces: Set[str] = set()

    for sc in scenarios:
        category_counts[sc.category.value] = category_counts.get(sc.category.value, 0) + 1
        
        # Tools & Capabilities
        for cap in sc.required_capabilities:
            tested_capabilities.add(cap.upper())
            for t in agent.tools:
                if t.canonical_capability == cap or t.name.lower() == cap.lower():
                    exercised_tools.add(t.name)
                    
        # Services
        for s in sc.required_services:
            tested_services.add(s.lower())
        for fi in sc.fault_injections:
            if hasattr(fi, "target_tool"):
                tested_services.add(fi.target_tool.lower())
            elif isinstance(fi, dict) and fi.get("target_tool"):
                tested_services.add(fi["target_tool"].lower())
            
        # Workflow nodes
        if sc.target_workflow_node:
            tested_workflow_nodes.add(sc.target_workflow_node)
            
        # Failure Surfaces & Invariants
        if sc.target_failure_surface:
            tested_failure_surfaces.add(sc.target_failure_surface)
        if sc.target_invariant:
            tested_invariants.add(sc.target_invariant)
            
        # Interface
        if sc.interface_type:
            tested_interfaces.add(sc.interface_type.upper())

    if not scenarios:
        category_coverage = {cat.value: 0.0 for cat in ScenarioCategory}
        gaps = ["Interface contract has not been exercised by any test scenario."]
        if agent.tools:
            gaps.append(f"{len(agent.tools)} user tool(s) never exercised: {', '.join(t.name for t in agent.tools)}")
        if context.framework_tools:
            gaps.append(f"{len(context.framework_tools)} framework tool(s) never exercised: {', '.join(context.framework_tools)}")
        if context.workflow_nodes:
            gaps.append(f"{len(context.workflow_nodes)} workflow node(s) never targeted: {', '.join(context.workflow_nodes)}")
        if context.external_services:
            gaps.append(f"{len(context.external_services)} external service(s) never tested: {', '.join(context.external_services)}")
        for cat in ScenarioCategory:
            gaps.append(f"Low test depth in '{cat.value.upper()}' category (0.0% coverage)")

        return CoverageGapReport(
            total_tools=total_tools,
            exercised_tools=0,
            unexercised_tools=list(all_tool_names),
            interface_coverage_pct=0.0,
            workflow_node_coverage_pct=0.0,
            capability_coverage_pct=0.0,
            service_coverage_pct=0.0,
            failure_surface_coverage_pct=0.0,
            invariant_coverage_pct=0.0,
            category_coverage=category_coverage,
            overall_coverage_pct=0.0,
            gaps_detected=gaps
        )

    # 1. Tool Coverage (User-defined + Framework-provided tools)
    all_known_tools = set(all_tool_names).union(set(context.framework_tools or []))
    for sc in scenarios:
        for fi in sc.fault_injections:
            if hasattr(fi, "target_tool") and fi.target_tool in all_known_tools:
                exercised_tools.add(fi.target_tool)
    unexercised_tools = list(all_known_tools - exercised_tools)
    total_tools_count = len(all_known_tools)
    tool_cov = round((len(exercised_tools) / total_tools_count) * 100.0, 1) if total_tools_count > 0 else 100.0

    # 2. Category coverage percentages (relative to balanced target depth of 1 scenario per category)
    category_coverage = {
        cat: min(100.0, round((count / 1.0) * 100.0, 1))
        for cat, count in category_counts.items()
    }
    category_avg = round(sum(category_coverage.values()) / max(1, len(category_coverage)), 1)

    # 3. Workflow node coverage (relative to actual workflow nodes)
    workflow_nodes = context.workflow_nodes
    workflow_node_cov = 100.0
    if workflow_nodes:
        exercised_nodes = [node for node in workflow_nodes if node in tested_workflow_nodes]
        workflow_node_cov = round((len(exercised_nodes) / len(workflow_nodes)) * 100.0, 1)

    # 4. External service coverage (relative to actual detected services)
    external_services = context.external_services
    service_cov = 100.0
    if external_services:
        exercised_services = [s for s in external_services if s.lower() in tested_services]
        service_cov = round((len(exercised_services) / len(external_services)) * 100.0, 1)

    # 5. Capability coverage (relative to actual agent capabilities)
    all_caps = set(context.capabilities or [])
    if all_caps:
        matching_caps = {c.upper() for c in tested_capabilities if c.upper() in {ac.upper() for ac in all_caps}}
        cap_cov = round((len(matching_caps) / len(all_caps)) * 100.0, 1)
    else:
        cap_cov = 100.0

    # 6. Failure Surface & Invariant Coverage (relative to actual discovered surfaces)
    all_failure_surfaces = set(context.failure_surfaces or [])
    if all_failure_surfaces:
        matching_fs = {fs for fs in tested_failure_surfaces if fs in all_failure_surfaces}
        failure_cov = round((len(matching_fs) / len(all_failure_surfaces)) * 100.0, 1)
    else:
        failure_cov = 100.0 if tested_failure_surfaces else 100.0

    all_invariants = set(context.constitution.get("never_rules", []) + context.constitution.get("always_rules", []))
    if all_invariants:
        matching_inv = {inv for inv in tested_invariants if inv in all_invariants}
        invariant_cov = round((len(matching_inv) / len(all_invariants)) * 100.0, 1)
    else:
        invariant_cov = 100.0 if tested_invariants else 100.0

    # 7. Interface coverage
    interface_cov = 100.0 if len(tested_interfaces) > 0 else 0.0

    # Composite overall coverage score
    overall_pct = (
        tool_cov * 0.2 +
        category_avg * 0.2 +
        cap_cov * 0.15 +
        interface_cov * 0.15 +
        workflow_node_cov * 0.15 +
        service_cov * 0.15
    )
    overall_pct = round(overall_pct, 1)

    gaps: List[str] = []
    if unexercised_tools:
        gaps.append(f"{len(unexercised_tools)} tool(s) never exercised in test suite: {', '.join(unexercised_tools)}")

    if not tested_interfaces:
        gaps.append("Interface contract has not been exercised by any test scenario.")

    if workflow_nodes:
        unexercised_nodes = [node for node in workflow_nodes if node not in tested_workflow_nodes]
        if unexercised_nodes:
            gaps.append(f"{len(unexercised_nodes)} workflow node(s) never targeted: {', '.join(unexercised_nodes)}")

    if external_services:
        unexercised_services = [s for s in external_services if s.lower() not in tested_services]
        if unexercised_services:
            gaps.append(f"{len(unexercised_services)} external service(s) never tested: {', '.join(unexercised_services)}")

    for cat, score in category_coverage.items():
        if score < 50.0:
            gaps.append(f"Low test depth in '{cat.upper()}' category ({score}% coverage)")

    return CoverageGapReport(
        total_tools=total_tools,
        exercised_tools=len(exercised_tools),
        unexercised_tools=unexercised_tools,
        interface_coverage_pct=interface_cov,
        workflow_node_coverage_pct=workflow_node_cov,
        capability_coverage_pct=cap_cov,
        service_coverage_pct=service_cov,
        failure_surface_coverage_pct=failure_cov,
        invariant_coverage_pct=invariant_cov,
        category_coverage=category_coverage,
        overall_coverage_pct=min(100.0, max(0.0, overall_pct)),
        gaps_detected=gaps
    )
