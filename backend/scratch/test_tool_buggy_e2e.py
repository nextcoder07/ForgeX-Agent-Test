import os
import sys
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.models.intake import AgentIntakePayload
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.sandbox.subprocess_runner import run_scenario_in_subprocess
from app.core.dependencies.tool_gateway import ToolGateway
from app.core.evaluation.hybrid_evaluator import evaluate_trace
from app.models.agent import AgentRecord
from app.core.llm.providers import UniversalProvider

tool_buggy_code = '''import argparse, json

def search_products(query):
    return [{"name": "Example Product", "query": query}]

def delete_record(record_id):
    return {"deleted": record_id}

def process(request):
    if "delete" in request.lower():
        record_id = request.split()[-1]
        return {"tool": "delete_record", "result": delete_record(record_id)}
    return {"tool": "search_products", "result": search_products(request)}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    args = p.parse_args()
    print(json.dumps(process(args.request)))

if __name__ == "__main__":
    main()
'''

async def run():
    print("[1/4] Processing agent intake...")
    payload = AgentIntakePayload(
        input_type="files",
        files={"agent.py": tool_buggy_code},
        agent_name_hint="tool-buggy"
    )
    llm = UniversalProvider()
    res = await process_agent_intake(payload, llm)
    spec = res.normalized_spec
    print(f"[2/4] Intake complete. Tools: {[t.name for t in spec.tools]}")
    
    agent = AgentRecord(
        id="ag-test-tool-buggy",
        name="tool-buggy",
        description="Tool buggy test agent with delete_record and search_products",
        status="READY",
        source_files=payload.files,
        tools=spec.tools,
        capabilities=spec.capabilities,
        inputs=spec.inputs,
        outputs=spec.outputs,
        constitution=spec.constitution,
        evidence_packet=spec.evidence_packet or {},
        runtime_manifest=spec.runtime_manifest,
    )
    
    print("[3/4] Generating scenarios...")
    scenarios = await generate_scenarios_for_agent(agent, llm, target_count=4)
    sc_list = scenarios if isinstance(scenarios, list) else scenarios.scenarios
    print(f"[4/4] Generated {len(sc_list)} scenarios. Running sandbox execution & evaluation...\n")
    
    pass_count = 0
    fail_count = 0
    gateway = ToolGateway(tools=agent.tools)
    for sc in sc_list:
        # Fix missing --request flag in invocation args
        inv_args = sc.invocation.get("args", [])
        if inv_args and not any(a.startswith("--") for a in inv_args):
            inv_args = ["--request"] + inv_args
            sc.invocation["args"] = inv_args
            sc.invocation["command"] = f"python agent.py --request " + " ".join(f'"{a}"' if " " in a else a for a in inv_args[1:])
        
        print(f"--- Scenario [{sc.category.value.upper()}]: {sc.title} ---")
        print(f"  Cmd: {sc.invocation.get('command', 'N/A')}")
        
        trace = run_scenario_in_subprocess(agent, sc, tool_buggy_code, gateway, timeout_seconds=10)
        
        tc_names = [tc.tool_name for tc in trace.tool_calls]
        exit_ev = next((e for e in trace.events if "PROCESS_EXITED" in e.content), None)
        exit_code = exit_ev.content.split("Exit code ")[-1] if exit_ev else "?"
        print(f"  Exit: {exit_code} | Tool calls: {tc_names}")
        
        verdict = await evaluate_trace(agent, sc, trace, llm)
        
        if verdict.passed:
            pass_count += 1
            print(f"  [PASS] (findings: {len(verdict.findings)})")
        else:
            fail_count += 1
            finding_summary = [f"{f.category}({f.severity})" for f in verdict.findings]
            print(f"  [FAIL] (findings: {len(verdict.findings)})")
            print(f"     Findings: {finding_summary}")
        print()
    
    total = pass_count + fail_count
    print("=" * 60)
    print(f"EVALUATION COMPLETE: {pass_count}/{total} PASSED, {fail_count}/{total} FAILED")
    if fail_count > 0:
        print("✅ ForgeX correctly detected failures in tool-buggy agent!")
    else:
        print("⚠️  WARNING: All scenarios passed — tool-buggy defects were NOT caught.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run())
