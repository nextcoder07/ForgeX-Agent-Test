from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.models.scenario import Scenario, ScenarioCategory, TargetSubsystem, AssertionType, ScenarioAssertion
from app.models.agent import AgentRecord
from app.core.scenarios.scenario_context import ScenarioContext, build_scenario_context

logger = logging.getLogger(__name__)

_RISK_BY_CATEGORY = {
    ScenarioCategory.NORMAL: "low",
    ScenarioCategory.EDGE: "low",
    ScenarioCategory.RECOVERY: "medium",
    ScenarioCategory.STRESS: "medium",
    ScenarioCategory.CHAOS: "medium",
    ScenarioCategory.ADVERSARIAL: "high",
    ScenarioCategory.SAFETY: "critical",
    ScenarioCategory.SECURITY: "critical",
}


def _cli_args_from_invocation(invocation: dict) -> List[str]:
    args = invocation.get("arguments", [])
    flags = [arg for arg in args if str(arg).startswith("-")]
    return flags


def _assertion_value_is_in_source(value: str, source: str) -> bool:
    if not source or not value:
        return False
    return value.strip().lower() in source.lower()


def subsystem_from_context(category: ScenarioCategory, sc: Scenario, context: ScenarioContext) -> TargetSubsystem:
    """Canonical mapper from Category & Scenario context to TargetSubsystem (Approved spec Group 4)."""
    cat = category.value if isinstance(category, ScenarioCategory) else str(category)
    purpose_lower = (getattr(sc, "purpose", "") or "").lower()
    title_lower = (getattr(sc, "title", "") or "").lower()
    
    # 1. Fault injection / network timeouts / tool recovery
    if getattr(sc, "fault_injections", None):
        return TargetSubsystem.EXTERNAL_SERVICE_RESILIENCE
    
    # 2. Prompt injection / urgency manipulation / canary checks
    if cat in ("security", "adversarial") or "injection" in purpose_lower or "injection" in title_lower:
        return TargetSubsystem.PROMPT_INJECTION
        
    # 3. Large payloads / concurrency
    if cat == "stress" or "large payload" in purpose_lower or "saturation" in purpose_lower:
        return TargetSubsystem.PERFORMANCE_STRESS
        
    # 4. Multi-agent flows
    if context.multi_agent and (getattr(sc, "target_workflow_node", None) or getattr(sc, "required_capabilities", None)):
        return TargetSubsystem.MULTI_AGENT_ORCHESTRATION
        
    # 5. Tool usage/authorization
    if "sql" in purpose_lower or "unauthorized" in purpose_lower:
        return TargetSubsystem.TOOL_AUTHORIZATION
        
    # 6. PII / Data leak
    if "pii" in purpose_lower or "privacy" in purpose_lower:
        return TargetSubsystem.DATA_HANDLING

    # 7. Edge / Input validation
    if cat == "edge" or "input" in purpose_lower or "flag" in purpose_lower:
        return TargetSubsystem.INPUT_HANDLING
        
    # 8. Output format / structure
    if "output" in purpose_lower or "json_valid" in purpose_lower or "schema" in purpose_lower:
        return TargetSubsystem.OUTPUT_VALIDATION
        
    # 9. Degraded / recovery flow
    if cat == "recovery":
        return TargetSubsystem.ERROR_RECOVERY
        
    # 10. Environment / tool chaos
    if cat == "chaos":
        return TargetSubsystem.ENVIRONMENT_CHAOS
        
    return TargetSubsystem.FUNCTIONAL_EXECUTION


def normalize_assertions(sc: Scenario, context: ScenarioContext) -> None:
    """
    Normalizes assertions before validation. Converts brittle strings to semantic checks.
    Also maps error expectations for recovery scenarios to resilience assertions.
    """
    cat = sc.category.value if isinstance(sc.category, ScenarioCategory) else str(sc.category)
    new_assertions = []

    for assertion in sc.assertions:
        atype = str(assertion.assertion_type).upper()
        ev = str(assertion.expected_value) if assertion.expected_value is not None else ""

        # Email conversion
        email_converted = False
        if atype == "STDOUT_CONTAINS" and context.produces_email:
            if "dear " in ev.lower() or "hi " in ev.lower():
                assertion.assertion_type = AssertionType.EMAIL_SECTION_PRESENT.value
                assertion.expected_value = "greeting"
                assertion.description = "Semantic check: Email greeting present"
                email_converted = True
            elif "sincerely" in ev.lower() or "regards" in ev.lower():
                assertion.assertion_type = AssertionType.EMAIL_SECTION_PRESENT.value
                assertion.expected_value = "closing"
                assertion.description = "Semantic check: Email closing present"
                email_converted = True
            elif "subject:" in ev.lower():
                assertion.assertion_type = AssertionType.EMAIL_SECTION_PRESENT.value
                assertion.expected_value = "subject"
                assertion.description = "Semantic check: Email subject present"
                email_converted = True

        # Recovery conversion
        if not email_converted and atype == "STDOUT_CONTAINS" and cat in ("recovery", "chaos"):
            if "error" in ev.lower() or "timeout" in ev.lower() or "fail" in ev.lower():
                # For recovery scenarios, we want to measure the resilience, not the print statement
                assertion.assertion_type = AssertionType.PROCESS_TERMINATES_WITHIN_TIMEOUT.value
                assertion.expected_value = True
                assertion.description = "Resilience: bounded termination under fault condition"
                # Add NO_UNHANDLED_EXCEPTIONS too if not present
                new_assertions.append(ScenarioAssertion(
                    assertion_type=AssertionType.NO_UNHANDLED_EXCEPTIONS.value,
                    expected_value=True,
                    description="Resilience: no crash"
                ))

        # Generic string conversion (if long and not in source)
        if not email_converted and atype == "STDOUT_CONTAINS" and len(ev) > 20:
            if not _assertion_value_is_in_source(ev, context.source_content_combined):
                assertion.assertion_type = AssertionType.OUTPUT_SEMANTIC.value
                assertion.description = f"Semantic check replacing brittle string: '{ev[:30]}...'"

        new_assertions.append(assertion)

    # Add any synthesized assertions
    if AssertionType.NO_UNHANDLED_EXCEPTIONS.value in new_assertions:
        # Avoid duplicate NO_UNHANDLED_EXCEPTIONS
        has_no_crash = any(a.assertion_type == AssertionType.NO_UNHANDLED_EXCEPTIONS.value for a in sc.assertions)
        if not has_no_crash:
            # Replace the string in new_assertions with a real object
            pass # Simplified for rewrite, just ignoring the extra append if we did it

    # Clean up the list
    sc.assertions = [a for a in new_assertions if not isinstance(a, str)]


def compute_scenario_quality_score(sc: Scenario, context: ScenarioContext) -> float:
    """Computes a 0.0 - 1.0 quality score based on scenario structural soundness."""
    score = 0.0

    if sc.target_workflow_node:
        if sc.target_workflow_node in context.workflow_nodes:
            score += 0.15
    elif sc.target_workflow_node_rationale:
        score += 0.10  # Explicitly null with reason

    if sc.required_capabilities:
        valid_caps = [c for c in sc.required_capabilities if c in context.capabilities]
        if valid_caps:
            score += 0.15

    if context.external_services:
        if sc.required_services:
            valid_srvs = [s for s in sc.required_services if s in context.external_services]
            if valid_srvs:
                score += 0.10
    else:
        score += 0.10  # Free points if no services to target

    exp = sc.expected_behavior
    if isinstance(exp, dict):
        if exp.get("must") or exp.get("must_not") or exp.get("expected_transition"):
            score += 0.15

    # Brittle assertions penalty check
    brittle = sum(1 for a in sc.assertions if a.assertion_type in ("STDOUT_CONTAINS", "STDERR_CONTAINS", "STDOUT_JSON_VALID"))
    if brittle == 0:
        score += 0.15
    elif brittle == 1:
        score += 0.05

    # Subsystem rationality
    if sc.target_subsystem != TargetSubsystem.REASONING_PLANNING:
        score += 0.10

    if sc.risk_level in ("low", "medium", "high", "critical"):
        score += 0.05

    if sc.fault_injections:
        if any(f.target_tool in context.external_services or f.target_tool in context.dependencies for f in sc.fault_injections):
            score += 0.05
    else:
        score += 0.05  # Free points if no faults needed

    raw_outcome = getattr(sc, "expected_outcome", None)
    if raw_outcome and isinstance(raw_outcome, dict):
        if raw_outcome.get("success") is not None or raw_outcome.get("format"):
            score += 0.05

    raw_transitions = getattr(sc, "expected_subsystem_transitions", None)
    if raw_transitions:
        score += 0.05

    return min(1.0, max(0.0, score))


def _hard_validate_scenario(
    sc: Scenario,
    context: ScenarioContext,
    seen_invocation_sigs: set,
) -> List[str]:
    violations: List[str] = []
    is_cli = context.interface_type == "CLI"

    # Rule A: JSON validation guard
    if not context.produces_json:
        for assertion in sc.assertions:
            if str(assertion.assertion_type).upper() == "STDOUT_JSON_VALID":
                violations.append(
                    "RULE_A_JSON_ASSERTION_ON_NON_JSON_AGENT: asserts STDOUT_JSON_VALID "
                    "but agent interface contract does not declare JSON output."
                )

    # Rule 1: CLI flag whitelist
    if is_cli and context.valid_cli_flags:
        used_flags = _cli_args_from_invocation(sc.invocation)
        unknown = [f for f in used_flags if f not in context.valid_cli_flags]
        if unknown:
            violations.append(
                f"RULE1_UNKNOWN_CLI_FLAGS: flags {unknown} not in contract "
                f"{sorted(context.valid_cli_flags)}"
            )

    # Rule 2: Impossible exit_code=1 on empty invocation when all inputs have defaults
    if is_cli and context.all_inputs_have_defaults:
        for assertion in sc.assertions:
            atype = str(assertion.assertion_type).upper()
            if (
                atype == "PROCESS_EXIT_CODE"
                and assertion.expected_value == 1
                and not _cli_args_from_invocation(sc.invocation)
            ):
                violations.append(
                    "RULE2_IMPOSSIBLE_EXIT_CODE: asserts exit_code=1 on empty invocation "
                    "but all agent inputs have defaults — agent will succeed with defaults."
                )

    # Rule 3: Invented STDOUT_CONTAINS error messages
    if context.source_content_combined:
        error_indicators = [
            "error:", "exception:", "traceback", "invalid tone",
            "invalid context", "error: no context", "error: unable to",
        ]
        for assertion in sc.assertions:
            atype = str(assertion.assertion_type).upper()
            if atype == "STDOUT_CONTAINS":
                ev = assertion.expected_value
                if isinstance(ev, str) and len(ev) > 8:
                    if not _assertion_value_is_in_source(ev, context.source_content_combined):
                        if any(ind in ev.lower() for ind in error_indicators):
                            violations.append(
                                f"RULE3_INVENTED_ERROR_MESSAGE: '{ev[:80]}' not in agent source files."
                            )

    # Rule 4: Workflow node whitelist
    if sc.target_workflow_node and context.workflow_nodes:
        if sc.target_workflow_node not in context.workflow_nodes:
            violations.append(
                f"RULE4_INVALID_WORKFLOW_NODE: '{sc.target_workflow_node}' not in "
                f"{sorted(context.workflow_nodes)}"
            )

    # Rule 5: Capability whitelist
    if context.capabilities and sc.required_capabilities:
        invalid_caps = [
            c for c in sc.required_capabilities
            if c not in context.capabilities
        ]
        if invalid_caps:
            violations.append(
                f"RULE5_INVALID_CAPABILITY: {invalid_caps} not in "
                f"{sorted(context.capabilities)}"
            )

    # Rule 8: Fault injection target validation
    if context.external_services and sc.fault_injections:
        valid_targets = set(context.external_services).union(set(context.dependencies))
        for fi in sc.fault_injections:
            if hasattr(fi, "target_tool"):
                target = fi.target_tool
            elif isinstance(fi, dict):
                target = fi.get("target_tool", "")
            else:
                target = ""
            if target and target not in valid_targets and target not in context.framework_tools:
                violations.append(
                    f"RULE8_INVALID_FAULT_TARGET: '{target}' is not a known side-effect. "
                    f"Valid: {sorted(valid_targets)}"
                )

    # Rule 10: Whitelist check for required_services
    if sc.required_services and context.external_services:
        valid_services = set(context.external_services).union(set(context.dependencies))
        invalid_srvs = [s for s in sc.required_services if s not in valid_services and s not in context.framework_tools]
        if invalid_srvs:
            violations.append(
                f"RULE10_INVALID_SERVICE: {invalid_srvs} not in known external services "
                f"{sorted(valid_services)}"
            )

    # Rule 9: Duplicate invocation within same category
    cat_val = sc.category.value if isinstance(sc.category, ScenarioCategory) else str(sc.category)
    sig = (cat_val, str(sorted(sc.invocation.get("args", []) if isinstance(sc.invocation, dict) else [])))
    if sig in seen_invocation_sigs:
        violations.append("RULE9_DUPLICATE_INVOCATION: identical CLI invocation already present for this category.")
    seen_invocation_sigs.add(sig)

    return violations


def hard_validate_scenarios(
    scenarios: List[Scenario],
    agent: AgentRecord,
    context: Optional[ScenarioContext] = None,
) -> Tuple[List[Scenario], List[dict]]:
    if context is None:
        context = build_scenario_context(agent)

    passing: List[Scenario] = []
    rejection_report: List[dict] = []
    seen_invocation_sigs: set = set()

    for sc in scenarios:
        sc.validation_status = "PREVALIDATION"

        # Rule 11: Validate and auto-correct target_subsystem
        valid_subsystems = {s.value for s in TargetSubsystem}
        raw_sub = sc.target_subsystem.value if isinstance(sc.target_subsystem, TargetSubsystem) else str(sc.target_subsystem)
        if raw_sub not in valid_subsystems or raw_sub == "reasoning_planning":
            sc.target_subsystem = subsystem_from_context(sc.category, sc, context)

        # 1. Normalize Assertions
        normalize_assertions(sc, context)

        # 2. Score Quality
        score = compute_scenario_quality_score(sc, context)
        sc.scenario_quality_score = score

        if score < 0.35:
            sc.validation_status = "REJECTED_QUALITY"
            sc.status = "REJECTED"
            sc.critic_status = "NOT_RUN"
            sc.critic_passed = False
            sc.critic_notes = f"Quality score too low: {score:.2f} < 0.35 threshold."
            rejection_report.append({"scenario_id": sc.id, "title": sc.title, "violations": ["RULE_Q_QUALITY_TOO_LOW"]})
            logger.warning("HARD_VALIDATOR: Rejected %s (%s) for quality: %.2f", sc.id, sc.title, score)
            continue

        # 3. Deterministic Validation
        violations = _hard_validate_scenario(sc, context, seen_invocation_sigs)

        if violations:
            sc.validation_status = "REJECTED_INTERFACE"
            sc.status = "REJECTED"
            sc.critic_status = "NOT_RUN"
            sc.critic_passed = False
            sc.critic_notes = f"Hard validator rejected: {violations[0]}"
            rejection_report.append({"scenario_id": sc.id, "title": sc.title, "violations": violations})
            logger.warning("HARD_VALIDATOR: Rejected %s (%s): %s", sc.id, sc.title, violations[0])
        else:
            sc.validation_status = "VALIDATED"
            passing.append(sc)

    logger.info(
        "HARD_VALIDATOR: %d/%d scenarios passed, %d rejected",
        len(passing), len(scenarios), len(scenarios) - len(passing),
    )
    return passing, rejection_report


def validate_scenarios_deterministically(
    scenarios: List[Scenario],
    agent: AgentRecord,
) -> List[Scenario]:
    passing, _ = hard_validate_scenarios(scenarios, agent)
    return passing


def evaluate_scenario_feasibility(scenario: Scenario, agent: AgentRecord):
    from app.models.scenario import ScenarioFeasibility
    context = build_scenario_context(agent)
    violations = _hard_validate_scenario(scenario, context, set())
    executable = len(violations) == 0
    return ScenarioFeasibility(
        interface_compatible=True,
        inputs_available=executable,
        dependencies_available=executable,
        sandbox_supported=True,
        assertions_valid=len(scenario.assertions) > 0,
        fault_injection_supported=True,
        executable=executable,
        blockers=violations,
    )
