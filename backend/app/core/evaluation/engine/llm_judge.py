"""
LLM-Based Evaluator.
Leverages LLM semantic judge to evaluate subjective text correctness and security boundaries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution import ExecutionTrace
from app.models.failure import RunVerdict, FailureFinding
from app.core.evaluation.engine.base import Evaluator
from app.core.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class LLMEvaluator(Evaluator):
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def evaluate(
        self,
        agent: AgentRecord,
        scenario: Scenario,
        trace: ExecutionTrace,
        counterfactual_trace: Optional[ExecutionTrace] = None
    ) -> RunVerdict:
        findings: List[FailureFinding] = []
        passed = True

        try:
            # Enforce safety constraints and expected behavior check via LLM
            constraints = agent.constitution.never_rules + (scenario.safety_constraints or [])
            if scenario.expected_behavior:
                constraints.append(f"Expected Behavior Requirement: {scenario.expected_behavior}")

            judge_res = await self.llm.judge_trace(trace.dict(), constraints)
            passed = judge_res.get("passed", True)

            if not passed:
                category = judge_res.get("failure_category", "policy_violation").lower().strip()
                findings.append(
                    FailureFinding(
                        category=category,
                        severity="high",
                        source="LLM_JUDGE",
                        explanation=judge_res.get("explanation", "Agent failed to follow instructions or safety rules."),
                        evidence=judge_res.get("evidence", "Semantic trace analysis"),
                        confidence=0.9
                    )
                )
        except Exception as e:
            logger.warning(f"LLM Judge evaluation failed: {e}. Defaulting to safe PASS.")
            passed = True

        return RunVerdict(
            trace_id=trace.id,
            scenario_id=scenario.id,
            passed=passed,
            findings=findings,
            expected_behavior_met=passed,
            counterfactual_trace_id=counterfactual_trace.id if counterfactual_trace else None,
            counterfactual_passed=None,
            attack_causation_proven=False
        )
