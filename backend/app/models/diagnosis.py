"""
Failure Diagnosis and Root Cause Classification Models.
Translates raw execution findings and trajectory events into precise,
human-interpretable diagnoses with source code & prompt references.
"""

from __future__ import annotations
import uuid
import datetime as dt
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class DiagnosticEvidence(BaseModel):
    event_id: str
    event_type: str  # ACTION_ATTEMPT, POLICY_DECISION, EXECUTED, RESULT, SIDE_EFFECT, ERROR
    timestamp: Optional[str] = None
    summary: str
    raw_payload: Optional[Dict[str, Any]] = None


class FailureDiagnosis(BaseModel):
    id: str = Field(default_factory=lambda: f"diag-{uuid.uuid4().hex[:8]}")
    finding_id: str
    agent_id: str
    scenario_id: str
    scenario_title: Optional[str] = None
    category: str
    severity: str  # critical, high, medium, low
    title: str
    
    # Root Cause Classification (Strict Taxonomy)
    # CODE_DEFECT | PROMPT_DEFECT | POLICY_DEFECT | ENVIRONMENT_DEFECT | TOOL_DEFECT | MODEL_CAPABILITY_DEFECT
    root_cause_type: str
    
    # Diagnosis Narrative
    what_happened: str
    why_it_happened: str
    root_cause_detail: str
    impact_assessment: str
    
    # Source Code / Prompt Grounding
    affected_source_file: Optional[str] = None
    affected_line_number: Optional[int] = None
    affected_symbol: Optional[str] = None
    affected_prompt_section: Optional[str] = None
    
    # Evidence Trace
    evidence_events: List[DiagnosticEvidence] = Field(default_factory=list)
    attempted_action: Optional[str] = None
    policy_blocked: bool = False
    actual_side_effect_occurred: bool = False
    
    # Repair Recommendation
    recommended_repair_type: str  # CODE_PATCH, PROMPT_HARDENING, TOOL_POLICY, CONFIG_UPDATE, TRAINING_DATASET
    suggested_fix_summary: str
    created_at: str = Field(default_factory=_now)


class AgentDiagnosisReport(BaseModel):
    id: str = Field(default_factory=lambda: f"diag-rep-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_name: str
    evaluation_run_id: str
    total_failures: int
    critical_failures: int
    diagnoses: List[FailureDiagnosis] = Field(default_factory=list)
    defect_breakdown: Dict[str, int] = Field(default_factory=dict)
    primary_repair_recommendation: str = "CODE_PATCH"
    created_at: str = Field(default_factory=_now)


def build_empty_diagnosis_report(
    agent_id: str,
    agent_name: str,
    evaluation_run_id: str,
    summary: str = "No evaluation failures detected for this agent."
) -> AgentDiagnosisReport:
    """Canonical factory that constructs a 100% complete empty AgentDiagnosisReport."""
    return AgentDiagnosisReport(
        id=f"diag-empty-{evaluation_run_id or agent_id}",
        agent_id=agent_id or "unknown",
        agent_name=agent_name or "Unknown Agent",
        evaluation_run_id=evaluation_run_id or "",
        total_failures=0,
        critical_failures=0,
        diagnoses=[],
        defect_breakdown={},
        primary_repair_recommendation=summary,
        created_at=_now()
    )
