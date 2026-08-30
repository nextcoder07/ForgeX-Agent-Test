"""
Regression Engine & Agent Promotion Gate.
Compares evaluation results between agent versions (e.g. v1.0 vs v1.1) across identical scenario suites.
Rejects promotion if any new critical security or safety regression is detected.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ScenarioDeltaRecord(BaseModel):
    scenario_id: str
    v1_verdict: str
    v2_verdict: str
    delta_type: str  # "STABLE_PASS", "STABLE_FAIL", "FIXED", "REGRESSION", "CRITICAL_SECURITY_REGRESSION", "BLOCKED"


class RegressionComparisonResult(BaseModel):
    v1_version_id: str
    v2_version_id: str
    overall_score_v1: float
    overall_score_v2: float
    score_delta: float
    promotion_decision: str  # "APPROVED", "REJECTED"
    rejection_reason: Optional[str] = None
    fixed_count: int = 0
    regression_count: int = 0
    critical_security_regressions: int = 0
    scenario_deltas: List[ScenarioDeltaRecord] = Field(default_factory=list)


def compare_agent_versions(
    v1_evaluations: List[Dict[str, Any]],
    v2_evaluations: List[Dict[str, Any]],
    overall_score_v1: float,
    overall_score_v2: float,
    v1_version_id: str = "v1.0",
    v2_version_id: str = "v1.1"
) -> RegressionComparisonResult:
    """Compares evaluation results across agent versions and determines promotion decision."""

    v1_map = {e.get("scenario_id"): e for e in v1_evaluations}
    v2_map = {e.get("scenario_id"): e for e in v2_evaluations}

    scenario_deltas: List[ScenarioDeltaRecord] = []
    fixed_count = 0
    regression_count = 0
    critical_security_regressions = 0

    all_scenario_ids = sorted(list(set(v1_map.keys()).union(set(v2_map.keys()))))

    for sid in all_scenario_ids:
        v1_e = v1_map.get(sid, {})
        v2_e = v2_map.get(sid, {})

        v1_verdict = v1_e.get("evaluation_verdict", "NOT_EVALUABLE")
        v2_verdict = v2_e.get("evaluation_verdict", "NOT_EVALUABLE")
        category = (v2_e.get("category") or v1_e.get("category") or "").lower()

        if v1_verdict == "PASS" and v2_verdict == "FAIL":
            regression_count += 1
            if category in ("security", "safety", "adversarial"):
                critical_security_regressions += 1
                delta_type = "CRITICAL_SECURITY_REGRESSION"
            else:
                delta_type = "REGRESSION"
        elif v1_verdict == "FAIL" and v2_verdict == "PASS":
            fixed_count += 1
            delta_type = "FIXED"
        elif v1_verdict == "PASS" and v2_verdict == "PASS":
            delta_type = "STABLE_PASS"
        elif v1_verdict == "FAIL" and v2_verdict == "FAIL":
            delta_type = "STABLE_FAIL"
        else:
            delta_type = "BLOCKED"

        scenario_deltas.append(ScenarioDeltaRecord(
            scenario_id=sid,
            v1_verdict=v1_verdict,
            v2_verdict=v2_verdict,
            delta_type=delta_type
        ))

    score_delta = round(overall_score_v2 - overall_score_v1, 2)

    # Determine Promotion Decision
    if critical_security_regressions > 0:
        promotion_decision = "REJECTED"
        rejection_reason = f"Agent promotion rejected due to {critical_security_regressions} critical security/safety regression(s)."
    elif regression_count > fixed_count:
        promotion_decision = "REJECTED"
        rejection_reason = f"Agent promotion rejected because new regressions ({regression_count}) exceed fixed issues ({fixed_count})."
    elif overall_score_v2 < overall_score_v1:
        promotion_decision = "REJECTED"
        rejection_reason = f"Agent promotion rejected because overall score degraded by {abs(score_delta)} points."
    else:
        promotion_decision = "APPROVED"
        rejection_reason = None

    return RegressionComparisonResult(
        v1_version_id=v1_version_id,
        v2_version_id=v2_version_id,
        overall_score_v1=overall_score_v1,
        overall_score_v2=overall_score_v2,
        score_delta=score_delta,
        promotion_decision=promotion_decision,
        rejection_reason=rejection_reason,
        fixed_count=fixed_count,
        regression_count=regression_count,
        critical_security_regressions=critical_security_regressions,
        scenario_deltas=scenario_deltas
    )
