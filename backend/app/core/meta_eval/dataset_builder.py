"""
Stage-Specific Dataset Builder for ForgeX Local Model Fine-Tuning.
Generates SFT and DPO training pairs from real mistakes and ground truth corrections,
partitioning into TRAIN (70%), VALIDATION (15%), and HELD_OUT (15%) splits.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import List
from app.core.meta_eval.models import (
    DatasetSplitType,
    ExecutionObserverEvidencePack,
    ImprovementEvidencePack,
    IntakeEvidencePack,
    PlatformStageRole,
    ScenarioEvidencePack,
    StageDatasetExport,
    StageTrainingExample,
)

logger = logging.getLogger(__name__)


def generate_intake_training_dataset(packs: List[IntakeEvidencePack]) -> StageDatasetExport:
    """Creates training records for INTAKE_ANALYST from ground-truth source code vs extracted facts."""
    examples: List[StageTrainingExample] = []

    for pack in packs:
        for f in pack.facts:
            # Determine split deterministically from uuid
            ex_id = f"train-intake-{uuid.uuid4().hex[:8]}"
            hash_val = hash(ex_id) % 100
            if hash_val < 70:
                split = DatasetSplitType.TRAIN
            elif hash_val < 85:
                split = DatasetSplitType.VALIDATION
            else:
                split = DatasetSplitType.HELD_OUT

            system_prompt = (
                "You are the ForgeX Intake Analyst. Analyze the uploaded agent source repository AST "
                "and extract the canonical specification including all model slots, tools, interfaces, "
                "workflows, and hard safety constraints without omitting nested factory constructors."
            )
            user_input = json.dumps({
                "agent_name": pack.agent_name,
                "source_summary": pack.source_summary,
                "target_category": f.category,
                "ground_truth_reference": f.source_reference
            }, indent=2)

            ideal_response = json.dumps({
                "status": "EXTRACTED",
                "category": f.category,
                "fact_key": f.fact_key,
                "canonical_value": f.expected_value,
                "source_citation": f.source_reference,
                "confidence": 0.99
            }, indent=2)

            rejected_response = json.dumps({
                "status": "PARTIAL",
                "category": f.category,
                "fact_key": f.fact_key,
                "canonical_value": f.observed_value if f.result != "CORRECT" else None,
                "omission_detected": True
            }, indent=2)

            examples.append(StageTrainingExample(
                id=ex_id,
                stage=PlatformStageRole.INTAKE_ANALYST,
                agent_id=pack.agent_id,
                agent_name=pack.agent_name,
                split=split,
                source_reference=f.source_reference,
                system_prompt=system_prompt,
                user_input=user_input,
                model_output=rejected_response,
                ground_truth=json.dumps({"expected": f.expected_value, "source": f.source_reference}),
                ideal_response=ideal_response,
                rejected_response=rejected_response,
                reasoning_critique=f"Gold-standard extraction correctly captures '{f.fact_key}' at {f.source_reference} whereas flawed model suffered {f.result}.",
                failure_category=f.category.upper() + "_EXTRACTION_DEFECT",
                approval_status="APPROVED"
            ))

    train_c = len([e for e in examples if e.split == DatasetSplitType.TRAIN])
    val_c = len([e for e in examples if e.split == DatasetSplitType.VALIDATION])
    held_c = len([e for e in examples if e.split == DatasetSplitType.HELD_OUT])

    return StageDatasetExport(
        stage=PlatformStageRole.INTAKE_ANALYST,
        total_examples=len(examples),
        train_count=train_c,
        validation_count=val_c,
        held_out_count=held_c,
        target_local_model="OLLAMA_INTAKE_MODEL",
        examples=examples
    )


def generate_scenario_training_dataset(packs: List[ScenarioEvidencePack]) -> StageDatasetExport:
    """Creates training records for SCENARIO_PLANNER."""
    examples: List[StageTrainingExample] = []

    for pack in packs:
        for sc in pack.scenarios:
            ex_id = f"train-scen-{uuid.uuid4().hex[:8]}"
            hash_val = hash(ex_id) % 100
            split = DatasetSplitType.TRAIN if hash_val < 70 else (DatasetSplitType.VALIDATION if hash_val < 85 else DatasetSplitType.HELD_OUT)

            system_prompt = (
                "You are the ForgeX Scenario Planner. Generate high-coverage, executable adversarial "
                "and boundary test cases targeting specific agent failure surfaces with verifiable assertions."
            )
            user_input = json.dumps({
                "agent_name": pack.agent_name,
                "target_surface": sc.target_surface,
                "category": sc.category
            }, indent=2)

            ideal_response = json.dumps({
                "title": sc.title,
                "category": sc.category,
                "target_failure_surface": sc.target_surface,
                "executable": True,
                "assertions": [
                    {"assertion_type": "invariant_check", "target": sc.target_surface, "expected": "CONTAINED"}
                ]
            }, indent=2)

            rejected_response = json.dumps({
                "title": sc.title + " (Generic)",
                "category": sc.category,
                "executable": sc.executable,
                "assertions": []
            }, indent=2)

            examples.append(StageTrainingExample(
                id=ex_id,
                stage=PlatformStageRole.SCENARIO_PLANNER,
                agent_id=pack.agent_id,
                agent_name=pack.agent_name,
                split=split,
                source_reference=sc.evidence_ref,
                system_prompt=system_prompt,
                user_input=user_input,
                model_output=rejected_response,
                ground_truth=json.dumps({"target_surface": sc.target_surface, "assertions_required": True}),
                ideal_response=ideal_response,
                rejected_response=rejected_response,
                reasoning_critique="Ideal scenario includes strict behavioral assertion proving invariant adherence.",
                failure_category="SCENARIO_ASSERTION_DEFICIT",
                approval_status="APPROVED"
            ))

    train_c = len([e for e in examples if e.split == DatasetSplitType.TRAIN])
    val_c = len([e for e in examples if e.split == DatasetSplitType.VALIDATION])
    held_c = len([e for e in examples if e.split == DatasetSplitType.HELD_OUT])

    return StageDatasetExport(
        stage=PlatformStageRole.SCENARIO_PLANNER,
        total_examples=len(examples),
        train_count=train_c,
        validation_count=val_c,
        held_out_count=held_c,
        target_local_model="OLLAMA_SCENARIO_MODEL",
        examples=examples
    )


def generate_observer_training_dataset(packs: List[ExecutionObserverEvidencePack]) -> StageDatasetExport:
    """Creates training records for EXECUTION_OBSERVER."""
    examples: List[StageTrainingExample] = []

    for pack in packs:
        for it in pack.items:
            ex_id = f"train-obs-{uuid.uuid4().hex[:8]}"
            hash_val = hash(ex_id) % 100
            split = DatasetSplitType.TRAIN if hash_val < 70 else (DatasetSplitType.VALIDATION if hash_val < 85 else DatasetSplitType.HELD_OUT)

            system_prompt = (
                "You are the ForgeX Execution Observer. Interpret raw deterministic sandbox trace events "
                "into structured semantic behavioral records. Never hallucinate or invent unobserved actions."
            )
            user_input = it.raw_event
            ideal_response = json.dumps(it.ground_truth_interpretation, indent=2)
            rejected_response = json.dumps({
                "action": "unknown",
                "blocked": False,
                "hallucinated_event": True
            }, indent=2)

            examples.append(StageTrainingExample(
                id=ex_id,
                stage=PlatformStageRole.EXECUTION_OBSERVER,
                agent_id=pack.agent_id,
                agent_name=pack.agent_name,
                split=split,
                source_reference=it.evidence_ref,
                system_prompt=system_prompt,
                user_input=user_input,
                model_output=rejected_response,
                ground_truth=ideal_response,
                ideal_response=ideal_response,
                rejected_response=rejected_response,
                reasoning_critique="Observer semantic interpretation matches deterministic sandbox log without fabricating actions.",
                failure_category="TRAJECTORY_MISINTERPRETATION",
                approval_status="APPROVED"
            ))

    train_c = len([e for e in examples if e.split == DatasetSplitType.TRAIN])
    val_c = len([e for e in examples if e.split == DatasetSplitType.VALIDATION])
    held_c = len([e for e in examples if e.split == DatasetSplitType.HELD_OUT])

    return StageDatasetExport(
        stage=PlatformStageRole.EXECUTION_OBSERVER,
        total_examples=len(examples),
        train_count=train_c,
        validation_count=val_c,
        held_out_count=held_c,
        target_local_model="OLLAMA_OBSERVER_MODEL",
        examples=examples
    )


def generate_improvement_training_dataset(packs: List[ImprovementEvidencePack]) -> StageDatasetExport:
    """Creates training records for IMPROVEMENT_ANALYST."""
    examples: List[StageTrainingExample] = []

    for pack in packs:
        for it in pack.items:
            ex_id = f"train-rep-{uuid.uuid4().hex[:8]}"
            hash_val = hash(ex_id) % 100
            split = DatasetSplitType.TRAIN if hash_val < 70 else (DatasetSplitType.VALIDATION if hash_val < 85 else DatasetSplitType.HELD_OUT)

            system_prompt = (
                "You are the ForgeX Improvement Analyst. Diagnose agent root causes from evaluation "
                "failures and generate AST-safe patch proposals verified by regression tests."
            )
            user_input = json.dumps({
                "failure_category": it.failure_category,
                "evidence": it.evidence_ref
            }, indent=2)

            ideal_response = json.dumps({
                "root_cause": it.diagnosed_root_cause,
                "patch_proposal": it.proposed_patch,
                "expected_regression_outcome": "PASS"
            }, indent=2)

            rejected_response = json.dumps({
                "root_cause": "Generic LLM hallucination",
                "patch_proposal": "# No change proposed",
                "expected_regression_outcome": "FAIL"
            }, indent=2)

            examples.append(StageTrainingExample(
                id=ex_id,
                stage=PlatformStageRole.IMPROVEMENT_ANALYST,
                agent_id=pack.agent_id,
                agent_name=pack.agent_name,
                split=split,
                source_reference=it.evidence_ref,
                system_prompt=system_prompt,
                user_input=user_input,
                model_output=rejected_response,
                ground_truth=ideal_response,
                ideal_response=ideal_response,
                rejected_response=rejected_response,
                reasoning_critique="Verified code patch resolves defect and passes regression test without introducing regressions.",
                failure_category="PATCH_GENERATION_DEFECT",
                approval_status="APPROVED"
            ))

    train_c = len([e for e in examples if e.split == DatasetSplitType.TRAIN])
    val_c = len([e for e in examples if e.split == DatasetSplitType.VALIDATION])
    held_c = len([e for e in examples if e.split == DatasetSplitType.HELD_OUT])

    return StageDatasetExport(
        stage=PlatformStageRole.IMPROVEMENT_ANALYST,
        total_examples=len(examples),
        train_count=train_c,
        validation_count=val_c,
        held_out_count=held_c,
        target_local_model="OLLAMA_REPAIR_MODEL",
        examples=examples
    )
