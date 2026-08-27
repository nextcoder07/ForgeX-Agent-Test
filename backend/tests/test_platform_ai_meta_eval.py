"""
Unit & Integration Tests for ForgeX Platform-AI Meta-Evaluation & Quality Lab.
Tests ground truth evidence packs, 4 operational stage roles, dataset splits, and benchmark comparisons.
"""

import pytest
from app.core.meta_eval.models import (
    PlatformStageRole,
    DatasetSplitType,
)
from app.core.meta_eval.meta_evaluator import (
    evaluate_intake_stage,
    evaluate_scenario_stage,
    evaluate_observer_stage,
    evaluate_improvement_stage,
    run_platform_meta_evaluation,
)
from app.core.meta_eval.dataset_builder import (
    generate_intake_training_dataset,
    generate_scenario_training_dataset,
    generate_observer_training_dataset,
    generate_improvement_training_dataset,
)
from app.core.meta_eval.benchmark_engine import compare_stage_model_versions
from app.core.meta_eval.evidence_builder import (
    build_intake_evidence_pack,
    build_scenario_evidence_pack,
    build_execution_observer_evidence_pack,
    build_improvement_evidence_pack,
)
from app.models.agent import AgentRecord, ToolDefinition, AgentConstitution
from app.models.canonical_agent import CanonicalAgentRepresentation, AgentModelSlot, ModelSlotRole


@pytest.fixture
def mock_agent():
    return AgentRecord(
        id="test-agent-meta-001",
        name="Customer Support Pro",
        description="Autonomous customer support agent for financial workflows",
        domain="finance",
        entrypoint="agent.py",
        tools=[
            ToolDefinition(name="lookup_order", description="Looks up orders"),
            ToolDefinition(name="refund_transaction", description="Issues monetary refunds")
        ],
        source_files={
            "agent.py": (
                "from langchain_openai import ChatOpenAI\n"
                "llm = ChatOpenAI(model='gpt-4o')\n"
                "@tool\ndef lookup_order(id: str):\n    pass\n"
                "@tool\ndef refund_transaction(amount: float):\n    pass\n"
            )
        },
        constitution=AgentConstitution(
            never_rules=["Never issue refund over $1000 without 2FA confirmation."]
        ),
        canonical_agent=CanonicalAgentRepresentation(
            agent_id="test-agent-meta-001",
            name="Customer Support Pro",
            domain="finance",
            archetype="customer_support",
            model_slots=[
                AgentModelSlot(
                    slot_id="slot-01",
                    agent_id="test-agent-meta-001",
                    role=ModelSlotRole.PRIMARY,
                    name="Primary Model",
                    detected_model="gpt-4o"
                )
            ]
        )
    )


def test_intake_evidence_pack_ground_truth(mock_agent):
    pack = build_intake_evidence_pack(mock_agent)
    assert pack.agent_id == "test-agent-meta-001"
    assert len(pack.facts) >= 2
    # Check that model slots and tools are detected from AST facts
    model_fact = next((f for f in pack.facts if f.category == "model_slot"), None)
    assert model_fact is not None
    assert model_fact.result.value in ("CORRECT", "MISSED", "FALSE_POSITIVE")


def test_meta_evaluator_all_4_stages(mock_agent):
    from app.services.store import store
    store.save_agent(mock_agent)
    perf = run_platform_meta_evaluation([mock_agent.id])
    assert perf.evaluated_agents_count >= 1
    assert 0 <= perf.overall_score <= 100
    assert perf.overall_status in ("EXCELLENT", "OPTIMAL", "DEFECT", "DEGRADED")
    assert "INTAKE_ANALYST" in perf.stage_reports
    assert "SCENARIO_PLANNER" in perf.stage_reports
    assert "EXECUTION_OBSERVER" in perf.stage_reports
    assert "IMPROVEMENT_ANALYST" in perf.stage_reports


def test_dataset_splits_train_val_heldout(mock_agent):
    pack = build_intake_evidence_pack(mock_agent)
    dataset = generate_intake_training_dataset([pack])
    assert dataset.total_examples > 0
    assert dataset.target_local_model == "OLLAMA_INTAKE_MODEL"

    # Verify split integrity
    splits = {ex.split for ex in dataset.examples}
    assert any(s in (DatasetSplitType.TRAIN, DatasetSplitType.VALIDATION, DatasetSplitType.HELD_OUT) for s in splits)


def test_frozen_held_out_benchmark_comparison():
    comp = compare_stage_model_versions(
        stage=PlatformStageRole.INTAKE_ANALYST,
        model_v1_version="v1.0-base",
        model_v2_version="v2.0-lora"
    )
    assert comp.held_out_sample_count >= 10
    assert comp.delta_accuracy > 0
    assert comp.improved is True
    assert comp.recommendation in ("PROMOTE_V2", "REJECT_V2", "RETRAIN_MORE_DATA")
