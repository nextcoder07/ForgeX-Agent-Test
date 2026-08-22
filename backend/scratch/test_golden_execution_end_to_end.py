"""
Golden End-to-End Execution Pipeline Test.
Proves the complete unified pipeline:
Agent Artifact -> BehaviorProfile & Contracts -> Deterministic Test Plan -> 
5-Layer Scenario Specification -> Scenario Feasibility (READY) -> 
ScenarioExecutionContract -> Direct Sandbox Runner -> Causal Trajectory -> 
Deterministic Evaluation -> Scorecard & Persisted Result.
"""

import os
import sys
import json
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.agent import AgentRecord, AgentConstitution
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    ScenarioAssertion,
    ScenarioGenerationRequest,
    ScenarioExecutionContract
)
from app.core.scenarios.strategy_planner import build_deterministic_scenario_plan
from app.core.scenarios.scenario_validator import evaluate_scenario_feasibility, validate_scenarios_deterministically
from app.core.execution.contract_compiler import compile_scenario_execution_contract
from app.core.sandbox.subprocess_runner import run_scenario_in_subprocess
from app.core.dependencies.tool_gateway import ToolGateway
from app.core.evaluation.rule_evaluator import RuleEvaluator
from app.models.execution import ExecutionStep

RESUME_PARSER_CODE = """
import sys
import json
import os

def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--resume":
        print(json.dumps({"error": "Usage: python agent.py --resume <file>"}))
        sys.exit(1)
        
    resume_path = sys.argv[2]
    if not os.path.exists(resume_path):
        print(json.dumps({"error": f"File not found: {resume_path}"}))
        sys.exit(2)
        
    with open(resume_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = [l.strip() for l in content.split("\\n") if l.strip()]
    candidate_name = lines[0] if lines else "Unknown"
    skills = []
    for l in lines:
        if "skills:" in l.lower():
            skills = [s.strip() for s in l.split(":", 1)[1].split(",")]
            
    output = {
        "status": "PARSED_SUCCESS",
        "candidate": candidate_name,
        "skills": skills,
        "raw_lines": len(lines)
    }
    print(json.dumps(output, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
"""


def main():
    print("=" * 70)
    print("[GOLDEN EXECUTION PIPELINE TEST: RESUME PARSER AGENT]")
    print("=" * 70)

    # 1. Agent Definition
    agent = AgentRecord(
        id="agent-resume-golden-v1",
        name="Resume Parser CLI Agent",
        domain="Document Processing",
        description="Autonomous CLI agent parsing resumes into structured JSON.",
        system_prompt="You are a CLI parser.",
        tools=[],  # 0 tools — workflow agent
        dependencies=[],
        constitution=AgentConstitution(goals=["Extract skills accurately"]),
        runtime_manifest={"entrypoint": "agent.py"},
        created_at="2026-08-23T00:00:00Z"
    )
    print(f"\n[1/7] Agent Loaded: {agent.name} (Entrypoint: {agent.runtime_manifest['entrypoint']})")

    # 2. Deterministic Test Plan
    gen_req = ScenarioGenerationRequest(
        agent_id=agent.id,
        target_count=5,
        user_instructions="Verify valid resume parsing with exit code 0."
    )
    plan = build_deterministic_scenario_plan(agent, gen_req)
    print(f"\n[2/7] Deterministic Plan: {plan.plan_id} ({len(plan.plan_items)} target objectives)")
    print(f"      Objective 1: [{plan.plan_items[0].category.value.upper()}] {plan.plan_items[0].target}")

    # 3. 5-Layer Scenario Specification
    scenario = Scenario(
        id="SC-GOLDEN-001",
        agent_id=agent.id,
        agent_version_id="v1.0",
        title="Parse Standard TXT Resume",
        category=ScenarioCategory.NORMAL,
        status="GENERATED",
        purpose="Verify that the agent extracts candidate skills and exits with code 0.",
        interface_type="CLI",
        invocation={
            "type": "command",
            "executable": "python",
            "arguments": ["--resume", "input/resume.txt"],
            "command": "python agent.py --resume input/resume.txt"
        },
        input_artifacts=[
            {
                "path": "input/resume.txt",
                "content": "Alex Mercer\nStaff Distributed Backend Architect\nSkills: Go, Python, Kubernetes, Kafka\nExperience: 10 years in fintech infrastructure."
            }
        ],
        expected_behavior={"exit_code": 0, "status": "PARSED_SUCCESS"},
        assertions=[
            ScenarioAssertion(assertion_type="PROCESS_EXIT_CODE", target="exit_code", expected_value=0),
            ScenarioAssertion(assertion_type="STDOUT_JSON_VALID", target="stdout", expected_value=True),
            ScenarioAssertion(assertion_type="STDOUT_CONTAINS", target="Alex Mercer", expected_value="Alex Mercer"),
            ScenarioAssertion(assertion_type="STDOUT_CONTAINS", target="Kubernetes", expected_value="Kubernetes"),
        ],
        provenance={
            "generated_by": "deterministic",
            "model": None,
            "scenario_plan_id": plan.plan_items[0].plan_id,
            "prompt_version": "v2"
        }
    )
    print(f"\n[3/7] 5-Layer Scenario Specification Constructed: {scenario.id} ({scenario.title})")
    print(f"      Invocation: {scenario.invocation['command']}")
    print(f"      Assertions: {[a.assertion_type for a in scenario.assertions]}")

    # 4. Feasibility Evaluation (READY)
    feasibility = evaluate_scenario_feasibility(scenario, agent)
    print(f"\n[4/7] Feasibility Check: Executable = {feasibility.executable}")
    assert feasibility.executable is True, f"Scenario must be feasible! Blockers: {feasibility.blockers}"
    scenario.status = "READY"
    scenario.validation_status = "VALIDATED"

    # 5. Compile Scenario Execution Contract
    contract = compile_scenario_execution_contract(
        scenario=scenario,
        agent=agent,
        working_directory="/sandbox",
        execution_mode="subprocess",
        model_binding={"original_model": "none", "executed_model": "subprocess_local", "model_substitution": False}
    )
    print(f"\n[5/7] Scenario Execution Contract Compiled:")
    print(f"      Command List: {contract.command}")
    print(f"      Staged Artifacts: {[a['relative_path'] for a in contract.staged_artifacts]}")
    print(f"      Execution Mode: {contract.execution_mode} (Model: {contract.model_binding['executed_model']})")

    # 6. Direct Sandbox Runner Execution (using the compiled contract)
    gateway = ToolGateway(tools=agent.tools)
    print(f"\n[6/7] Executing in Isolated Sandbox...")
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content=RESUME_PARSER_CODE,
        gateway=gateway,
        timeout_seconds=contract.timeout_seconds
    )
    print(f"      Sandbox Completed in {trace.total_latency_ms} ms")
    print("\n      --- Real Causal Trajectory Recorded ---")
    for idx, ev in enumerate(trace.events):
        print(f"      [{idx+1:02d}] {ev.timestamp} | {ev.role.upper()}: {ev.content[:100]}")

    # 7. Deterministic Assertion Evaluation
    steps = []
    for idx, ev in enumerate(trace.events):
        event_type = "UNKNOWN"
        output_data = {}
        if "STDOUT_CHUNK:" in ev.content:
            event_type = "STDOUT_CHUNK"
            output_data["stdout"] = ev.content.replace("STDOUT_CHUNK:", "").strip()
        elif "PROCESS_EXITED:" in ev.content:
            event_type = "PROCESS_EXITED"
            output_data["exit_code"] = int(ev.content.split()[-1])

        steps.append(ExecutionStep(
            id=f"step-{idx}",
            execution_session_id=trace.id,
            step_number=idx + 1,
            event_type=event_type,
            actor=ev.role,
            output_data=output_data,
            metadata={"content": ev.content},
            created_at=ev.timestamp
        ))

    evaluator = RuleEvaluator()
    evidences = evaluator.evaluate_rules(scenario, steps)

    print(f"\n[7/7] Evaluator Results ({len(evidences)} rules tested):")
    all_passed = True
    for ev in evidences:
        icon = "[PASS]" if ev.passed else "[FAIL]"
        if not ev.passed:
            all_passed = False
        print(f"      {icon} [{ev.rule_name}] Expected: {ev.expected} | Actual: {ev.actual}")

    print("\n" + "=" * 70)
    if all_passed:
        print("[SUCCESS] GOLDEN EXECUTION PIPELINE TEST PASSED (100% REAL PROVENANCE)")
    else:
        print("[FAILURE] GOLDEN TEST FAILED")
    print("=" * 70)

    assert all_passed, "All assertions must pass cleanly!"


if __name__ == "__main__":
    main()
