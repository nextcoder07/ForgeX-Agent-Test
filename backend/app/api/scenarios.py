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
    validated: List[Scenario] = []

    # Step 1: Generate Scenarios
    try:
        # 1. Generate
        generated = await generate_scenarios_for_agent(agent, strategy, llm)
        # 2. Critic
        critiqued = await critique_scenarios(generated, agent, llm)
        # 3. Deterministic Validation
        validated = validate_scenarios_deterministically(critiqued, agent)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Scenario generation failed, filling up with blocked items: {e}")

    for scenario in validated:
        scenario.agent_id = agent.id

    # 4. Fill up any missing scenarios to meet the requested target_count
    total_target = payload.target_count
    if len(validated) < total_target:
        from app.models.scenario import ScenarioCategory
        import uuid
        categories = list(ScenarioCategory)
        missing_count = total_target - len(validated)
        
        for i in range(missing_count):
            cat = categories[i % len(categories)]
            dummy_id = f"SC-FAIL-{uuid.uuid4().hex[:6]}".upper()
            dummy_sc = Scenario(
                id=dummy_id,
                agent_id=agent.id,
                version=1,
                category=cat,
                title=f"Generation Failed ({cat.value.title()})",
                purpose="This scenario could not be generated. Rest cannot be done so leave that.",
                user_messages=["Rest of scenarios cannot be generated"],
                initial_state={},
                required_capabilities=[],
                fault_injections=[],
                assertions=[],
                critic_passed=False,
                critic_notes="Quota/model limitation or parsing error. Rest cannot be done so leave that.",
                validation_status="FAILED_GENERATION",
                rationale="Rest cannot be done so leave that."
            )
            validated.append(dummy_sc)

    # Save to store
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
