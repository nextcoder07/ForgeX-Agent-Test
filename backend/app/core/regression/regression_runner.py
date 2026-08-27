"""
Regression Benchmarking and Version Comparison Runner.
Compares original agent baseline (v1.0) against patched/repaired version (v1.1)
across identical scenario suites, identifying fixed failures, persistent defects, and regressions.
"""

from __future__ import annotations

import uuid
import datetime as dt
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.failure import RunVerdict
from app.models.evaluation import ReliabilityScorecard
from app.services.store import store

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class ScenarioComparisonItem(BaseModel):
    scenario_id: str
    scenario_title: str
    category: str
    baseline_passed: bool
    repaired_passed: bool
    status: str  # "FIXED", "REGRESSED", "STABLE_PASS", "PERSISTENT_FAIL"
    baseline_finding: Optional[str] = None
    repaired_finding: Optional[str] = None


class RegressionComparisonReport(BaseModel):
    id: str = Field(default_factory=lambda: f"reg-comp-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_name: str
    baseline_version: str = "v1.0"
    repaired_version: str = "v1.1"
    baseline_evaluation_id: str
    repaired_evaluation_id: str
    
    # High-level Metrics
    baseline_score: float
    repaired_score: float
    score_delta: float
    
    # Test Counts
    total_scenarios: int
    baseline_passed: int
    repaired_passed: int
    fixed_count: int
    regressions_count: int
    persistent_fail_count: int
    
    # Critical Issues
    baseline_critical: int
    repaired_critical: int
    critical_delta: int
    
    # Dimension Comparison
    dimension_deltas: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    
    # Detailed Item Comparisons
    scenario_comparisons: List[ScenarioComparisonItem] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class RegressionRunner:
    """Computes rigorous before-vs-after regression diffs between two agent versions."""

    def compare_evaluations(
        self,
        agent: AgentRecord,
        baseline_eval_id: str,
        repaired_eval_id: str,
        baseline_version: str = "v1.0",
        repaired_version: str = "v1.1"
    ) -> RegressionComparisonReport:
        baseline_scorecard: Optional[ReliabilityScorecard] = store.get_scorecard(baseline_eval_id)
        repaired_scorecard: Optional[ReliabilityScorecard] = store.get_scorecard(repaired_eval_id)

        baseline_verdicts: List[RunVerdict] = store.verdicts.get(baseline_eval_id, [])
        repaired_verdicts: List[RunVerdict] = store.verdicts.get(repaired_eval_id, [])

        scenarios = {s.id: s for s in store.list_scenarios() if s.agent_id == agent.id}

        base_v_map = {v.scenario_id: v for v in baseline_verdicts}
        rep_v_map = {v.scenario_id: v for v in repaired_verdicts}

        all_scenario_ids = list(set(list(base_v_map.keys()) + list(rep_v_map.keys())))
        if not all_scenario_ids:
            all_scenario_ids = list(scenarios.keys())

        scenario_comps: List[ScenarioComparisonItem] = []
        fixed_count = 0
        regressions_count = 0
        persistent_fail = 0

        for sc_id in all_scenario_ids:
            sc = scenarios.get(sc_id)
            title = sc.title if sc else sc_id
            category = sc.category.value if (sc and hasattr(sc.category, "value")) else "NORMAL"

            bv = base_v_map.get(sc_id)
            rv = rep_v_map.get(sc_id)

            b_passed = bv.passed if bv else True
            r_passed = rv.passed if rv else True

            b_finding = bv.findings[0].title if (bv and bv.findings) else None
            r_finding = rv.findings[0].title if (rv and rv.findings) else None

            if not b_passed and r_passed:
                status = "FIXED"
                fixed_count += 1
            elif b_passed and not r_passed:
                status = "REGRESSED"
                regressions_count += 1
            elif not b_passed and not r_passed:
                status = "PERSISTENT_FAIL"
                persistent_fail += 1
            else:
                status = "STABLE_PASS"

            scenario_comps.append(ScenarioComparisonItem(
                scenario_id=sc_id,
                scenario_title=title,
                category=category,
                baseline_passed=b_passed,
                repaired_passed=r_passed,
                status=status,
                baseline_finding=b_finding,
                repaired_finding=r_finding
            ))

        base_comp = baseline_scorecard.composite if baseline_scorecard else 0.0
        rep_comp = repaired_scorecard.composite if repaired_scorecard else 0.0
        score_delta = round(rep_comp - base_comp, 2)

        base_crit = baseline_scorecard.critical_failures if baseline_scorecard else 0
        rep_crit = repaired_scorecard.critical_failures if repaired_scorecard else 0
        crit_delta = rep_crit - base_crit

        # Dimension breakdown
        dimension_deltas: Dict[str, Dict[str, float]] = {}
        if baseline_scorecard and repaired_scorecard:
            dim_keys = ["correctness", "safety", "robustness", "tool_discipline", "goal_adherence"]
            for dim in dim_keys:
                b_val = getattr(baseline_scorecard, dim, 0.0) or 0.0
                r_val = getattr(repaired_scorecard, dim, 0.0) or 0.0
                dimension_deltas[dim] = {
                    "baseline": round(float(b_val), 1),
                    "repaired": round(float(r_val), 1),
                    "delta": round(float(r_val - b_val), 1)
                }

        report = RegressionComparisonReport(
            agent_id=agent.id,
            agent_name=agent.name,
            baseline_version=baseline_version,
            repaired_version=repaired_version,
            baseline_evaluation_id=baseline_eval_id,
            repaired_evaluation_id=repaired_eval_id,
            baseline_score=base_comp,
            repaired_score=rep_comp,
            score_delta=score_delta,
            total_scenarios=len(scenario_comps),
            baseline_passed=sum(1 for s in scenario_comps if s.baseline_passed),
            repaired_passed=sum(1 for s in scenario_comps if s.repaired_passed),
            fixed_count=fixed_count,
            regressions_count=regressions_count,
            persistent_fail_count=persistent_fail,
            baseline_critical=base_crit,
            repaired_critical=rep_crit,
            critical_delta=crit_delta,
            dimension_deltas=dimension_deltas,
            scenario_comparisons=scenario_comps
        )
        return report
