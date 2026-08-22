"""
End-to-End Golden Test: Resume Parser CLI Agent Vertical Slice.
Verifies the complete top-to-bottom pipeline:
1. Deterministic Interface Contract (CLI)
2. Scenario with Invocation & Input Artifacts
3. Scenario Preflight Validation
4. Isolated Subprocess Sandbox Execution
5. Causal Trajectory Recording
6. Rule & Assertion Evaluation with 100% Provenance
"""

import os
import sys
import json
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.agent import AgentRecord, AgentConstitution
from app.models.scenario import Scenario, ScenarioCategory, ScenarioAssertion, AssertionType
from app.core.execution.preflight import run_scenario_preflight
from app.core.sandbox.subprocess_runner import run_scenario_in_subprocess
from app.core.dependencies.tool_gateway import ToolGateway
from app.core.evaluation.rule_evaluator import RuleEvaluator
from app.models.execution import ExecutionStep

# 1. Concrete Agent Python Source Code
RESUME_PARSER_AGENT_CODE = """
import sys
import json
import os

def parse_resume(file_path):
    if not os.path.exists(file_path):
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)
        
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    lines = [line.strip() for line in text.split("\\n") if line.strip()]
    name = lines[0] if lines else "Unknown"
    
    skills = []
    for line in lines:
        if "skills:" in line.lower():
            skills = [s.strip() for s in line.split(":", 1)[1].split(",")]
            
    result = {
        "status": "SUCCESS",
        "candidate_name": name,
        "raw_lines_count": len(lines),
        "extracted_skills": skills,
        "file_processed": os.path.basename(file_path)
    }
    
    # Print JSON output to stdout
    print(json.dumps(result, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "--resume":
        print(json.dumps({"error": "Usage: python resume_agent.py --resume <path>"}))
        sys.exit(2)
        
    resume_file = sys.argv[2]
    parse_resume(resume_file)
"""


def main():
    print("=" * 70)
    print("[RUNNING GOLDEN VERTICAL SLICE: RESUME PARSER CLI AGENT]")
    print("=" * 70)

    # 1. Initialize Agent Record
    agent = AgentRecord(
        id="agent-resume-parser-v1",
        name="Resume Parser CLI Agent",
        domain="Document Processing",
        description="Autonomous CLI agent that parses text resumes into structured JSON.",
        system_prompt="You are a CLI parser.",
        tools=[],  # Pure CLI workflow agent — 0 tools!
        dependencies=[],
        constitution=AgentConstitution(goals=["Extract candidate skills accurately"]),
        runtime_manifest={"entrypoint": "resume_agent.py"},
        created_at="2026-08-23T00:00:00Z"
    )
    print(f"\n[1/5] Agent Registered: {agent.name} (Tools: {len(agent.tools)}, Entrypoint: {agent.runtime_manifest['entrypoint']})")

    # 2. Build Concrete Scenario with CLI Contract & Input Artifacts
    scenario = Scenario(
        id="SC-CLI-RESUME-001",
        agent_id=agent.id,
        category=ScenarioCategory.NORMAL,
        title="Valid Candidate Resume Parsing",
        purpose="Verify that the CLI agent parses candidate resume text into structured JSON with exit code 0.",
        interface_type="CLI",
        invocation={
            "command": "python resume_agent.py --resume input/sample_resume.txt",
            "args": ["--resume", "input/sample_resume.txt"]
        },
        input_artifacts=[
            {
                "path": "input/sample_resume.txt",
                "content": "Jane Doe\nSenior Distributed Systems Engineer\nSkills: Python, FastAPI, Docker, PostgreSQL\nExperience: 6 years building high-scale backends."
            }
        ],
        assertions=[
            ScenarioAssertion(
                assertion_type="PROCESS_EXIT_CODE",
                target="exit_code",
                expected_value=0,
                description="Process terminates successfully with code 0."
            ),
            ScenarioAssertion(
                assertion_type="STDOUT_JSON_VALID",
                target="stdout",
                expected_value=True,
                description="Process output on stdout is valid parsable JSON."
            ),
            ScenarioAssertion(
                assertion_type="STDOUT_CONTAINS",
                target="Jane Doe",
                expected_value="Jane Doe",
                description="Parsed output includes candidate name Jane Doe."
            ),
            ScenarioAssertion(
                assertion_type="STDOUT_CONTAINS",
                target="FastAPI",
                expected_value="FastAPI",
                description="Parsed output contains extracted skill FastAPI."
            )
        ],
        rationale="WHY THIS TEST EXISTS: Baseline happy-path execution test for CLI resume parser."
    )
    print(f"\n[2/5] Scenario Built: {scenario.title}")
    print(f"      Interface: {scenario.interface_type}")
    print(f"      Invocation: {scenario.invocation['command']}")
    print(f"      Input Artifacts: {[a['path'] for a in scenario.input_artifacts]}")
    print(f"      Assertions Count: {len(scenario.assertions)}")

    # 3. Run Scenario Preflight
    preflight = run_scenario_preflight(scenario, agent)
    print(f"\n[3/5] Preflight Result: {preflight.status} (Ready: {preflight.is_ready})")
    for f in preflight.findings:
        icon = "[PASS]" if f.passed else "[FAIL]"
        print(f"      {icon} [{f.check_name}] {f.message}")
    assert preflight.is_ready, f"Preflight failed: {preflight.findings}"

    # 4. Run Isolated Subprocess Sandbox Execution
    gateway = ToolGateway(tools=agent.tools)
    print(f"\n[4/5] Executing in Isolated Sandbox...")
    trace = run_scenario_in_subprocess(
        agent=agent,
        scenario=scenario,
        code_content=RESUME_PARSER_AGENT_CODE,
        gateway=gateway,
        timeout_seconds=5.0
    )

    print(f"      Execution Completed in {trace.total_latency_ms} ms")
    print("\n      --- Real Trajectory Events Recorded ---")
    for idx, ev in enumerate(trace.events):
        print(f"      [{idx+1:02d}] {ev.timestamp} | {ev.role.upper()}: {ev.content[:120]}")

    # 5. Evaluate Trajectory Evidence Against Assertions
    # Convert trace events into execution steps for evaluator
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
        elif "PROCESS_STARTED:" in ev.content:
            event_type = "PROCESS_STARTED"
        elif "FILE_CREATED:" in ev.content:
            event_type = "FILE_CREATED"
        elif "SANDBOX_STARTED:" in ev.content:
            event_type = "SANDBOX_STARTED"
        elif "SANDBOX_TERMINATED:" in ev.content:
            event_type = "SANDBOX_TERMINATED"

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

    print(f"\n[5/5] Evaluator Scorecard ({len(evidences)} rules tested):")
    all_passed = True
    for ev in evidences:
        icon = "[PASS]" if ev.passed else "[FAIL]"
        if not ev.passed:
            all_passed = False
        print(f"      {icon} [{ev.rule_name}] Expected: {ev.expected} | Actual: {ev.actual}")

    print("\n" + "=" * 70)
    if all_passed:
        print("[SUCCESS] VERTICAL SLICE RESULT: 100% PASS - ZERO FAKE DATA - REAL PROVENANCE")
    else:
        print("[FAILURE] VERTICAL SLICE FAILED")
    print("=" * 70)

    assert all_passed, "All assertions must pass!"


if __name__ == "__main__":
    main()
