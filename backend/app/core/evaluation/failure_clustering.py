"""
Root-Cause Failure Mode Clustering & Remediation Generator.
Groups raw failure verdicts into actionable semantic clusters with root cause patterns and code/prompt fix recommendations.
"""

from __future__ import annotations

import uuid
from typing import Dict, List
from app.models.failure import RunVerdict, FailureCluster


def cluster_failure_verdicts(job_id: str | List[RunVerdict], verdicts: List[RunVerdict] | str = None) -> List[FailureCluster]:
    """Groups failed verdicts by semantic root cause pattern."""
    if isinstance(job_id, list):
        # Called as cluster_failure_verdicts(verdicts, evaluation_id)
        actual_verdicts: List[RunVerdict] = job_id
        evaluation_id: str = str(verdicts) if isinstance(verdicts, str) else ""
    else:
        # Called as cluster_failure_verdicts(job_id, verdicts)
        evaluation_id: str = str(job_id) if job_id else ""
        actual_verdicts: List[RunVerdict] = verdicts if isinstance(verdicts, list) else []

    clusters_map: Dict[str, List[RunVerdict]] = {}

    for v in actual_verdicts:
        if (not v.passed or v.status != "PASS") and v.findings:
            for finding in v.findings:
                # Root cause pattern key based on category, source, and evidence surface
                root_cause_key = f"{finding.category}:{finding.source}"
                clusters_map.setdefault(root_cause_key, []).append(v)

    result_clusters: List[FailureCluster] = []

    fix_recommendations = {
        "UNAUTHORIZED_FINANCIAL_ACTION": "Enforce a strict hard monetary parameter gate (max_amount <= 10000) inside the Rule Engine before dispatching refund_order().",
        "UNAUTHORIZED_PAYOUT": "Enforce a strict hard monetary parameter gate (max_amount <= 10000) inside the Rule Engine before dispatching refund_order().",
        "UNAUTHORIZED_TOOL_INVOCATION": "Enforce strict hard policy gates in Rule Engine before dispatching restricted tool capability.",
        "DESTRUCTIVE_ACTION_WITHOUT_CONFIRMATION": "Add a mandatory two-step confirmation state gate for cancel_order() so execution requires explicit user 'YES'.",
        "INFINITE_TOOL_LOOP": "Implement exponential backoff with a max retry ceiling of 3 attempts in the Tool Gateway.",
        "EXCESSIVE_TOOL_CALLS": "Implement exponential backoff with a max retry ceiling of 3 attempts in the Tool Gateway.",
        "SAFETY_POLICY_VIOLATION": "Harden system instructions with negative constraints against authority impersonation overrides.",
        "PROMPT_INJECTION_DETECTED": "Add prompt injection input sanitizer and strict instruction boundary isolation.",
        "MISSING_EXPECTED_OUTPUT": "Reinforce user instruction guidelines and response format rules in system prompt.",
        "INCORRECT_TOOL_ARGUMENTS": "Validate tool parameter types and required fields before API dispatch."
    }

    for root_key, members in clusters_map.items():
        sample_finding = members[0].findings[0]
        cat = sample_finding.category
        affected_scenarios = list(dict.fromkeys([m.scenario_id for m in members]))
        verdict_ids = list(dict.fromkeys([m.id or m.trace_id for m in members]))
        title_text = sample_finding.title or cat.replace("_", " ").title()
        rec_fix = fix_recommendations.get(cat, "Refine agent system instructions and add input guardrail validation.")

        result_clusters.append(
            FailureCluster(
                id=f"cl-{uuid.uuid4().hex[:6]}",
                evaluation_id=evaluation_id,
                label=title_text,
                title=title_text,
                category=cat,
                root_cause_pattern=root_key,
                member_verdict_ids=[m.trace_id for m in members],
                verdict_ids=verdict_ids,
                affected_scenarios=affected_scenarios,
                representative_evidence=sample_finding.evidence or sample_finding.description,
                count=len(members),
                occurrences=len(members),
                severity=sample_finding.severity,
                recommended_fix=rec_fix,
                remediation_suggestion=rec_fix,
                failure_surface=sample_finding.evidence_type,
                workflow_node="tool_executor" if sample_finding.evidence_type == "tool_call" else "system_prompt"
            )
        )

    return result_clusters
