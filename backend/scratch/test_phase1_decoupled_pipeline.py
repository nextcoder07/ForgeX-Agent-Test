"""
Phase 1 Decoupled Pipeline Verification Script.
Tests:
  1. Agent Registration & Intake persistence
  2. Independent Scenario Generation & persistence
  3. Independent Sandbox Execution & trace persistence
  4. Independent Evaluation of stored traces & scorecard persistence
  5. Restart independence (retrieving state purely via stable IDs)
"""

import sys
import os

# Set up python path to include backend
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

import asyncio
from app.services.store import store
from app.api.intake import list_local_demo_agents, get_local_demo_agent_files, analyze_agent, register_normalized_spec
from app.models.intake import AgentIntakePayload, RegisterSpecRequest
from app.api.scenarios import generate_and_validate_scenarios, GenerateScenariosRequest
from app.api.executions import start_execution_job, RunExecutionRequest
from app.api.evaluations import evaluate_execution, EvaluateExecutionRequest


async def run_verification():
    print("=" * 80)
    print("PHASE 1 DECOUPLED PIPELINE VERIFICATION TEST SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: Agent Upload / Intake & Registration
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Ingesting & Registering Agent '03-customer-support'...")
    demo_files = get_local_demo_agent_files("03-customer-support")
    intake_payload = AgentIntakePayload(
        agent_name_hint="Customer Support Agent",
        files=demo_files["files"]
    )
    understanding_result = await analyze_agent(intake_payload)
    
    register_req = RegisterSpecRequest(
        normalized_spec=understanding_result.normalized_spec,
        display_name="Customer Support Agent (Phase 1 Test)",
        source_files=demo_files["files"]
    )
    agent = register_normalized_spec(register_req)
    agent_id = agent.id

    assert agent_id is not None, "Agent ID must not be None"
    assert store.get_agent(agent_id) is not None, "Agent must be saved in store"
    print(f"✓ TEST 1 PASSED: Agent successfully registered & persisted in store!")
    print(f"  - Agent ID: {agent_id}")
    print(f"  - Inferred Domain: {agent.domain}")
    print(f"  - Tool Count: {len(agent.tools)}")

    # -------------------------------------------------------------------------
    # TEST 2: Independent Scenario Generation & Persistence
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Generating 5 Adversarial Scenarios independently...")
    gen_req = GenerateScenariosRequest(
        agent_id=agent_id,
        scenario_type="adversarial",
        count=5,
        difficulty="hard"
    )
    generated_scenarios = await generate_and_validate_scenarios(gen_req)
    scenario_ids = [sc.id for sc in generated_scenarios]

    assert len(scenario_ids) > 0, "Scenario IDs must not be empty"
    for sc_id in scenario_ids:
        sc_in_store = store.get_scenario(sc_id)
        assert sc_in_store is not None, f"Scenario {sc_id} must exist in store"
        assert sc_in_store.agent_id == agent_id, f"Scenario {sc_id} agent_id match failed"

    print(f"✓ TEST 2 PASSED: Generated & persisted {len(scenario_ids)} scenarios!")
    print(f"  - Scenario IDs: {scenario_ids}")

    # -------------------------------------------------------------------------
    # TEST 3: Independent Sandbox Execution using ONLY agent_id & scenario_ids
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Executing Scenarios in Sandbox using ONLY IDs...")
    exec_req = RunExecutionRequest(
        agent_id=agent_id,
        scenario_ids=scenario_ids,
        include_counterfactuals=True,
        run_sync=True
    )
    # Class mimicking FastAPI BackgroundTasks for synchronous test run
    class SyncBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            func(*args, **kwargs)

    exec_job = await start_execution_job(exec_req, SyncBackgroundTasks())
    exec_job_id = exec_job.id

    assert exec_job_id is not None, "Execution job ID must not be None"
    assert exec_job.status == "completed", f"Execution job status must be completed, got {exec_job.status}"
    
    stored_traces = store.traces.get(exec_job_id, [])
    assert len(stored_traces) > 0, "Stored execution traces must not be empty"
    
    print(f"✓ TEST 3 PASSED: Executed scenarios and persisted traces!")
    print(f"  - Execution Job ID: {exec_job_id}")
    print(f"  - Status: {exec_job.status}")
    print(f"  - Total Execution Traces Collected: {len(stored_traces)}")

    # -------------------------------------------------------------------------
    # TEST 4: Independent Evaluation using ONLY execution_job_id
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Running Evaluation using ONLY execution_job_id...")
    eval_req = EvaluateExecutionRequest(
        execution_job_id=exec_job_id,
        include_counterfactuals=True
    )
    eval_job = await evaluate_execution(eval_req)
    eval_job_id = eval_job.id

    scorecard = store.get_scorecard(eval_job_id)
    assert scorecard is not None, f"Scorecard {eval_job_id} must exist in store"
    verdicts = store.verdicts.get(eval_job_id, [])
    clusters = store.get_clusters(eval_job_id)

    print(f"✓ TEST 4 PASSED: Evaluated execution job and generated reliability scorecard!")
    print(f"  - Evaluation Job ID: {eval_job_id}")
    print(f"  - Safety Axis Score: {scorecard.safety_axis}%")
    print(f"  - Capability Axis Score: {scorecard.capability_axis}%")
    print(f"  - Composite Score: {scorecard.composite}%")
    print(f"  - Failure Clusters Identified: {len(clusters)}")

    # -------------------------------------------------------------------------
    # TEST 5: Process Restart / Memory Decoupling Test
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing State Retrieval via Stable IDs (Restart Independence)...")
    
    # Simulate a brand new request/session looking up persisted data strictly by ID
    retrieved_agent = store.get_agent(agent_id)
    assert retrieved_agent is not None, "Failed to retrieve agent by ID"

    retrieved_scenarios = [store.get_scenario(sc_id) for sc_id in scenario_ids]
    assert all(s is not None for s in retrieved_scenarios), "Failed to retrieve scenarios by IDs"

    retrieved_exec_job = store.get_execution_job(exec_job_id)
    assert retrieved_exec_job is not None, "Failed to retrieve execution job by ID"

    retrieved_traces = store.traces.get(exec_job_id)
    assert retrieved_traces is not None and len(retrieved_traces) > 0, "Failed to retrieve traces by job ID"

    retrieved_scorecard = store.get_scorecard(eval_job_id)
    assert retrieved_scorecard is not None, "Failed to retrieve scorecard by eval ID"

    print("✓ TEST 5 PASSED: All entities successfully retrieved purely by stable IDs!")
    print("=" * 80)
    print("ALL PHASE 1 DECOUPLED PIPELINE TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_verification())
