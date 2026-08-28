"""
ForgeX Canonical Data Models & Evidence Schema.
Defines the unified TestCaseSpecification, EvidenceGraph, PatchArtifact, and AgentVersionRecord.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
import datetime as dt
from pydantic import BaseModel, Field
from app.models.evaluation_ontology import (
    EvaluationDimension,
    FindingSeverity,
    TestVerdictStatus,
    RootCauseAttribution,
    FindingEvidence,
)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# 1. Canonical TestCase Specification
# ---------------------------------------------------------------------------
class AssertionType(str, Enum):
    EQUALS = "EQUALS"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"
    REGEX_MATCH = "REGEX_MATCH"
    JSON_SCHEMA_VALID = "JSON_SCHEMA_VALID"
    EXIT_CODE_EQUALS = "EXIT_CODE_EQUALS"
    TOOL_CALLED = "TOOL_CALLED"
    TOOL_NOT_CALLED = "TOOL_NOT_CALLED"
    TOOL_ARGS_MATCH = "TOOL_ARGS_MATCH"
    TOOL_ORDER_CORRECT = "TOOL_ORDER_CORRECT"
    LATENCY_UNDER_MS = "LATENCY_UNDER_MS"
    TOKEN_COST_UNDER = "TOKEN_COST_UNDER"
    SEMANTIC_JUDGE = "SEMANTIC_JUDGE"


class TestAssertion(BaseModel):
    id: str
    assertion_type: AssertionType
    target_field: str  # e.g. "stdout", "final_message", "tool_calls.args.amount", "exit_code"
    expected_value: Any
    description: str
    is_hard_gate: bool = False
    severity: FindingSeverity = FindingSeverity.HIGH


class TestCaseSpecification(BaseModel):
    id: str
    scenario_id: str
    agent_id: str
    agent_version: str = "v1.0"
    dimension: EvaluationDimension
    metric_id: str
    title: str
    intent: str
    preconditions: Dict[str, Any] = Field(default_factory=dict)
    input_payload: Dict[str, Any] = Field(default_factory=dict)  # user message, CLI args, files
    expected_behavior: List[str] = Field(default_factory=list)
    forbidden_behavior: List[str] = Field(default_factory=list)
    expected_tools: List[str] = Field(default_factory=list)
    assertions: List[TestAssertion] = Field(default_factory=list)
    severity: FindingSeverity = FindingSeverity.HIGH
    timeout_seconds: int = 30
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 2. Canonical Evidence Graph
# ---------------------------------------------------------------------------
class EvidenceNodeType(str, Enum):
    USER_INPUT = "USER_INPUT"
    AGENT_THOUGHT = "AGENT_THOUGHT"
    ACTION_ATTEMPT = "ACTION_ATTEMPT"
    POLICY_DECISION = "POLICY_DECISION"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    SIDE_EFFECT = "SIDE_EFFECT"
    ASSERTION_RESULT = "ASSERTION_RESULT"
    FINDING_TRIGGER = "FINDING_TRIGGER"


class EvidenceEdgeType(str, Enum):
    CAUSES = "CAUSES"
    EVALUATES = "EVALUATES"
    CALLS = "CALLS"
    MUTATES = "MUTATES"
    VIOLATES = "VIOLATES"


class EvidenceNode(BaseModel):
    id: str
    node_type: EvidenceNodeType
    label: str
    timestamp: str
    data: Dict[str, Any] = Field(default_factory=dict)
    is_violation: bool = False


class EvidenceEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: EvidenceEdgeType
    description: Optional[str] = None


class EvidenceGraph(BaseModel):
    scenario_id: str
    execution_session_id: str
    nodes: List[EvidenceNode] = Field(default_factory=list)
    edges: List[EvidenceEdge] = Field(default_factory=list)
    sealed_hash: str = ""
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 3. Patch Artifact & Code Remediation
# ---------------------------------------------------------------------------
class PatchStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPLIED = "APPLIED"
    VERIFIED_PASSED = "VERIFIED_PASSED"
    VERIFIED_REGRESSION = "VERIFIED_REGRESSION"
    REJECTED = "REJECTED"


class FilePatch(BaseModel):
    file_path: str
    before_content: str
    after_content: str
    unified_diff: str
    lines_added: int = 0
    lines_removed: int = 0


class PatchArtifact(BaseModel):
    id: str
    finding_id: str
    agent_id: str
    source_version_id: str
    target_version_label: str  # e.g. "v1.1-repaired"
    title: str
    explanation: str
    root_cause_ref: RootCauseAttribution
    files_changed: List[FilePatch] = Field(default_factory=list)
    status: PatchStatus = PatchStatus.PROPOSED
    regression_test_results: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 4. Agent Version Record & Promotion Lineage
# ---------------------------------------------------------------------------
class AgentVersionRecord(BaseModel):
    id: str
    agent_id: str
    version_label: str  # e.g. "v1.0", "v1.1"
    parent_version_id: Optional[str] = None
    is_latest: bool = True
    change_summary: str = "Initial baseline intake"
    source_files: Dict[str, str] = Field(default_factory=dict)
    patch_artifact_id: Optional[str] = None
    reliability_score: Optional[float] = None
    release_decision: Optional[str] = None
    created_at: str = Field(default_factory=_now)
