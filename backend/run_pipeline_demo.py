"""
Demonstration run for Member 1 AI Agent Evaluation pipeline.
Executes intake analysis, capability extraction, scenario generation, critiquing,
validation, and coverage analysis for a local demonstration agent.
"""
from __future__ import annotations

import os
import json
from app.core.member1_pipeline import (
    analyze_agent,
    generate_scenarios,
    validate_scenarios,
    calculate_coverage
)
from app.core.scenarios.library import ScenarioLibrary

async def main_async():
    # Resolve backend path dynamically
    current_dir = os.path.dirname(os.path.abspath(__file__))
    agent_path = os.path.join(current_dir, "test-agents", "03-customer-support")
    
    print("=" * 70)
    print("MEMBER 1 PIPELINE DEMONSTRATION")
    print(f"Target Agent: {agent_path}")
    print("=" * 70)
    
    # 1. Semantic Intake Analysis & Capability Extraction
    print("\n[Step 1] Running Intake Analysis & Capability Extraction...")
    spec = await analyze_agent(agent_path)
    print(f"Successfully analyzed agent: '{spec.name}'")
    print(f"Purpose: {spec.purpose}")
    print(f"Extracted Capabilities ({len(spec.capabilities)}):")
    for cap in spec.capabilities:
        print(f" - {cap.capability_id}: {cap.name} (Related Tools: {', '.join(cap.related_tools)})")
        
    # 2. Scenario Generation and Critic Filtering
    print(f"\n[Step 2] Generating Test Scenarios (Target count: 12)...")
    scenarios = await generate_scenarios(spec, count=12)
    print(f"Generated {len(scenarios)} unique test scenarios.")
    for idx, sc in enumerate(scenarios[:3]):
        print(f" - Scenario {idx+1} [{sc.scenario_id}] - Capability: {sc.capability_id} - Category: {sc.category}")
        print(f"   Prompt: {sc.input.get('message', '')}")
        print(f"   Expected behavior: {sc.expected_behavior}")
        print(f"   Critic Score Status: {sc.critic_status} ({sc.critic_feedback})")
    if len(scenarios) > 3:
        print(f"   ... and {len(scenarios) - 3} more scenarios.")

    # 3. Deterministic Validation
    print("\n[Step 3] Running Scenario Validation...")
    val_result = validate_scenarios(scenarios, spec)
    print(f"Validation status: {'VALIDATED' if val_result['is_valid'] else 'INVALID'}")
    if not val_result["is_valid"]:
        print(f"Validation Errors ({val_result['errors_count']}):")
        for err in val_result["errors"]:
            print(f" - [{err['scenario_id']}] Field '{err['field']}': {err['message']}")
            
    # 4. Scenario Library Serialization
    library_path = os.path.join(current_dir, "scratch", "demo_scenario_library.json")
    print(f"\n[Step 4] Saving Scenarios to Library: {library_path}...")
    ScenarioLibrary.save_scenarios(scenarios, library_path)
    print("Scenario library saved successfully.")
    
    # 5. Coverage Calculation
    print("\n[Step 5] Computing Scenario & Capability Coverage Report...")
    report = calculate_coverage(spec, scenarios)
    print("-" * 75)
    print(f"CAPABILITY COVERAGE  : {report.capability_coverage}%")
    print(f"CATEGORY COVERAGE    : {report.category_coverage}%")
    print(f"TOOL COVERAGE        : {report.tool_coverage}%")
    print(f"RISK COVERAGE        : {report.risk_coverage}%")
    print(f"FAILURE MODE COV     : {report.failure_mode_coverage}%")
    print("-" * 75)
    
    if report.untested_capabilities:
        print(f"[Warning] Untested Capabilities: {', '.join(report.untested_capabilities)}")
    if report.untested_tools:
        print(f"[Warning] Untested Tools: {', '.join(report.untested_tools)}")
    if report.untested_risks:
        print(f"[Warning] Untested Risks:\n" + "\n".join(f" - {r}" for r in report.untested_risks))
    if report.missing_categories:
        print(f"[Warning] Missing scenario categories: {', '.join(report.missing_categories)}")
        
    print("\nDemo execution complete. Member 1 pipeline is fully operational!")
    print("=" * 70)

def main():
    import asyncio
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
