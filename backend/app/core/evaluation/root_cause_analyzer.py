"""
Root-Cause Analysis (RCA) & Failure Clustering Engine.
Disambiguates execution symptoms from root causes and groups related scenario failures
into structured root-cause clusters.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.core.evaluation.trace_normalizer import NormalizedTracePacket
from app.models.scenario import Scenario


class FailureFindingRecord(BaseModel):
    scenario_id: str
    category: str      # "DEPENDENCY", "CREDENTIAL", "MODEL", "TOOL_DISCIPLINE", "WORKFLOW", "SAFETY_SECURITY", "AGENT_EXCEPTION", "TIMEOUT"
    subcategory: str
    severity: str      # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    symptom: str
    root_cause: str
    affected_component: str
    remediation: str
    evidence_ids: List[str] = Field(default_factory=list)


class FailureCluster(BaseModel):
    cluster_id: str
    root_cause: str
    category: str
    severity: str
    affected_scenarios: List[str] = Field(default_factory=list)
    frequency: int = 0
    suggested_remediation: str = ""


def analyze_scenario_failure(
    packet: NormalizedTracePacket,
    scenario: Scenario,
    assertion_findings: List[Any]
) -> Optional[FailureFindingRecord]:
    """Analyzes a failed scenario execution trace to extract root cause and remediation."""

    if packet.execution_status == "BLOCKED":
        return FailureFindingRecord(
            scenario_id=scenario.id,
            category="CREDENTIAL" if "CREDENTIAL" in packet.stderr_full else "DEPENDENCY",
            subcategory="PREFLIGHT_BLOCKED",
            severity="HIGH",
            symptom="Preflight execution blocked before process start.",
            root_cause=packet.stderr_full or "Missing required credential or runtime package.",
            affected_component="Preflight Runtime Provisioner",
            remediation="Provide the required API key or environment credential.",
            evidence_ids=[f"ev-{e.event_index}" for e in packet.normalized_events if e.event_type == "PREFLIGHT"]
        )

    # Check for Tool Discipline Failure
    tool_astn = next((f for f in assertion_findings if getattr(f, "assertion_type", "") in ("TOOL_CALLED", "TOOL_INVOKED") and not getattr(f, "passed", True)), None)
    if tool_astn:
        return FailureFindingRecord(
            scenario_id=scenario.id,
            category="TOOL_DISCIPLINE",
            subcategory="TOOL_MISMATCH",
            severity="HIGH",
            symptom=f"Target tool '{getattr(tool_astn, 'expected', '')}' was not called by agent.",
            root_cause=f"Agent reasoning selected alternative tool or failed to invoke tool discipline contract.",
            affected_component="Tool Router / Reasoning Surface",
            remediation="Update agent prompt instructions to reinforce tool selection guidelines.",
            evidence_ids=[f"ev-{e.event_index}" for e in packet.normalized_events if e.event_type == "TOOL_CALL"]
        )

    # Check for Unhandled Exception
    if packet.exceptions:
        return FailureFindingRecord(
            scenario_id=scenario.id,
            category="AGENT_EXCEPTION",
            subcategory="UNHANDLED_EXCEPTION",
            severity="HIGH",
            symptom="Agent process crashed with an unhandled exception.",
            root_cause=packet.exceptions[0][:150],
            affected_component="Agent Entrypoint Script",
            remediation="Wrap entrypoint execution block in try-except and add exception handling.",
            evidence_ids=[f"ev-{e.event_index}" for e in packet.normalized_events if e.event_type == "STDERR"]
        )

    # Check for Security Violation
    sec_astn = next((f for f in assertion_findings if getattr(f, "assertion_type", "") == "SECURITY_BEHAVIOR" and not getattr(f, "passed", True)), None)
    if sec_astn:
        return FailureFindingRecord(
            scenario_id=scenario.id,
            category="SAFETY_SECURITY",
            subcategory="SECURITY_VIOLATION",
            severity="CRITICAL",
            symptom="Agent executed unauthorized action or followed adversarial prompt injection.",
            root_cause="Lack of prompt injection input sanitization and authorization boundaries.",
            affected_component="Instruction Hierarchy / Guardrails",
            remediation="Implement strict system prompt instruction hierarchy and input filtering.",
            evidence_ids=[]
        )

    # General Output Failure
    return FailureFindingRecord(
        scenario_id=scenario.id,
        category="OUTPUT",
        subcategory="ASSERTION_FAILED",
        severity="MEDIUM",
        symptom="Scenario assertion failed.",
        root_cause=f"Observed output did not satisfy scenario requirement.",
        affected_component="Agent Response Generator",
        remediation="Adjust scenario prompt framing or response formatting instructions.",
        evidence_ids=[]
    )


def cluster_failure_findings(findings: List[FailureFindingRecord]) -> List[FailureCluster]:
    """Groups individual scenario failure findings into root-cause clusters."""
    clusters_map: Dict[str, FailureCluster] = {}

    for f in findings:
        key = f"{f.category}:{f.root_cause[:40]}"
        if key not in clusters_map:
            clusters_map[key] = FailureCluster(
                cluster_id=f"cls-{len(clusters_map)+1}",
                root_cause=f.root_cause,
                category=f.category,
                severity=f.severity,
                affected_scenarios=[f.scenario_id],
                frequency=1,
                suggested_remediation=f.remediation
            )
        else:
            clusters_map[key].affected_scenarios.append(f.scenario_id)
            clusters_map[key].frequency += 1

    return list(clusters_map.values())
