"""
Root-Cause Failure Mode Clustering & Remediation Generator.
Groups raw failure verdicts into actionable semantic clusters with code/prompt fix recommendations.
"""

from __future__ import annotations

import uuid
from typing import Dict, List
from app.models.failure import RunVerdict, FailureCluster


def cluster_failure_verdicts(verdicts: List[RunVerdict]) -> List[FailureCluster]:
    """Groups failed verdicts by semantic root cause."""
    clusters_map: Dict[str, List[RunVerdict]] = {}

    for v in verdicts:
        if not v.passed and v.findings:
            cat = v.findings[0].category
            clusters_map.setdefault(cat, []).append(v)

    result_clusters: List[FailureCluster] = []

    fix_recommendations = {
        "UNAUTHORIZED_FINANCIAL_ACTION": "Enforce a strict hard monetary parameter gate (max_amount <= 10000) inside the Rule Engine before dispatching refund_order().",
        "DESTRUCTIVE_ACTION_WITHOUT_CONFIRMATION": "Add a mandatory two-step confirmation state gate for cancel_order() so execution requires explicit user 'YES'.",
        "INFINITE_TOOL_LOOP": "Implement exponential backoff with a max retry ceiling of 3 attempts in the Tool Gateway.",
        "SAFETY_POLICY_VIOLATION": "Harden system instructions with negative constraints against authority impersonation overrides."
    }

    for cat, members in clusters_map.items():
        sample_finding = members[0].findings[0]
        result_clusters.append(
            FailureCluster(
                id=f"cl-{uuid.uuid4().hex[:6]}",
                label=cat.replace("_", " ").title(),
                category=cat,
                member_verdict_ids=[m.trace_id for m in members],
                representative_evidence=sample_finding.evidence,
                count=len(members),
                severity=sample_finding.severity,
                recommended_fix=fix_recommendations.get(cat, "Refine agent system instructions and add input guardrail validation.")
            )
        )

    return result_clusters
