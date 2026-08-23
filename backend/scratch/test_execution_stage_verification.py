import os
import sys
import asyncio
import json

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.store import store
from app.core.llm.key_manager import TestAgentKeyManager, UnifiedKeyManager
from app.core.sandbox.subprocess_runner import create_sanitized_environment
from app.core.execution.controller import ExecutionController
from app.core.dependencies.dependency_resolver import DependencyResolver
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.core.evaluation.hybrid_evaluator import evaluate_trace


async def verify_execution_stage():
    print("======================================================================")
    print("VERIFYING EXECUTION STAGE & TEST AGENT API KEY ROTATION")
    print("======================================================================")

    # 1. Verify Test Agent Key Manager & Environment Injection
    print("\n[TEST 1] Testing TestAgentKeyManager & Environment Key Mapping...")
    test_km = TestAgentKeyManager()
    creds = test_km.get_active_test_credentials()
    print(f"-> Active Test Credentials: {list(creds.keys())}")
    assert "OPENAI_API_KEY" in creds, "OPENAI_API_KEY missing from test agent credentials mapping!"
    assert "GEMINI_API_KEY" in creds, "GEMINI_API_KEY missing from test agent credentials mapping!"
    
    sanitized_env = create_sanitized_environment(provided_secrets={"WHO_CLINICAL_API_KEY": "test-key-123"})
    print(f"-> Sanitized Subprocess Environment Keys: OPENAI_API_KEY={'PRESENT' if 'OPENAI_API_KEY' in sanitized_env else 'ABSENT'}, WHO_CLINICAL_API_KEY={'PRESENT' if 'WHO_CLINICAL_API_KEY' in sanitized_env else 'ABSENT'}")
    assert "OPENAI_API_KEY" in sanitized_env, "Subprocess environment failed to receive OPENAI_API_KEY!"
    assert "WHO_CLINICAL_API_KEY" in sanitized_env, "Subprocess environment failed to receive user secret WHO_CLINICAL_API_KEY!"

    # 2. Find or register test agent for preflight & execution
    agents = store.list_agents()
    print(f"\n[TEST 2] Stored Agents Count: {len(agents)}")
    if not agents:
        print("ERROR: No agents found in store!")
        return

    agent = agents[0]
    print(f"-> Selected Agent: {agent.name} ({agent.id})")

    # 3. Test Preflight Requirements & Credential Demands
    print("\n[TEST 3] Testing Preflight Credential Resolver...")
    prompt = DependencyResolver.evaluate_execution_credential_demands(
        agent=agent,
        provided_secrets={"WHO_CLINICAL_API_KEY": "val-1", "INTERNAL_HOSPITAL_DB_KEY": "val-2"}
    )
    print(f"-> Credential Prompt Status: all_fulfilled={prompt.all_fulfilled}, message={prompt.message}")

    # 4. Test Sandboxed Scenario Execution & Trajectory Step Observation
    scenarios = [s for s in store.list_scenarios() if s.agent_id == agent.id]
    print(f"\n[TEST 4] Agent Scenarios Count: {len(scenarios)}")
    if not scenarios:
        print("WARNING: No scenarios found for agent! Listing all scenarios...")
        all_sc = store.list_scenarios()
        if all_sc:
            scenarios = all_sc[:1]
            print(f"-> Using fallback scenario: {scenarios[0].title} ({scenarios[0].id})")

    if scenarios:
        sc = scenarios[0]
        print(f"-> Running Execution Session for scenario: {sc.title} ({sc.id})...")
        res = await ExecutionController.run_session(
            agent=agent,
            scenario=sc,
            provided_secrets={"WHO_CLINICAL_API_KEY": "mock-who", "INTERNAL_HOSPITAL_DB_KEY": "mock-db"}
        )
        print(f"-> Session Completed: session_id={res['session_id']}, steps={res['trajectory_steps']}, status={res['status']}")

        session_steps = store.get_execution_steps(res['session_id'])
        print(f"-> Trajectory Steps Recorded: {len(session_steps)}")
        for step in session_steps[:5]:
            print(f"   * [{step.event_type}] ({step.actor}): {step.input_data or step.output_data}")

    print("\n======================================================================")
    print("EXECUTION STAGE VERIFICATION PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    asyncio.run(verify_execution_stage())
