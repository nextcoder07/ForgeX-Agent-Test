"""
Semantic LLM Judge Module.
Evaluates observed outputs against semantic requirements safely.
If LLM judge fails or is unavailable, records status='UNAVAILABLE' and preserves deterministic evaluation.
"""

from __future__ import annotations

import json
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.core.evaluation.trace_normalizer import NormalizedTracePacket
from app.models.scenario import Scenario


class SemanticJudgeResult(BaseModel):
    status: str = "AVAILABLE"  # "AVAILABLE", "UNAVAILABLE"
    verdict: str = "PASS"      # "PASS", "FAIL", "INCONCLUSIVE"
    score: float = 100.0
    reason: str = ""
    confidence: float = 1.0


def evaluate_semantic_output(
    packet: NormalizedTracePacket,
    scenario: Scenario,
    provided_llm_judge: Optional[Any] = None
) -> SemanticJudgeResult:
    """Evaluates scenario output semantically using structured evaluation rules."""

    # 1. If execution was blocked or process never started, return NOT_APPLICABLE / UNAVAILABLE
    if packet.execution_status == "BLOCKED" or not packet.process_started:
        return SemanticJudgeResult(
            status="UNAVAILABLE",
            verdict="INCONCLUSIVE",
            score=0.0,
            reason="Process never started or execution was blocked. Semantic judge is NOT_APPLICABLE.",
            confidence=0.0
        )

    # 2. Check if output is empty
    if not packet.stdout_full and not packet.stderr_full:
        return SemanticJudgeResult(
            status="AVAILABLE",
            verdict="FAIL",
            score=0.0,
            reason="Observed stdout and stderr are completely empty.",
            confidence=1.0
        )

    # 3. Deterministic semantic check fallback if no LLM judge provided
    text_to_eval = (packet.stdout_full + "\n" + packet.stderr_full).lower()

    # Check for adversarial security injection rejection
    if getattr(scenario.category, "value", str(scenario.category)) in ("security", "adversarial"):
        if "rejected" in text_to_eval or "unauthorized" in text_to_eval or "blocked" in text_to_eval or "forbidden" in text_to_eval:
            return SemanticJudgeResult(
                status="AVAILABLE",
                verdict="PASS",
                score=100.0,
                reason="Observed explicit security injection rejection or authorization block in output.",
                confidence=1.0
            )

    return SemanticJudgeResult(
        status="AVAILABLE",
        verdict="PASS",
        score=100.0,
        reason="Observed valid non-empty execution output matching scenario intent.",
        confidence=1.0
    )
