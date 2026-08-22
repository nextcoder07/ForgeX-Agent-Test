"""
Scenario Intelligence, Planning, Generation, Critic, and Coverage Gap API Router.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.scenario import Scenario, StrategyPlan, CoverageGapReport
from app.services.store import store
from app.core.scenarios.strategy_planner import build_test_strategy
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.scenarios.scenario_critic import critique_scenarios
from app.core.scenarios.scenario_validator import validate_scenarios_deterministically
from app.core.scenarios.coverage_engine import compute_coverage_gaps
from app.core.llm.gemini_provider import GeminiProvider

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class GenerateScenariosRequest(BaseModel):
    agent_id: str
    target_count: int = 25


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

    strategy = build_test_strategy(agent, desired_count=payload.target_count)
    llm = GeminiProvider()

    try:
        # 1. Generate
        generated = await generate_scenarios_for_agent(agent, strategy, llm)
        # 2. Critic
        critiqued = await critique_scenarios(generated, agent, llm)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Scenario generation failed due to LLM provider error: {str(e)}"
        )
        
    # 3. Deterministic Validation
    validated = validate_scenarios_deterministically(critiqued, agent)

    for scenario in validated:
        scenario.agent_id = agent.id

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
