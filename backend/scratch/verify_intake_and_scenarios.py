import asyncio
import json
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app.models.intake import AgentIntakePayload
from app.models.scenario import ScenarioGenerationRequest
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.scenarios.strategy_planner import build_deterministic_scenario_plan
from app.core.llm.providers import get_platform_provider
from app.services.store import store

async def test_intake_and_scenarios():
    print("======================================================================")
    print("STAGE 1: AGENT INTAKE & SPECIFICATION RECONSTRUCTION")
    print("======================================================================")

    # 1. Load files from 03-customer-support test-agent
    agent_dir = os.path.abspath(os.path.dirname(__file__) + "/../test-agents/03-customer-support")
    files_payload = {}
    for root, _, files in os.walk(agent_dir):
        for file in files:
            if file.endswith((".py", ".txt", ".json", ".yaml", ".yml", ".md")):
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, agent_dir).replace(os.sep, "/")
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    files_payload[rel_path] = f.read()

    payload = AgentIntakePayload(
        agent_name_hint="Customer Support Agent Demo",
        domain="customer_support",
        files=files_payload,
        input_type="folder"
    )

    llm = get_platform_provider()
    print(f"Using Platform LLM Provider: {llm.__class__.__name__}")

    understanding_result = await process_agent_intake(payload, llm)
    print(f"[OK] Intake Analysis Completed! Status: {understanding_result.analysis_status}")
    print(f"   Agent ID: {understanding_result.agent_record.id}")
    print(f"   Name: {understanding_result.agent_record.name}")
    print(f"   Domain: {understanding_result.agent_record.domain}")
    print(f"   Tools Discovered ({len(understanding_result.agent_record.tools)}):")
    for t in understanding_result.agent_record.tools:
        print(f"     - Tool: {t.name} (Risk: {t.risk}, Capability: {t.canonical_capability})")

    # Save to store
    agent_record = understanding_result.agent_record
    store.save_agent(agent_record)

    print("\n======================================================================")
    print("STAGE 2: SCENARIO INTELLIGENCE & GENERATION")
    print("======================================================================")

    scenario_req = ScenarioGenerationRequest(
        agent_id=agent_record.id,
        target_count=5,
        user_instructions="Focus on unauthorized monetary refunds and order cancellations without confirmation."
    )

    plan = build_deterministic_scenario_plan(agent_record, scenario_req)
    print(f"[OK] Scenario Plan Built! Total Target: {plan.total_target} scenarios across {len(plan.plan_items)} categories.")

    scenarios = await generate_scenarios_for_agent(
        agent=agent_record,
        llm=llm,
        scenario_plan=plan,
        request=scenario_req
    )

    print(f"\n[OK] Scenario Generation Complete! Generated {len(scenarios)} 5-layer scenarios:")
    for sc in scenarios:
        print(f"\n  [Scenario: {sc.id}] - {sc.title}")
        print(f"    Category: {sc.category.value} | Status: {sc.status}")
        print(f"    Purpose: {sc.purpose}")
        print(f"    User Messages: {sc.user_messages}")
        print(f"    Assertions ({len(sc.assertions)}):")
        for a in sc.assertions:
            print(f"      - Assertion: {a.assertion_type} -> Target: {a.target} (Expected: {a.expected_value})")
        if sc.fault_injections:
            print(f"    Fault Injections ({len(sc.fault_injections)}):")
            for f in sc.fault_injections:
                print(f"      - Fault: {f.fault_type} on tool {f.target_tool}")

    # Save generated scenarios to store
    store.save_scenarios(scenarios)
    print("\n======================================================================")
    print("SUMMARY: Both Stage 1 Intake & Stage 2 Scenario Generation Verified OK!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(test_intake_and_scenarios())
