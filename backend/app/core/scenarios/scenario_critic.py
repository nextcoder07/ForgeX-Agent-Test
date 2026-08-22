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

from app.core.llm.gemini_provider import LLMGenerationError, LLMQuotaExhaustedError

logger = logging.getLogger(__name__)


async def critique_scenarios(
    scenarios: List[Scenario],
    agent: AgentRecord,
    llm: LLMProvider
) -> List[Scenario]:
    """Runs each scenario through the critic filter."""
    critiqued: List[Scenario] = []
    quota_exhausted = False

    for sc in scenarios:
        if quota_exhausted:
            sc.critic_notes = "Critic review skipped due to Gemini API quota exhaustion."
            sc.validation_status = "UNREVIEWED_QUOTA_EXHAUSTED"
            critiqued.append(sc)
            continue

        try:
            critic_res = await llm.critique(sc.dict(), agent.dict())
            passed = critic_res.get("passed", True)
            notes = critic_res.get("notes", "Scenario validated as relevant and executable.")

            sc.critic_passed = passed
            sc.critic_notes = notes
            if not passed:
                sc.validation_status = "REJECTED_CRITIC"
            critiqued.append(sc)
        except (LLMQuotaExhaustedError, LLMGenerationError) as err:
            logger.warning(f"Critic call failed for scenario {sc.id} due to LLM error: {err}")
            quota_exhausted = True
            sc.critic_notes = f"Critic review skipped due to Gemini API quota exhaustion ({str(err)[:80]})"
            sc.validation_status = "UNREVIEWED_QUOTA_EXHAUSTED"
            critiqued.append(sc)
        except Exception as err:
            logger.warning(f"Critic call failed for scenario {sc.id}: {err}")
            sc.critic_notes = f"Critic review skipped due to error: {str(err)[:80]}"
            critiqued.append(sc)

    return critiqued
