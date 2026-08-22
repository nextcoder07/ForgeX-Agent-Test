"""
Scenario Intelligence, Planning, Generation, Critic, and Coverage Gap API Router.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.scenario import Scenario, ScenarioCategory, StrategyPlan, CoverageGapReport
from app.services.store import store
from app.core.scenarios.strategy_planner import build_test_strategy
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.scenarios.scenario_critic import critique_scenarios
from app.core.scenarios.scenario_validator import validate_scenarios_deterministically
from app.core.scenarios.coverage_engine import compute_coverage_gaps
import logging
from app.core.llm.gemini_provider import GeminiProvider, LLMGenerationError, LLMQuotaExhaustedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class GenerateScenariosRequest(BaseModel):
    agent_id: str
    target_count: int = 25
    scenario_type: Optional[str] = None  # e.g. "normal", "adversarial", "security", "tool_misuse"
    count: Optional[int] = None           # Alias for target_count
    difficulty: Optional[str] = None      # "easy", "medium", "hard"
    configuration: Optional[Dict[str, Any]] = None


@router.get("/strategy/{agent_id}", response_model=StrategyPlan)
def get_test_strategy(agent_id: str):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return build_test_strategy(agent)


@router.post("/generate", response_model=List[Scenario])
async def generate_and_validate_scenarios(payload: GenerateScenariosRequest):
    agent = store.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")

    target_count = payload.count if payload.count is not None else payload.target_count
    strategy = build_test_strategy(agent, desired_count=target_count)
    llm = GeminiProvider()

    # Step 1: Generate Scenarios
    try:
        scenarios = await generate_scenarios_for_agent(agent, strategy, llm)
    except LLMQuotaExhaustedError as e:
        logger.warning(f"Scenario generation aborted due to Gemini quota exhaustion: {e}")
        raise HTTPException(
            status_code=429,
            detail=f"Gemini API quota exhausted (429 RESOURCE_EXHAUSTED). Please try again later."
        )
    except Exception as e:
        logger.error(f"Scenario generation failed due to LLM provider error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scenario generation failed due to LLM provider error: {str(e)}"
        )

    if not scenarios:
        raise HTTPException(status_code=500, detail="Failed to generate any valid test scenarios.")

    for sc in scenarios:
        sc.agent_id = agent.id

    # Step 2: IMMEDIATELY save valid scenarios to store & Supabase
    # Ensures scenarios are never lost even if subsequent critic/validation LLM calls fail.
    for sc in scenarios:
        store.save_scenario(sc)

    # Step 3: Run Critic Evaluation
    try:
        scenarios = await critique_scenarios(scenarios, agent, llm)
    except (LLMQuotaExhaustedError, LLMGenerationError) as quota_err:
        logger.warning(f"Critic review phase skipped/truncated due to LLM quota limit: {quota_err}")
        for sc in scenarios:
            if not sc.critic_notes or sc.critic_notes == "Scenario validated as relevant and executable.":
                sc.critic_notes = "Critic review skipped due to Gemini API quota limit."
                sc.validation_status = "UNREVIEWED_QUOTA_EXHAUSTED"
    except Exception as critic_err:
        logger.warning(f"Critic review phase error: {critic_err}")

    # Step 4: Deterministic Validation
    validated = validate_scenarios_deterministically(scenarios, agent)

    # Step 5: Filter by scenario_type if specified
    if payload.scenario_type and payload.scenario_type.lower() != "all":
        stype = payload.scenario_type.lower().replace("-", "_").replace(" ", "_")
        filtered = [sc for sc in validated if sc.category.value.lower() == stype or stype in sc.category.value.lower()]
        if filtered:
            validated = filtered

    # Step 6: Persist updated scenario records (with final critic/validation status)
    for sc in validated:
        store.save_scenario(sc)

    return validated


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
