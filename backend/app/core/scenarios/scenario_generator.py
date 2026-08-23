"""
Scenario Generation Engine with Interface Contract & Fault Injection Mapping.
"""

from __future__ import annotations

import json
import uuid
import hashlib
import logging
from typing import Any, Dict, List
from app.models.agent import AgentRecord
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    FaultInjection,
    ScenarioAssertion,
    StrategyPlan,
    ScenarioPlan,
    ScenarioPlanItem,
    ScenarioGenerationRequest
)
from app.core.scenarios.strategy_planner import build_deterministic_scenario_plan
from app.core.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def _compute_scenario_fingerprint(sc: Scenario) -> str:
    """Computes a canonical deterministic hash for deduplication based strictly on invocation, inputs, targets, and assertions."""
    payload = {
        "interface": sc.interface_type,
        "invocation": sc.invocation,
        "artifacts": [{"path": a.get("path"), "content": a.get("content")} for a in sc.input_artifacts if isinstance(a, dict)],
        "inputs": sc.input_values,
        "target_failure_surface": sc.target_failure_surface,
        "target_invariant": sc.target_invariant,
        "environment": sc.environment_conditions,
        "faults": [{"tool": f.target_tool, "type": f.fault_type} for f in sc.fault_injections],
        "assertions": [{"type": a.assertion_type, "target": a.target, "expected": str(a.expected_value)} for a in sc.assertions],
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def deduplicate_scenarios(scenarios: List[Scenario], threshold: float = 0.88) -> List[Scenario]:
    """Deduplicates scenarios based on fingerprint and purpose similarity."""
    seen_fingerprints = set()
    unique_scenarios = []
    for sc in scenarios:
        fp = _compute_scenario_fingerprint(sc)
        purpose_key = sc.purpose.strip().lower()
        key = (fp, purpose_key)
        if key not in seen_fingerprints:
            seen_fingerprints.add(key)
            unique_scenarios.append(sc)
    return unique_scenarios



async def generate_scenarios_for_agent(
    agent: AgentRecord,
    strategy: Optional[StrategyPlan] = None,
    llm: Optional[LLMProvider] = None,
    scenario_plan: Optional[ScenarioPlan] = None,
    request: Optional[ScenarioGenerationRequest] = None
) -> List[Scenario]:
    """Generates concrete 5-layer test scenarios from deterministic ScenarioPlan items using batch LLM intelligence."""
    from app.core.llm.gemini_provider import GeminiProvider
    if llm is None:
        llm = GeminiProvider()

    # 1. Deterministic Planning First
    if scenario_plan is None:
        scenario_plan = build_deterministic_scenario_plan(agent, request)

    manifest = agent.runtime_manifest or {}
    entrypoint = manifest.get("entrypoint", "main.py")
    interface_type = "CLI" if entrypoint.endswith(".py") and not agent.tools else ("CHAT" if agent.tools else "UNKNOWN")

    # 2. Package Structured Evidence for LLM
    evidence_pack: Dict[str, Any] = {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "domain": agent.domain,
        "description": agent.description,
        "interface": {
            "type": interface_type,
            "entrypoint": entrypoint,
            "runtime_manifest": manifest,
        },
        "capabilities": [t.canonical_capability for t in agent.tools if t.canonical_capability],
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters_schema": t.parameters_schema,
                "canonical_capability": t.canonical_capability,
            }
            for t in agent.tools
        ],
        "dependencies": [
            {"id": d.id, "name": d.name, "type": d.type, "required": d.required}
            for d in agent.dependencies
        ],
        "constitution": {
            "goals": agent.constitution.goals,
            "never_rules": agent.constitution.never_rules,
            "always_rules": agent.constitution.always_rules,
        },
        "user_test_request": request.user_instructions if request else None,
    }

    plan_dict: Dict[str, Any] = {
        "plan_id": scenario_plan.plan_id,
        "total_targets": scenario_plan.total_target,
        "plan_items": [item.dict() for item in scenario_plan.plan_items]
    }

    # 3. Call LLM in One Batch
    try:
        raw_scenarios = await llm.generate_scenarios(evidence_pack, plan_dict)
    except Exception as e:
        logger.warning(f"Gemini scenario batch generation failed: {e}")
        return []

    scenarios: List[Scenario] = []
    seen_fingerprints = set(request.existing_scenario_fingerprints if request else [])

    # 4. Parse into 5-Layer Scenario Specifications
    for idx, raw in enumerate(raw_scenarios):
        try:
            cat_str = str(raw.get("category", "normal")).lower()
            try:
                category = ScenarioCategory(cat_str)
            except ValueError:
                category = ScenarioCategory.NORMAL

            sc_id = f"SC-{category.value[:3].upper()}-{uuid.uuid4().hex[:6]}"
            plan_item_id = raw.get("scenario_plan_id") or (
                scenario_plan.plan_items[idx % len(scenario_plan.plan_items)].plan_id
                if scenario_plan.plan_items else None
            )

            # Fault Injections
            faults: List[FaultInjection] = []
            for f in raw.get("fault_injections", []):
                if isinstance(f, dict) and f.get("target_tool"):
                    faults.append(FaultInjection(
                        target_tool=f["target_tool"],
                        fault_type=f.get("fault_type", "timeout"),
                        occurrence=f.get("occurrence", 1),
                        parameters=f.get("parameters", {})
                    ))

            # Typed Assertions
            assertions: List[ScenarioAssertion] = []
            for a in raw.get("assertions", []):
                if isinstance(a, dict) and (a.get("assertion_type") or a.get("type")):
                    atype = a.get("assertion_type") or a.get("type")
                    assertions.append(ScenarioAssertion(
                        assertion_type=str(atype),
                        target=a.get("target", a.get("expected", "")),
                        expected_value=a.get("expected_value", a.get("expected")),
                        description=a.get("description", f"Verifies {atype}")
                    ))

            raw_interface = str(raw.get("interface_type", interface_type)).upper()
            invocation = raw.get("invocation", {})
            input_artifacts = raw.get("input_artifacts", [])
            user_messages = raw.get("user_messages", [])
            if isinstance(user_messages, str):
                user_messages = [user_messages]
            elif not isinstance(user_messages, list):
                user_messages = []

            # Default CLI invocation fallback
            if raw_interface == "CLI" and not invocation:
                invocation = {
                    "type": "command",
                    "executable": "python",
                    "arguments": [entrypoint],
                    "command": f"python {entrypoint}"
                }

            # Expected Behavior Object
            raw_exp = raw.get("expected_behavior", {})
            expected_behavior = raw_exp if isinstance(raw_exp, dict) else {"summary": str(raw_exp)}

            # Build 5-Layer Scenario
            scenario = Scenario(
                id=sc_id,
                agent_id=agent.id,
                agent_version_id=agent.version_label,
                version=1,
                title=raw.get("title", f"{category.value.title()} Test"),
                category=category,
                status="GENERATED",
                purpose=raw.get("purpose", f"Evaluate agent behavior under {category.value} conditions."),
                target_failure_surface=raw.get("target_failure_surface"),
                target_invariant=raw.get("target_invariant"),
                target_workflow_node=raw.get("target_workflow_node"),
                rationale=raw.get("rationale", f"Validates {category.value} resilience for {agent.name}."),
                interface_type=raw_interface,
                invocation=invocation,
                input_artifacts=input_artifacts if isinstance(input_artifacts, list) else [],
                input_values=raw.get("input_values", {}),
                initial_state=raw.get("initial_state", {}),
                user_messages=user_messages,
                required_capabilities=raw.get("required_capabilities", []),
                required_services=raw.get("required_services", []),
                fault_injections=faults,
                safety_constraints=raw.get("safety_constraints", agent.constitution.never_rules),
                execution_limits=raw.get("execution_limits", {"timeout_seconds": 30}),
                expected_behavior=expected_behavior,
                assertions=assertions,
                provenance={
                    "generated_by": "gemini",
                    "model": getattr(llm, "model_name", "gemini-2.5-flash"),
                    "prompt_version": "v2",
                    "scenario_plan_id": plan_item_id,
                    "behavior_profile_id": request.behavior_profile_id if request else None,
                },
                critic_status="PENDING",
                validation_status="VALIDATED"
            )

            # Deduplicate by deterministic fingerprint
            fp = _compute_scenario_fingerprint(scenario)
            scenario.fingerprint = fp
            if fp not in seen_fingerprints:
                seen_fingerprints.add(fp)
                scenarios.append(scenario)

        except Exception as e:
            logger.debug(f"Skipping malformed scenario object: {e}")
            continue

    return scenarios

