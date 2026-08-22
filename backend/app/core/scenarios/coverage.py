"""
Scenario & Capability Coverage Analyzer for Member 1.
Computes metrics to identify testing gaps in capabilities, tools, categories, and risks.
"""
from __future__ import annotations

import re
from typing import List, Dict, Set
from app.models.agent_test_spec import AgentTestSpecification, ScenarioDefinition, CoverageReport

TARGET_CATEGORIES = [
    "NORMAL",
    "EDGE_CASE",
    "BOUNDARY",
    "INVALID_INPUT",
    "MISSING_INPUT",
    "LARGE_INPUT",
    "TOOL_FAILURE",
    "TIMEOUT",
    "RETRY/RECOVERY",
    "ADVERSARIAL",
    "PROMPT_INJECTION",
    "CONFLICTING_INSTRUCTION"
]

STANDARD_FAILURE_MODES = ["TIMEOUT", "HTTP_500", "SCHEMA_VIOLATION", "RETRY_SUCCESS"]

def calculate_coverage(
    spec: AgentTestSpecification,
    scenarios: List[ScenarioDefinition]
) -> CoverageReport:
    """
    Computes coverage statistics mapping test scenarios against agent specs.
    Calculates capability, category, tool, risk, and failure mode coverage rates.
    """
    # 1. Capability Coverage
    all_caps = {c.capability_id.upper() for c in spec.capabilities}
    covered_caps: Set[str] = set()
    scenarios_per_cap: Dict[str, int] = {c: 0 for c in all_caps}
    
    for sc in scenarios:
        cap_id = sc.capability_id.upper()
        if cap_id in all_caps:
            covered_caps.add(cap_id)
            scenarios_per_cap[cap_id] = scenarios_per_cap.get(cap_id, 0) + 1
        elif sc.capability_id == "GENERIC":
            scenarios_per_cap["GENERIC"] = scenarios_per_cap.get("GENERIC", 0) + 1
            
    untested_caps = list(all_caps - covered_caps)
    cap_cov_pct = round((len(covered_caps) / len(all_caps)) * 100.0, 1) if all_caps else 100.0

    # 2. Category Coverage
    covered_cats: Set[str] = set()
    scenarios_per_cat: Dict[str, int] = {cat: 0 for cat in TARGET_CATEGORIES}
    
    for sc in scenarios:
        cat_upper = sc.category.upper()
        if cat_upper in TARGET_CATEGORIES:
            covered_cats.add(cat_upper)
            scenarios_per_cat[cat_upper] = scenarios_per_cat.get(cat_upper, 0) + 1
            
    missing_cats = list(set(TARGET_CATEGORIES) - covered_cats)
    cat_cov_pct = round((len(covered_cats) / len(TARGET_CATEGORIES)) * 100.0, 1)

    # 3. Tool Coverage
    all_tools = {t.name.lower() for t in spec.tools}
    covered_tools: Set[str] = set()
    
    for sc in scenarios:
        for tool in sc.required_tools:
            tool_lower = tool.lower()
            if tool_lower in all_tools:
                covered_tools.add(tool_lower)
                
    untested_tools = list(all_tools - covered_tools)
    # Convert back to actual casing
    actual_untested_tools = []
    for t in spec.tools:
        if t.name.lower() in untested_tools:
            actual_untested_tools.append(t.name)
            
    tool_cov_pct = round((len(covered_tools) / len(all_tools)) * 100.0, 1) if all_tools else 100.0

    # 4. Risk Coverage
    covered_risks: Set[str] = set()
    for risk in spec.risks:
        risk_lower = risk.lower()
        # Clean risk from basic punctuation
        risk_cleaned = re.sub(r'[^\w\s]', '', risk_lower)
        keywords = [w for w in risk_cleaned.split() if len(w) > 3]
        
        for sc in scenarios:
            sc_text = f"{sc.description} {sc.expected_behavior} {sc.category}".lower()
            # Match if the risk name is mentioned, or if several key risk terms overlap in the scenario description
            if risk_lower in sc_text:
                covered_risks.add(risk)
                break
            elif keywords and sum(1 for w in keywords if w in sc_text) >= max(1, len(keywords) // 2):
                covered_risks.add(risk)
                break
                
    untested_risks = list(set(spec.risks) - covered_risks)
    risk_cov_pct = round((len(covered_risks) / len(spec.risks)) * 100.0, 1) if spec.risks else 100.0

    # 5. Failure Mode Coverage
    covered_failures: Set[str] = set()
    for sc in scenarios:
        if sc.failure_mode_to_test:
            fail_upper = sc.failure_mode_to_test.upper()
            if fail_upper in STANDARD_FAILURE_MODES:
                covered_failures.add(fail_upper)
                
    untested_failures = list(set(STANDARD_FAILURE_MODES) - covered_failures)
    failure_cov_pct = round((len(covered_failures) / len(STANDARD_FAILURE_MODES)) * 100.0, 1)

    return CoverageReport(
        capability_coverage=cap_cov_pct,
        category_coverage=cat_cov_pct,
        tool_coverage=tool_cov_pct,
        risk_coverage=risk_cov_pct,
        failure_mode_coverage=failure_cov_pct,
        untested_capabilities=untested_caps,
        untested_tools=actual_untested_tools,
        untested_risks=untested_risks,
        untested_failure_modes=untested_failures,
        missing_categories=missing_cats,
        scenarios_per_capability=scenarios_per_cap,
        scenarios_per_category=scenarios_per_cat
    )
