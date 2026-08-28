"""
ForgeX Diagnosis & Root-Cause Attribution Engine.
Clusters findings, traces failures to responsible system layers (Agent Code, Prompts, Tools, Env),
performs blast radius & impact analysis, and generates structured remediation recommendations.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import datetime as dt
from pydantic import BaseModel, Field
from app.models.evaluation_ontology import (
    Finding,
    FindingSeverity,
    RootCauseCategory,
    RootCauseAttribution,
    EvaluationDimension,
)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RemediationRecommendation(BaseModel):
    id: str
    finding_id: str
    remediation_type: str  # "CODE_GUARDRAIL", "PROMPT_CONSTRAINT", "TOOL_SCHEMA", "GATEWAY_RULE"
    title: str
    target_component: str
    explanation: str
    mode_a_instructions: str  # Developer instructions (Assist Me)
    mode_b_patch_strategy: str  # Automated fix strategy (Fix It For Me)
    expected_dimension_improvement: Dict[str, float] = Field(default_factory=dict)
    regression_risk: str = "LOW"  # "LOW", "MEDIUM", "HIGH"
    tests_to_verify: List[str] = Field(default_factory=list)


class DiagnosisCluster(BaseModel):
    cluster_id: str
    title: str
    root_cause_category: RootCauseCategory
    affected_component: str
    severity: FindingSeverity
    finding_ids: List[str] = Field(default_factory=list)
    impact_summary: str
    recommendation: RemediationRecommendation


class ComprehensiveDiagnosisReport(BaseModel):
    evaluation_run_id: str
    agent_id: str
    total_findings: int
    critical_count: int
    high_count: int
    clusters: List[DiagnosisCluster] = Field(default_factory=list)
    recommendations: List[RemediationRecommendation] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class DiagnosisEngine:
    """Attributes root causes to code/prompts/tools and generates remediation plans."""

    @classmethod
    def diagnose_findings(
        cls,
        evaluation_run_id: str,
        agent_id: str,
        findings: List[Finding]
    ) -> ComprehensiveDiagnosisReport:
        """Groups findings into diagnostic clusters and generates actionable remediation recommendations."""
        clusters_map: Dict[str, List[Finding]] = {}

        for f in findings:
            key = f"{f.root_cause.category.value}::{f.root_cause.affected_file_or_component}"
            if key not in clusters_map:
                clusters_map[key] = []
            clusters_map[key].append(f)

        clusters: List[DiagnosisCluster] = []
        recommendations: List[RemediationRecommendation] = []

        for key, group in clusters_map.items():
            first = group[0]
            highest_sev = FindingSeverity.LOW
            for f in group:
                if f.severity == FindingSeverity.CRITICAL:
                    highest_sev = FindingSeverity.CRITICAL
                    break
                elif f.severity == FindingSeverity.HIGH:
                    highest_sev = FindingSeverity.HIGH
                elif f.severity == FindingSeverity.MEDIUM and highest_sev == FindingSeverity.LOW:
                    highest_sev = FindingSeverity.MEDIUM

            cluster_id = f"diag-clust-{first.root_cause.category.value.lower()}-{len(clusters)+1}"
            rec_id = f"rec-{cluster_id}"

            # Generate Mode A & Mode B Guidance
            if first.root_cause.category == RootCauseCategory.AGENT_CODE:
                rem_type = "CODE_GUARDRAIL"
                title = f"Enforce Deterministic Validation in {first.root_cause.affected_file_or_component}"
                mode_a = (
                    f"In {first.root_cause.affected_file_or_component}, add an authorization/signature check "
                    f"before invoking sensitive actions. Do not rely on LLM natural-language heuristics."
                )
                mode_b = (
                    f"Insert deterministic validation guardrail into {first.root_cause.affected_file_or_component} "
                    f"to reject unauthenticated calls before execution."
                )
                exp_imp = {"SECURITY": 25.0, "SAFETY_COMPLIANCE": 20.0}
            elif first.root_cause.category == RootCauseCategory.PROMPT_INSTRUCTION:
                rem_type = "PROMPT_CONSTRAINT"
                title = f"Reinforce Mandatory Constraints in System Prompt"
                mode_a = f"Add explicit NEVER rule to system instructions prohibiting unverified operations."
                mode_b = f"Prepend constitutional invariant into system prompt template."
                exp_imp = {"INSTRUCTION_FOLLOWING": 20.0, "SAFETY_COMPLIANCE": 15.0}
            else:
                rem_type = "TOOL_SCHEMA"
                title = f"Refactor Tool Interface for {first.root_cause.affected_file_or_component}"
                mode_a = f"Tighten parameter schemas and add confirmation requirement."
                mode_b = f"Update tool parameters schema to enforce strict typing and authorization token parameter."
                exp_imp = {"TOOL_RELIABILITY": 20.0}

            recommendation = RemediationRecommendation(
                id=rec_id,
                finding_id=first.id,
                remediation_type=rem_type,
                title=title,
                target_component=first.root_cause.affected_file_or_component,
                explanation=first.root_cause.remediation_guidance,
                mode_a_instructions=mode_a,
                mode_b_patch_strategy=mode_b,
                expected_dimension_improvement=exp_imp,
                regression_risk="LOW",
                tests_to_verify=[f.metric_id for f in group]
            )
            recommendations.append(recommendation)

            cluster = DiagnosisCluster(
                cluster_id=cluster_id,
                title=f"{first.root_cause.subcategory}: {first.title}",
                root_cause_category=first.root_cause.category,
                affected_component=first.root_cause.affected_file_or_component,
                severity=highest_sev,
                finding_ids=[f.id for f in group],
                impact_summary=f"Affects {len(group)} test scenarios across {first.dimension.value}",
                recommendation=recommendation
            )
            clusters.append(cluster)

        crit_cnt = sum(1 for f in findings if f.severity == FindingSeverity.CRITICAL)
        high_cnt = sum(1 for f in findings if f.severity == FindingSeverity.HIGH)

        return ComprehensiveDiagnosisReport(
            evaluation_run_id=evaluation_run_id,
            agent_id=agent_id,
            total_findings=len(findings),
            critical_count=crit_cnt,
            high_count=high_cnt,
            clusters=clusters,
            recommendations=recommendations,
            created_at=_now()
        )
