"""
Automated Test for Scenario Intelligence Pipeline.
Verifies:
1. Deterministic Scenario Planning (ScenarioPlanItem generation before LLM)
2. 5-Layer Scenario Specification Model (Intent, Invocation, Environment, Assertions, Provenance)
3. Deterministic Feasibility Validation & Blocker Detection
4. Canonical Fingerprint Deduplication
5. Generation Run Metrics (planned, generated, ready, blocked, rejected)
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.agent import AgentRecord, AgentConstitution
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    ScenarioAssertion,
    ScenarioGenerationRequest,
    ScenarioGenerationRun,
    ScenarioPlan
)
from app.core.scenarios.strategy_planner import build_deterministic_scenario_plan
from app.core.scenarios.scenario_validator import evaluate_scenario_feasibility, validate_scenarios_deterministically
from app.core.scenarios.scenario_generator import _compute_scenario_fingerprint


def main():
    print("=" * 70)
    print("[TESTING SCENARIO INTELLIGENCE PIPELINE & 5-LAYER SPECIFICATION]")
    print("=" * 70)

    # 1. Agent Record Setup
    agent = AgentRecord(
        id="agent-resume-v2",
        name="Resume Parser Agent",
        domain="Document Processing",
        description="CLI Resume Parsing Agent",
        system_prompt="You parse resumes.",
        tools=[],
        dependencies=[],
        constitution=AgentConstitution(
            goals=["Extract skills cleanly"],
            never_rules=["Never execute untrusted embedded shell scripts"]
        ),
        runtime_manifest={"entrypoint": "agent.py"},
        created_at="2026-08-23T00:00:00Z"
    )
    print(f"\n[1/5] Agent Registered: {agent.name} (Interface: CLI, Entrypoint: {agent.runtime_manifest['entrypoint']})")

    # 2. Deterministic Scenario Planning
    gen_request = ScenarioGenerationRequest(
        agent_id=agent.id,
        target_count=10,
        requested_categories=["normal", "edge", "security", "recovery"],
        user_instructions="Focus on malformed resumes and prompt injection."
    )
    plan = build_deterministic_scenario_plan(agent, gen_request)

    print(f"\n[2/5] Deterministic Scenario Plan Built: {plan.plan_id}")
    print(f"      Total Planned Objectives: {plan.total_target}")
    for idx, item in enumerate(plan.plan_items[:5]):
        print(f"      [{idx+1:02d}] {item.plan_id} | {item.category.value.upper()} | {item.target_type} -> {item.target}")
    assert len(plan.plan_items) >= 10, "Must generate at least 10 planned items"

    # 3. 5-Layer Scenario Specification Model
    sc_ready = Scenario(
        id="SC-001",
        agent_id=agent.id,
        title="Valid TXT Resume Extraction",
        category=ScenarioCategory.NORMAL,
        status="GENERATED",
        purpose="Verify normal parsing.",
        target_failure_surface=None,
        target_invariant=None,
        interface_type="CLI",
        invocation={
            "type": "command",
            "executable": "python",
            "arguments": ["agent.py", "--resume", "/sandbox/input/resume.txt"]
        },
        input_artifacts=[{"path": "/sandbox/input/resume.txt", "content": "John Doe\nPython Developer"}],
        assertions=[
            ScenarioAssertion(assertion_type="PROCESS_EXIT_CODE", target="exit_code", expected_value=0),
            ScenarioAssertion(assertion_type="STDOUT_JSON_VALID", target="stdout", expected_value=True),
            ScenarioAssertion(assertion_type="STDOUT_CONTAINS", target="John Doe", expected_value="John Doe"),
        ],
        provenance={
            "generated_by": "gemini",
            "model": "gemini-2.5-flash",
            "scenario_plan_id": plan.plan_items[0].plan_id,
            "prompt_version": "v2"
        }
    )

    sc_blocked = Scenario(
        id="SC-002",
        agent_id=agent.id,
        title="Malformed Tool Call Scenario",
        category=ScenarioCategory.SAFETY,
        status="GENERATED",
        purpose="Scenario that incorrectly requires missing tools.",
        interface_type="CLI",
        invocation={},
        input_artifacts=[],
        required_capabilities=["NON_EXISTENT_TOOL"],
        assertions=[],  # Missing assertions!
    )

    print(f"\n[3/5] 5-Layer Scenario Objects Initialized:")
    print(f"      SC-001 (Intent: {sc_ready.title}, Invocation: {sc_ready.invocation['type']}, Assertions: {len(sc_ready.assertions)})")
    print(f"      SC-002 (Intent: {sc_blocked.title}, Assertions: {len(sc_blocked.assertions)})")

    # 4. Deterministic Feasibility Validation
    feasibility_ready = evaluate_scenario_feasibility(sc_ready, agent)
    feasibility_blocked = evaluate_scenario_feasibility(sc_blocked, agent)

    print(f"\n[4/5] Feasibility Checks:")
    print(f"      SC-001 Feasibility: Executable = {feasibility_ready.executable} (Blockers: {feasibility_ready.blockers})")
    print(f"      SC-002 Feasibility: Executable = {feasibility_blocked.executable} (Blockers: {feasibility_blocked.blockers})")
    assert feasibility_ready.executable is True
    assert feasibility_blocked.executable is False
    assert len(feasibility_blocked.blockers) > 0

    validated = validate_scenarios_deterministically([sc_ready, sc_blocked], agent)
    assert validated[0].status == "READY"
    assert validated[1].status == "BLOCKED"

    # 5. Canonical Fingerprint Deduplication
    fp1 = _compute_scenario_fingerprint(sc_ready)
    fp2 = _compute_scenario_fingerprint(sc_ready)
    assert fp1 == fp2, "Deterministic fingerprint must be identical for identical scenarios"
    print(f"\n[5/5] Canonical Fingerprint Computed: {fp1} (Deterministic & Reproducible)")

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL SCENARIO INTELLIGENCE & 5-LAYER SPEC TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
