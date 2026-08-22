"""
2nd-Pass LLM Scenario Critic.
Evaluates proposed test scenarios for relevance, executability, non-duplication, and sandbox safety.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from app.models.scenario import Scenario
from app.models.agent import AgentRecord
from app.core.llm.base import LLMProvider

logger = logging.getLogger(__name__)


async def critique_scenarios(
    scenarios: List[Scenario],
    agent: AgentRecord,
    llm: LLMProvider
) -> List[Scenario]:
    """Runs each scenario through the critic filter."""
    critiqued: List[Scenario] = []

    for sc in scenarios:
        critic_res = await llm.critique(sc.dict(), agent.dict())
        passed = critic_res.get("passed", True)
        notes = critic_res.get("notes", "Scenario validated as relevant and executable.")

        sc.critic_passed = passed
        sc.critic_notes = notes
        if not passed:
            sc.validation_status = "REJECTED_CRITIC"

        critiqued.append(sc)

    return critiqued
