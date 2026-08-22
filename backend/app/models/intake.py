"""
Agent Intake, Universal Ingestion, and Normalized Specification Models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.agent import ToolDefinition, DependencyDefinition, AgentConstitution


class AgentIntakePayload(BaseModel):
    files: Dict[str, str] = Field(default_factory=dict)  # filename -> file content string
    input_type: str = "package"
    pasted_code: Optional[str] = None
    pasted_prompt: Optional[str] = None
    endpoint_url: Optional[str] = None
    agent_name_hint: Optional[str] = "Discovered Agent"
    demo_agent_id: Optional[str] = None


class ArtifactRecord(BaseModel):
    artifact_id: str
    artifact_hash: str  # SHA256
    file_count: int
    total_bytes: int
    files_list: List[str]
    input_type: str = "package"
    created_at: str


class SpecConflict(BaseModel):
    id: str
    title: str
    doc_claim: str
    code_reality: str
    risk_level: str  # "critical", "high", "medium"
    explanation: str


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "agent", "tool", "database", "api", "memory", "subagent"
    risk: str  # "low", "medium", "high", "critical"
    details: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None


class NormalizedAgentSpec(BaseModel):
    identity: Dict[str, str]  # name, domain, framework, language, entrypoint
    goals: List[str] = Field(default_factory=list)
    instructions: List[str] = Field(default_factory=list)
    tools: List[ToolDefinition] = Field(default_factory=list)
    dependencies: List[DependencyDefinition] = Field(default_factory=list)
    constitution: AgentConstitution = Field(default_factory=AgentConstitution)
    capabilities: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    state_management: str = "In-memory session"
    architecture_components: List[str] = Field(default_factory=list)
    runtime_manifest: Dict[str, Any] = Field(default_factory=dict)
    execution_status: str = "EXECUTION_BLOCKED"


class RegisterSpecRequest(BaseModel):
    normalized_spec: NormalizedAgentSpec
    display_name: str = Field(..., min_length=1)
    artifact: Optional[ArtifactRecord] = None
    source_files: Dict[str, str] = Field(default_factory=dict)
    endpoint_url: Optional[str] = None


class AgentUnderstandingResult(BaseModel):
    artifact: ArtifactRecord
    normalized_spec: NormalizedAgentSpec
    conflicts: List[SpecConflict]
    confidence_score: float  # e.g., 96.4%
    ambiguities: List[str]
    graph_nodes: List[GraphNode]
    graph_edges: List[GraphEdge]
