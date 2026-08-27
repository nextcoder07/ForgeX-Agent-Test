"""
Scenario Intelligence, Planning, Generation, Critic, and Coverage Gap API Router.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.scenario import (
    Scenario,
    ScenarioCategory,
    StrategyPlan,
    CoverageGapReport,
    ScenarioGenerationRequest,
    ScenarioGenerationRun,
    ScenarioPlan
)
from app.services.store import store
from app.core.scenarios.strategy_planner import build_test_strategy, build_deterministic_scenario_plan
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.scenarios.scenario_critic import critique_scenarios
from app.core.scenarios.scenario_validator import validate_scenarios_deterministically
from app.core.scenarios.coverage_engine import compute_coverage_gaps
import logging
import uuid
import datetime as dt
from app.core.llm.gemini_provider import LLMGenerationError, LLMQuotaExhaustedError
from app.core.llm.providers import get_platform_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class GenerateScenariosRequest(BaseModel):
    agent_id: str
    target_count: int = 25
    scenario_type: Optional[str] = None  # e.g. "normal", "adversarial", "security", "tool_misuse"
    category_counts: Optional[Dict[str, int]] = None  # e.g. {"normal": 2, "edge": 3, "safety": 4, "chaos": 1}
    count: Optional[int] = None           # Alias for target_count
    difficulty: Optional[str] = None      # "easy", "medium", "hard"
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
    """Executes deterministic-first batch scenario generation and returns complete run metrics."""
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    count_val = getattr(payload, "count", None)
    if count_val and count_val > 0:
        payload.target_count = count_val

    run_id = f"gen-run-{uuid.uuid4().hex[:8]}"
    llm = get_platform_provider()

    # 1. Deterministic Plan
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
        # Check if fallback was used inside generate_scenarios_for_agent
        if any(sc.provenance.get("generated_by") == "deterministic_builder" for sc in generated):
            generation_method = "deterministic"
            ai_status = "quota_exhausted"
            failure_reason = "Gemini API unavailable or quota exhausted. Fell back to deterministic builder."
    except Exception as e:
        logger.warning(f"Batch scenario generation error: {e}")
        from app.core.scenarios.scenario_generator import generate_scenarios_deterministically
        generated = generate_scenarios_deterministically(agent, plan)
        generation_method = "deterministic"
        ai_status = "failed"
        failure_reason = f"Gemini error: {e}. Fell back to deterministic builder."

    # 3. Deterministic Feasibility Validation
    validated = validate_scenarios_deterministically(generated, agent)
    
    # 4. Save Valid Scenarios to Store
    ready_count = 0
    blocked_count = 0
    rejected_count = 0

    for sc in validated:
        sc.agent_id = agent.id
        store.save_scenario(sc)
        if sc.status == "READY":
            ready_count += 1
        elif sc.status == "BLOCKED":
            blocked_count += 1
        elif sc.status == "REJECTED":
            rejected_count += 1

    # Status is PARTIAL if fallback/deterministic builder was used, FAILED only if generated is 0
    run_status = "COMPLETED" if (ready_count > 0 and ai_status == "success") else ("PARTIAL" if ready_count > 0 else "FAILED")

    return ScenarioGenerationRun(
        id=run_id,
        agent_id=agent.id,
        agent_version_id=agent.version_label,
        requested_count=payload.target_count,
        planned_count=len(plan.plan_items),
        generated_count=len(generated),
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
        scenarios=validated,
        created_at=dt.datetime.utcnow().isoformat() + "Z"
    )


@router.post("/generate", response_model=List[Scenario])
async def generate_and_validate_scenarios(payload: GenerateScenariosRequest):
    """Backward-compatible scenario generation endpoint."""
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    target_count = payload.count if payload.count is not None else payload.target_count
    if payload.category_counts:
        target_count = sum(payload.category_counts.values())

    gen_req = ScenarioGenerationRequest(
        agent_id=payload.agent_id,
        target_count=target_count,
        category_counts=payload.category_counts,
        user_instructions=payload.user_instructions
    )
    
    run_result = await execute_scenario_generation_run(gen_req)
    return run_result.scenarios


@router.get("/library", response_model=List[Scenario])
def list_scenario_library(agent_id: Optional[str] = None):
    scs = store.list_scenarios()
    if agent_id:
        scs = [scenario for scenario in scs if scenario.agent_id == agent_id]
    return scs


@router.get("/coverage/{agent_id}", response_model=CoverageGapReport)
def get_scenario_coverage_report(agent_id: str):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    scenarios = [scenario for scenario in store.list_scenarios() if scenario.agent_id == agent_id]
    return compute_coverage_gaps(agent, scenarios)
