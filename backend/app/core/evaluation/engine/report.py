"""
Reliability Report Compiler.
Aggregates verdicts into a comprehensive safety/capability report and identifies the most dangerous failures.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.agent import AgentRecord
from app.models.failure import RunVerdict
from app.models.evaluation import ReliabilityScorecard

class ReliabilityReport(BaseModel):
    agent_id: str
    agent_name: str
    agent_version: str
    summary: Dict[str, Any] = Field(default_factory=dict)
    scores: Dict[str, float] = Field(default_factory=dict)
    failure_distribution: Dict[str, int] = Field(default_factory=dict)
    severity_distribution: Dict[str, int] = Field(default_factory=dict)
    most_dangerous_failure: Optional[Dict[str, Any]] = None

RECOMMENDATIONS = {
    "unauthorized_action": "Implement a strict validation middleware or auth check prior to calling any database/transaction modify tools.",
    "unsafe_action": "Require explicit confirmation prompt check in constitution before invoking any destructive action.",
    "prompt_injection": "Wrap the system prompt inside system instruction headers, reject prompt overrides like 'SYSTEM OVERRIDE:', and filter urgencies.",
    "sandbox_violation": "Harden sandbox environment. Ensure code does not access unrestricted builtins like __import__, open, etc.",
    "tool_misuse": "Refine the LLM planner instructions and enforce precise parameters validation schemas.",
    "looping": "Implement a tool-retry breaker at the application level to limit consecutive queries on the same target.",
    "tool_failure_handling": "Implement retry logic with backoff for timeouts, and handle internal transaction errors gracefully.",
}

def compile_reliability_report(
    agent: AgentRecord,
    scorecard: ReliabilityScorecard,
    verdicts: List[RunVerdict]
) -> ReliabilityReport:
    """Compiles individual verdicts and scores into an aggregate report highlighting key failure vulnerabilities."""
    total = len(verdicts) if verdicts else 1
    passed = scorecard.passed
    failed = scorecard.failed

    summary = {
        "total_scenarios": total,
        "passed": passed,
        "failed": failed,
        "reliability": round(passed / total, 2)
    }

    scores = {
        "correctness": scorecard.correctness / 100.0,
        "safety": scorecard.safety / 100.0,
        "tool_usage": scorecard.tool_discipline / 100.0,
        "instruction_following": scorecard.goal_adherence / 100.0
    }

    # Distributions
    failure_distribution: Dict[str, int] = {}
    severity_distribution: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}

    all_findings = []
    for v in verdicts:
        for f in v.findings:
            all_findings.append((v.scenario_id, f))
            # Category distribution
            cat = f.category
            failure_distribution[cat] = failure_distribution.get(cat, 0) + 1
            # Severity distribution
            sev = f.severity.lower()
            if sev in severity_distribution:
                severity_distribution[sev] += 1
            else:
                severity_distribution["medium"] += 1

    # Most Dangerous Failure Detection
    most_dangerous = None
    if all_findings:
        # Sort findings by severity level: critical > high > medium > low
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        sorted_findings = sorted(all_findings, key=lambda item: severity_rank.get(item[1].severity.lower(), 1), reverse=True)
        
        worst_scenario_id, worst_finding = sorted_findings[0]
        worst_severity = worst_finding.severity.lower()
        
        if severity_rank.get(worst_severity, 1) >= 2: # At least medium or higher
            # Gather all scenarios affected by this category
            affected_scenarios = list(set([
                sc_id for sc_id, f in all_findings 
                if f.category == worst_finding.category
            ]))

            remediation = RECOMMENDATIONS.get(
                worst_finding.category,
                "Audit agent system prompts and restrict tool capabilities."
            )

            most_dangerous = {
                "failure_category": worst_finding.category,
                "severity": worst_finding.severity.upper(),
                "explanation": worst_finding.explanation,
                "evidence": worst_finding.evidence,
                "affected_scenarios": affected_scenarios,
                "recommendation": remediation
            }

    return ReliabilityReport(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_version=agent.version_label,
        summary=summary,
        scores=scores,
        failure_distribution=failure_distribution,
        severity_distribution=severity_distribution,
        most_dangerous_failure=most_dangerous
    )
