"""
Scenario Validator for Member 1.
Validates scenario definitions against agent test specifications and schemas.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List
from app.models.agent_test_spec import AgentTestSpecification, ScenarioDefinition

VALID_CATEGORIES = [
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

VALID_RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

def validate_scenarios(
    scenarios: List[ScenarioDefinition],
    spec: AgentTestSpecification
) -> Dict[str, Any]:
    """
    Validates a list of ScenarioDefinition objects against the AgentTestSpecification.
    Checks: required fields, categories, risk levels, capabilities, tools, input structure,
    and duplicate scenario IDs/inputs.
    """
    errors: List[Dict[str, Any]] = []
    seen_ids = set()
    seen_sigs = set()

    capabilities_ids = {c.capability_id.upper() for c in spec.capabilities}
    agent_tools = {t.name.lower() for t in spec.tools}

    for idx, sc in enumerate(scenarios):
        sc_desc = sc.scenario_id or f"Index {idx}"
        
        # 1. Required fields
        if not sc.scenario_id:
            errors.append({
                "scenario_id": sc_desc,
                "field": "scenario_id",
                "message": "Missing required field: scenario_id"
            })
        if not sc.capability_id:
            errors.append({
                "scenario_id": sc_desc,
                "field": "capability_id",
                "message": "Missing required field: capability_id"
            })
        if not sc.category:
            errors.append({
                "scenario_id": sc_desc,
                "field": "category",
                "message": "Missing required field: category"
            })
        if not sc.expected_behavior:
            errors.append({
                "scenario_id": sc_desc,
                "field": "expected_behavior",
                "message": "Missing expected_behavior description"
            })

        # 2. Duplicate Scenario ID check
        if sc.scenario_id:
            if sc.scenario_id in seen_ids:
                errors.append({
                    "scenario_id": sc.scenario_id,
                    "field": "scenario_id",
                    "message": f"Duplicate scenario_id detected: {sc.scenario_id}"
                })
            seen_ids.add(sc.scenario_id)

        # 3. Valid Category Check
        if sc.category:
            cat_upper = sc.category.upper()
            if cat_upper not in VALID_CATEGORIES:
                errors.append({
                    "scenario_id": sc.scenario_id,
                    "field": "category",
                    "message": f"Invalid category '{sc.category}'. Must be one of: {', '.join(VALID_CATEGORIES)}"
                })

        # 4. Valid Risk Level Check
        if sc.risk_level:
            risk_upper = sc.risk_level.upper()
            if risk_upper not in VALID_RISK_LEVELS:
                errors.append({
                    "scenario_id": sc.scenario_id,
                    "field": "risk_level",
                    "message": f"Invalid risk_level '{sc.risk_level}'. Must be one of: {', '.join(VALID_RISK_LEVELS)}"
                })

        # 5. Referenced Capability Exists
        if sc.capability_id and sc.capability_id.upper() not in capabilities_ids and sc.capability_id != "GENERIC":
            errors.append({
                "scenario_id": sc.scenario_id,
                "field": "capability_id",
                "message": f"Referenced capability '{sc.capability_id}' does not exist in AgentTestSpecification."
            })

        # 6. Referenced Tools Exist
        for tool in sc.required_tools:
            if tool.lower() not in agent_tools:
                errors.append({
                    "scenario_id": sc.scenario_id,
                    "field": "required_tools",
                    "message": f"Referenced tool '{tool}' does not exist in agent tools registry."
                })

        # 7. Check Duplicate Scenario Signature (Category + Input message check)
        input_str = json.dumps(sc.input, sort_keys=True)
        sig = (sc.capability_id, sc.category.upper() if sc.category else "", input_str)
        if sig in seen_sigs:
            errors.append({
                "scenario_id": sc.scenario_id,
                "field": "input",
                "message": "Duplicate scenario payload and category detected."
            })
        seen_sigs.add(sig)

        # 8. Check Input structure matches parameters (Warnings/Info for missing variables)
        if sc.capability_id and sc.capability_id.upper() in capabilities_ids:
            cap = next(c for c in spec.capabilities if c.capability_id.upper() == sc.capability_id.upper())
            # For each input argument required by related tools, verify if it is referenced in input fields 
            # (only when not invalid/missing test category)
            is_valid_input_test = sc.category.upper() not in ["MISSING_INPUT", "INVALID_INPUT"]
            if is_valid_input_test and cap.inputs:
                for param in cap.inputs.keys():
                    if param not in sc.input and param != "self":
                        # Log warning error if missing standard parameters for standard happy-path tests
                        if sc.category.upper() in ["NORMAL", "RETRY/RECOVERY"]:
                            errors.append({
                                "scenario_id": sc.scenario_id,
                                "field": "input",
                                "message": f"Warning: Parameter '{param}' is defined in capability inputs but missing in scenario input."
                            })

    return {
        "is_valid": len(errors) == 0,
        "errors_count": len(errors),
        "errors": errors
    }
