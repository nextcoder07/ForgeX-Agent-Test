"""
FastAPI Endpoints for ForgeX Platform-AI Meta-Evaluation, Self-Improvement & Quality Lab.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.meta_eval.benchmark_engine import compare_stage_model_versions
from app.core.meta_eval.dataset_builder import (
    generate_improvement_training_dataset,
    generate_intake_training_dataset,
    generate_observer_training_dataset,
    generate_scenario_training_dataset,
)
from app.core.meta_eval.evidence_builder import (
    build_execution_observer_evidence_pack,
    build_improvement_evidence_pack,
    build_intake_evidence_pack,
    build_scenario_evidence_pack,
)
from app.core.meta_eval.meta_evaluator import run_platform_meta_evaluation
from app.core.meta_eval.models import (
    ModelBenchmarkComparison,
    OverallPlatformPerformance,
    PlatformStageRole,
    StageDatasetExport,
    StageModelBinding,
)
from app.services.store import store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform-ai", tags=["Platform AI Quality Lab"])


class EvaluatePlatformRequest(BaseModel):
    agent_ids: List[str] = []


class BenchmarkCompareRequest(BaseModel):
    stage: PlatformStageRole
    model_v1: str = "v1.0-base"
    model_v2: str = "v2.0-lora-adapter"


# ---------------------------------------------------------------------------
# 1. Platform AI Model Bindings (Primary Cloud vs Stage-Specific Fallbacks)
# ---------------------------------------------------------------------------
@router.get("/model-bindings", response_model=List[StageModelBinding])
def get_stage_model_bindings():
    """Returns the stage-specific primary and local fallback model bindings."""
    return [
        StageModelBinding(
            id="bind-intake",
            stage=PlatformStageRole.INTAKE_ANALYST,
            stage_name="Intake Analyst",
            primary_connection_id="cloud_rotation_pool",
            fallback_connection_id="ollama_intake_connection",
            active_connection_id="primary",
            fallback_enabled=True,
            primary_model="gemini-3.6-flash",
            fallback_model="qwen2.5-coder:7b",
            adapter_reference="forgeX-intake-v2",
            health_status="HEALTHY"
        ),
        StageModelBinding(
            id="bind-scenario",
            stage=PlatformStageRole.SCENARIO_PLANNER,
            stage_name="Scenario Planner",
            primary_connection_id="cloud_rotation_pool",
            fallback_connection_id="ollama_scenario_connection",
            active_connection_id="primary",
            fallback_enabled=True,
            primary_model="gemini-3.6-flash",
            fallback_model="qwen2.5-coder:7b",
            adapter_reference="forgeX-scenario-v2",
            health_status="HEALTHY"
        ),
        StageModelBinding(
            id="bind-observer",
            stage=PlatformStageRole.EXECUTION_OBSERVER,
            stage_name="Execution Observer",
            primary_connection_id="cloud_rotation_pool",
            fallback_connection_id="ollama_observer_connection",
            active_connection_id="primary",
            fallback_enabled=True,
            primary_model="gemini-3.6-flash",
            fallback_model="qwen2.5-coder:7b",
            adapter_reference="forgeX-observer-v2",
            health_status="HEALTHY"
        ),
        StageModelBinding(
            id="bind-improvement",
            stage=PlatformStageRole.IMPROVEMENT_ANALYST,
            stage_name="Improvement Analyst",
            primary_connection_id="cloud_rotation_pool",
            fallback_connection_id="ollama_repair_connection",
            active_connection_id="primary",
            fallback_enabled=True,
            primary_model="gemini-3.6-flash",
            fallback_model="qwen2.5-coder:7b",
            adapter_reference="forgeX-repair-v2",
            health_status="HEALTHY"
        ),
        StageModelBinding(
            id="bind-meta-evaluator",
            stage=PlatformStageRole.META_EVALUATOR,
            stage_name="Independent Meta-Evaluator",
            primary_connection_id="meta_evaluator_rotation_pool",
            fallback_connection_id="ollama_meta_eval_connection",
            active_connection_id="primary",
            fallback_enabled=True,
            primary_model="gemini-3.6-flash",
            fallback_model="qwen2.5-coder:7b",
            adapter_reference="forgeX-meta-evaluator-v1",
            health_status="HEALTHY"
        ),
    ]


# ---------------------------------------------------------------------------
# 2. Execute Meta-Evaluation Across Selected Test Agents
# ---------------------------------------------------------------------------
@router.post("/performance", response_model=OverallPlatformPerformance)
def evaluate_platform_performance(req: EvaluatePlatformRequest):
    """Runs the independent Meta-Evaluator across selected test agents to score all 4 platform stages."""
    try:
        report = run_platform_meta_evaluation(req.agent_ids)
        return report
    except Exception as e:
        logger.exception("Failed to run platform meta-evaluation")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 3. Stage-Specific Training Dataset Exports (SFT/DPO with Splits)
# ---------------------------------------------------------------------------
@router.get("/dataset/{stage}", response_model=StageDatasetExport)
def get_stage_training_dataset(stage: str, agent_ids: Optional[str] = Query(None)):
    """Exports stage-specific training dataset partitioned into TRAIN, VALIDATION, and HELD_OUT splits."""
    stage_enum = None
    stage_clean = stage.upper().replace("-", "_")
    for r in PlatformStageRole:
        if r.value == stage_clean or r.name == stage_clean or r.value.startswith(stage_clean):
            stage_enum = r
            break

    if not stage_enum:
        stage_enum = PlatformStageRole.INTAKE_ANALYST

    target_agent_ids = [aid.strip() for aid in agent_ids.split(",")] if agent_ids else []
    all_agents = list(store.agents.values())
    target_agents = [a for a in all_agents if a.id in target_agent_ids] if target_agent_ids else all_agents

    if not target_agents:
        target_agents = all_agents[:1]

    if stage_enum == PlatformStageRole.INTAKE_ANALYST:
        packs = [build_intake_evidence_pack(a) for a in target_agents]
        return generate_intake_training_dataset(packs)
    elif stage_enum == PlatformStageRole.SCENARIO_PLANNER:
        packs = [build_scenario_evidence_pack(a) for a in target_agents]
        return generate_scenario_training_dataset(packs)
    elif stage_enum == PlatformStageRole.EXECUTION_OBSERVER:
        packs = [build_execution_observer_evidence_pack(a) for a in target_agents]
        return generate_observer_training_dataset(packs)
    else:
        packs = [build_improvement_evidence_pack(a) for a in target_agents]
        return generate_improvement_training_dataset(packs)


# ---------------------------------------------------------------------------
# 4. Held-Out Benchmark Model Comparison
# ---------------------------------------------------------------------------
@router.post("/benchmark-compare", response_model=ModelBenchmarkComparison)
def compare_model_benchmarks(req: BenchmarkCompareRequest):
    """Compares Model v1 vs Model v2 strictly against the frozen HELD_OUT benchmark set."""
    return compare_stage_model_versions(
        stage=req.stage,
        model_v1_version=req.model_v1,
        model_v2_version=req.model_v2
    )
