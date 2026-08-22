"""
Phase 3 & Phase 4 Verification Script.
Tests:
  1. Complete Decoupled Pipeline Execution (Intake -> Scenario Gen -> Execution -> Evaluation)
  2. Structured ML Dataset Exporter (Feature extraction for agent, scenario, execution, and target labels)
  3. REST API Dataset Endpoints (/api/datasets/summary, /api/datasets/export in JSONL & CSV format)
"""

import sys
import os

# Set up python path to include backend
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

import asyncio
from app.services.store import store
from app.api.intake import get_local_demo_agent_files, analyze_agent, register_normalized_spec
from app.models.intake import AgentIntakePayload, RegisterSpecRequest
from app.api.scenarios import generate_and_validate_scenarios, GenerateScenariosRequest
from app.api.executions import start_execution_job, RunExecutionRequest
from app.api.evaluations import evaluate_execution, EvaluateExecutionRequest
from app.core.dataset_exporter import extract_ml_dataset_records, export_dataset_jsonl, export_dataset_csv
from app.api.datasets import get_dataset_summary, export_dataset


async def run_phase3_phase4_verification():
    print("=" * 80)
    print("PHASE 3 & PHASE 4 VERIFICATION TEST SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Run complete decoupled pipeline to populate persistent state
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Running Pipeline to populate persistent evaluation data...")
    demo_files = get_local_demo_agent_files("03-customer-support")
    intake_payload = AgentIntakePayload(
        agent_name_hint="Customer Support Agent",
        files=demo_files["files"]
    )
    understanding_result = await analyze_agent(intake_payload)
    
    register_req = RegisterSpecRequest(
        normalized_spec=understanding_result.normalized_spec,
        display_name="Customer Support Agent (Phase 4 Test)",
        source_files=demo_files["files"]
    )
    agent = register_normalized_spec(register_req)
    agent_id = agent.id

    gen_req = GenerateScenariosRequest(
        agent_id=agent_id,
        scenario_type="adversarial",
        count=3,
        difficulty="hard"
    )
    scenarios = await generate_and_validate_scenarios(gen_req)
    scenario_ids = [sc.id for sc in scenarios]

    exec_req = RunExecutionRequest(
        agent_id=agent_id,
        scenario_ids=scenario_ids,
        include_counterfactuals=True,
        run_sync=True
    )
    class SyncBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            func(*args, **kwargs)

    exec_job = await start_execution_job(exec_req, SyncBackgroundTasks())
    
    eval_req = EvaluateExecutionRequest(execution_job_id=exec_job.id)
    eval_job = await evaluate_execution(eval_req)
    print(f"✓ STEP 1 COMPLETE: Created evaluation job {eval_job.id}")

    # -------------------------------------------------------------------------
    # TEST 1: Feature Extraction Engine (dataset_exporter.py)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing ML Dataset Feature Extraction Engine...")
    records = extract_ml_dataset_records(agent_id=agent_id)
    assert len(records) > 0, "Extracted dataset records must not be empty"

    sample = records[0]
    assert "agent_features" in sample, "Sample must contain agent_features"
    assert "scenario_features" in sample, "Sample must contain scenario_features"
    assert "execution_features" in sample, "Sample must contain execution_features"
    assert "target_labels" in sample, "Sample must contain target_labels"

    print("✓ TEST 1 PASSED: Successfully extracted feature vectors & target labels!")
    print(f"  - Total Dataset Records Extracted: {len(records)}")
    print(f"  - Agent Features: {list(sample['agent_features'].keys())}")
    print(f"  - Scenario Features: {list(sample['scenario_features'].keys())}")
    print(f"  - Execution Features: {list(sample['execution_features'].keys())}")
    print(f"  - Target Labels: {list(sample['target_labels'].keys())}")

    # -------------------------------------------------------------------------
    # TEST 2: Dataset Formatting (JSONL & CSV)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing Dataset Exporters (JSONL & CSV)...")
    jsonl_out = export_dataset_jsonl(records)
    assert len(jsonl_out) > 0 and "\n" in jsonl_out, "JSONL output must contain line breaks"

    csv_out = export_dataset_csv(records)
    assert len(csv_out) > 0 and "target_labels.passed" in csv_out, "CSV output must contain headers"

    print("✓ TEST 2 PASSED: JSONL & CSV formatting verified!")
    print(f"  - JSONL Output Size: {len(jsonl_out)} bytes")
    print(f"  - CSV Output Size: {len(csv_out)} bytes")

    # -------------------------------------------------------------------------
    # TEST 3: REST API Dataset Endpoints (/api/datasets/summary & /api/datasets/export)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing REST API Dataset Router Endpoints...")
    summary = get_dataset_summary(agent_id=agent_id)
    assert summary["total_dataset_records"] > 0, "Summary total_dataset_records must be > 0"

    export_res_jsonl = export_dataset(agent_id=agent_id, format="jsonl")
    assert export_res_jsonl.status_code == 200, "Export JSONL status must be 200"
    assert export_res_jsonl.media_type == "application/jsonlines", "Export JSONL media type mismatch"

    export_res_csv = export_dataset(agent_id=agent_id, format="csv")
    assert export_res_csv.status_code == 200, "Export CSV status must be 200"
    assert export_res_csv.media_type == "text/csv", "Export CSV media type mismatch"

    print("✓ TEST 3 PASSED: REST API dataset endpoints functional!")
    print(f"  - Total Dataset Records in Summary: {summary['total_dataset_records']}")
    print(f"  - Failure Categories Count: {summary['failure_categories']}")
    print("=" * 80)
    print("ALL PHASE 3 & PHASE 4 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_phase3_phase4_verification())
