"""
Scenario Intelligence, Planning, Generation, Critic, and Coverage Gap API Router.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    TargetSubsystem,
    StrategyPlan,
    CoverageGapReport,
    ScenarioGenerationRequest,
    ScenarioGenerationRun,
    ScenarioPlan
)
from app.services.store import store
from app.core.scenarios.strategy_planner import build_test_strategy, build_deterministic_scenario_plan
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent, deduplicate_scenarios
from app.core.scenarios.scenario_critic import critique_scenarios
from app.core.scenarios.scenario_validator import hard_validate_scenarios
from app.core.scenarios.coverage_engine import compute_coverage_gaps
from app.core.scenarios.scenario_context import build_scenario_context
import logging
import uuid
import datetime as dt
from app.core.llm.providers import get_platform_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class GenerateScenariosRequest(BaseModel):
    agent_id: str
    target_count: int = 25
    scenario_type: Optional[str] = None
    category_counts: Optional[Dict[str, int]] = None
    count: Optional[int] = None
    difficulty: Optional[str] = None
    user_instructions: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None


@router.get("/strategy/{agent_id}", response_model=StrategyPlan)
def get_test_strategy(agent_id: str, target_count: int = 20, category_counts: Optional[str] = None):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    parsed_counts = None
    if category_counts:
        try:
            import json
            parsed_counts = json.loads(category_counts)
        except Exception:
            pass

    return build_test_strategy(agent, desired_count=target_count, category_counts=parsed_counts)


@router.get("/plan/{agent_id}", response_model=ScenarioPlan)
def get_scenario_plan(agent_id: str, target_count: int = 20):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    req = ScenarioGenerationRequest(agent_id=agent_id, target_count=target_count)
    return build_deterministic_scenario_plan(agent, req)


@router.post("/generation-run", response_model=ScenarioGenerationRun)
async def execute_scenario_generation_run(payload: ScenarioGenerationRequest):
    """Executes deterministic-first batch scenario generation, validation, and critic."""
    from app.core.llm.key_manager import UnifiedKeyManager
    UnifiedKeyManager().reset_rotation()

    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    count_val = getattr(payload, "count", None)
    if count_val and count_val > 0:
        payload.target_count = count_val

    run_id = f"gen-run-{uuid.uuid4().hex[:8]}"
    llm = get_platform_provider()

    # 1. Deterministic Context & Plan
    context = build_scenario_context(agent)
    plan = build_deterministic_scenario_plan(agent, payload)
    
    # 2. Batch Generation
    generated: List[Scenario] = []
    generation_method = "ai"
    ai_status = "success"
    failure_reason = None

    try:
        generated = await generate_scenarios_for_agent(
            agent=agent,
            llm=llm,
            scenario_plan=plan,
            request=payload
        )
    except Exception as e:
        logger.warning(f"Batch scenario generation error: {e}")
        ai_status = "failed"
        failure_reason = f"Gemini error: {e}."

    # 3. Deduplication
    original_count = len(generated)
    generated = deduplicate_scenarios(generated)
    duplicate_count = original_count - len(generated)

    # 4. Hard Deterministic Validation (Rule A, Quality Score, Interface Rules)
    hard_passing, rejection_report = hard_validate_scenarios(generated, agent, context)
    
    # 5. LLM Critic (Only on scenarios that passed hard validation)
    if hard_passing:
        critiqued = await critique_scenarios(hard_passing, agent, llm)
    else:
        critiqued = []
        
    # Collate results
    final_scenarios = []
    for sc in generated:
        # If it was passed to the critic, update it from the critiqued list
        c_match = next((c for c in critiqued if c.id == sc.id), None)
        if c_match:
            final_scenarios.append(c_match)
        else:
            final_scenarios.append(sc)

    # 6. Save all scenarios (including rejected) to Store
    ready_count = 0
    blocked_count = 0
    rejected_count = 0
    
    # Report metrics
    rejection_reasons: Dict[str, int] = {}
    quality_sum = 0.0
    cap_cov: Dict[str, int] = {}
    sub_cov: Dict[str, int] = {}
    node_cov: Dict[str, int] = {}
    risk_cov: Dict[str, int] = {}
    
    executable_scenarios = []
    valid_candidates = []

    for sc in final_scenarios:
        sc.agent_id = agent.id
        
        # Metrics
        if sc.scenario_quality_score:
            quality_sum += sc.scenario_quality_score
            
        if (sc.validation_status in ("EXECUTABLE", "VALIDATED") or sc.status in ("EXECUTABLE", "GENERATED")) and sc.status != "REJECTED" and sc.validation_status != "REJECTED_CRITIC":
            sc.validation_status = "EXECUTABLE"
            ready_count += 1
            valid_candidates.append(sc)
            
            # Record coverage metrics only for executable scenarios
            for cap in sc.required_capabilities:
                cap_cov[cap] = cap_cov.get(cap, 0) + 1
            
            ts_val = sc.target_subsystem.value if isinstance(sc.target_subsystem, TargetSubsystem) else str(sc.target_subsystem)
            sub_cov[ts_val] = sub_cov.get(ts_val, 0) + 1
            
            if sc.target_workflow_node:
                node_cov[sc.target_workflow_node] = node_cov.get(sc.target_workflow_node, 0) + 1
                
            risk_cov[sc.risk_level] = risk_cov.get(sc.risk_level, 0) + 1
                
        else:
            rejected_count += 1
            # Accumulate rejection reasons
            if sc.critic_notes:
                # Naive grouping by first few words
                reason_group = " ".join(sc.critic_notes.split()[:4])
                rejection_reasons[reason_group] = rejection_reasons.get(reason_group, 0) + 1

    for report in rejection_report:
        for v in report["violations"]:
            # e.g., "RULE1_UNKNOWN_CLI_FLAGS"
            code = v.split(":")[0]
            rejection_reasons[code] = rejection_reasons.get(code, 0) + 1

    # Replace previous scenarios only if fresh valid ones were produced
    if valid_candidates:
        store.clear_scenarios_for_agent(agent.id)
        for sc in valid_candidates:
            store.save_scenario(sc)
            executable_scenarios.append(sc)
    else:
        # Retain older scenarios if no new valid scenarios were generated
        existing = store.list_scenarios(agent_id=agent.id)
        executable_scenarios = [
            s for s in existing 
            if (s.validation_status in ("EXECUTABLE", "VALIDATED") or s.status in ("EXECUTABLE", "GENERATED"))
            and s.status != "REJECTED" and s.validation_status not in ("REJECTED_CRITIC", "REJECTED_INTERFACE", "REJECTED_QUALITY")
        ]

    run_status = "COMPLETED" if ready_count > 0 else "FAILED"
    avg_quality = quality_sum / max(1, len(final_scenarios))

    return ScenarioGenerationRun(
        id=run_id,
        agent_id=agent.id,
        agent_version_id=agent.version_label,
        requested_count=payload.target_count,
        planned_count=len(plan.plan_items),
        generated_count=len(final_scenarios),
        ready_count=ready_count,
        rejected_count=rejected_count,
        blocked_count=blocked_count,
        provider="gemini" if ai_status == "success" else "deterministic_builder",
        model=llm.model_name if ai_status == "success" else "rule_based_fallback",
        prompt_version="v2",
        status=run_status,
        generation_method=generation_method,
        ai_status=ai_status,
        failure_reason=failure_reason,
        scenarios=executable_scenarios,  # Ensure ONLY executable scenarios are returned to caller
        created_at=dt.datetime.utcnow().isoformat() + "Z",
        rejection_reasons=rejection_reasons,
        hallucination_count=rejection_reasons.get("RULE3_INVENTED_ERROR_MESSAGE", 0),
        interface_mismatch_count=rejection_reasons.get("RULE1_UNKNOWN_CLI_FLAGS", 0),
        assertion_mismatch_count=rejection_reasons.get("RULE_A_JSON_ASSERTION_ON_NON_JSON_AGENT", 0),
        duplicate_count=duplicate_count,
        quality_score_avg=avg_quality,
        capability_coverage=cap_cov,
        subsystem_coverage=sub_cov,
        workflow_node_coverage=node_cov,
        risk_vector_coverage=risk_cov
    )


@router.post("/generate", response_model=List[Scenario])
async def generate_and_validate_scenarios(payload: GenerateScenariosRequest):
    """Backward-compatible scenario generation endpoint."""
    req = ScenarioGenerationRequest(
        agent_id=payload.agent_id,
        target_count=payload.count or payload.target_count or 20,
        category_counts=payload.category_counts,
        user_instructions=payload.user_instructions,
    )
    run_result = await execute_scenario_generation_run(req)
    return run_result.scenarios


@router.get("/library", response_model=List[Scenario])
def list_scenario_library(agent_id: Optional[str] = None):
    # Retrieve all valid/executable scenarios for the library
    all_scenarios = store.list_scenarios(agent_id=agent_id)
    return [
        s for s in all_scenarios 
        if (s.validation_status in ("EXECUTABLE", "VALIDATED") or s.status in ("EXECUTABLE", "GENERATED"))
        and s.status != "REJECTED" and s.validation_status not in ("REJECTED_CRITIC", "REJECTED_INTERFACE", "REJECTED_QUALITY")
    ]


@router.get("/coverage/{agent_id}", response_model=CoverageGapReport)
def get_scenario_coverage_report(agent_id: str):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    scenarios = store.list_scenarios(agent_id=agent_id)
    # Filter to valid/executable scenarios for coverage
    exec_scenarios = [
        s for s in scenarios 
        if (s.validation_status in ("EXECUTABLE", "VALIDATED") or s.status in ("EXECUTABLE", "GENERATED"))
        and s.status != "REJECTED" and s.validation_status not in ("REJECTED_CRITIC", "REJECTED_INTERFACE", "REJECTED_QUALITY")
    ]
    return compute_coverage_gaps(agent, exec_scenarios)
