"""
Canonical Evidence Models for Deterministic Agent Intake.
Defines granular evidence items with certainty tiers (FACT / INFERRED / UNKNOWN)
and full traceability back to source files and AST nodes.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class CertaintyLevel(str, Enum):
    FACT = "FACT"          # Indisputable static AST fact
    INFERRED = "INFERRED"  # Synthesized from evidence combinations
    UNKNOWN = "UNKNOWN"    # Unstated in source code / unobservable statically


class ProvenanceType(str, Enum):
    CODE_PROVEN = "CODE_PROVEN"          # Found directly in executable AST / signatures
    PROMPT_DECLARED = "PROMPT_DECLARED"  # Declared in system prompts / prompt templates
    DOC_DECLARED = "DOC_DECLARED"        # Declared in README, docstrings, or metadata files
    INFERRED = "INFERRED"                # Deduced from contextual operations
    UNKNOWN = "UNKNOWN"                  # Cannot be proven


class SideEffectType(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    FILESYSTEM = "FILESYSTEM"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    SUBPROCESS = "SUBPROCESS"
    NONE = "NONE"


class EvidenceCategory(str, Enum):
    IMPORT = "IMPORT"
    CLI_ARGUMENT = "CLI_ARGUMENT"
    FUNCTION_DEF = "FUNCTION_DEF"
    CLASS_DEF = "CLASS_DEF"
    LLM_CONSTRUCTOR = "LLM_CONSTRUCTOR"
    TOOL_DEFINITION = "TOOL_DEFINITION"
    FRAMEWORK_CONSTRUCT = "FRAMEWORK_CONSTRUCT"
    DATABASE_OPERATION = "DATABASE_OPERATION"
    FILESYSTEM_OPERATION = "FILESYSTEM_OPERATION"
    NETWORK_CALL = "NETWORK_CALL"
    SUBPROCESS_EXECUTION = "SUBPROCESS_EXECUTION"
    SECURITY_SURFACE = "SECURITY_SURFACE"
    DECISION_SURFACE = "DECISION_SURFACE"
    ENVIRONMENT_VARIABLE = "ENVIRONMENT_VARIABLE"
    STATE_MEMORY = "STATE_MEMORY"
    CALL_EDGE = "CALL_EDGE"
    CONDITIONAL_BRANCH = "CONDITIONAL_BRANCH"
    OUTPUT_STRUCTURE = "OUTPUT_STRUCTURE"
    DATA_TRANSFORMATION = "DATA_TRANSFORMATION"


class EvidenceItem(BaseModel):
    id: str
    artifact_id: str
    category: EvidenceCategory
    certainty: CertaintyLevel = CertaintyLevel.FACT
    provenance: ProvenanceType = ProvenanceType.CODE_PROVEN
    name: str
    source_file: str
    line_number: int = 1
    raw_snippet: str = ""
    attributes: Dict[str, Any] = Field(default_factory=dict)
    supporting_evidence_ids: List[str] = Field(default_factory=list)


class CLIOptionEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    flags: List[str]
    name: str
    argument_type: str = "string"  # "string", "path", "int", "boolean", "float"
    required: bool = False
    default_value: Optional[Any] = None
    help_text: Optional[str] = None
    is_flag_switch: bool = False
    source_file: str = "agent.py"
    line_number: int = 1


class LLMConstructorEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    provider: str            # "openai", "anthropic", "google", "ollama", "local"
    model_name: str          # e.g. "gpt-4o-mini", "gemini-1.5-flash", "UNKNOWN"
    model_certainty: CertaintyLevel = CertaintyLevel.FACT
    is_dynamic_model: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_streaming: bool = False
    source_class: str        # "ChatOpenAI", "OpenAI", "ChatGoogleGenerativeAI"
    source_file: str
    line_number: int


class SecuritySurfaceEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    surface_type: str        # "SQL_EXECUTION", "PII_PROCESSING", "UNTRUSTED_FILE_READ", "SHELL_EXECUTION", "API_KEY_READ", "CONDITIONAL_WRITE"
    severity: str            # "low", "medium", "high", "critical"
    description: str
    source_file: str
    line_number: int
    trigger_condition: Optional[str] = None
    mitigation_hint: Optional[str] = None
    supporting_evidence_ids: List[str] = Field(default_factory=list)


class DecisionSurfaceEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    decision_type: str       # "CANDIDATE_EVALUATION", "FINANCIAL_DECISION", "ACCESS_APPROVAL", "CLASSIFICATION", "SCORING"
    impact: str              # "EMPLOYMENT_DECISION", "MONETARY_TRANSACTION", "DATA_ACCESS", "ROUTING"
    description: str
    recommendation_options: List[str] = Field(default_factory=list)
    source_file: str
    line_number: int
    evidence_snippet: str = ""
    supporting_evidence_ids: List[str] = Field(default_factory=list)


class OutputStructureEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    field_name: str
    field_type: str          # "string", "integer", "float", "dictionary", "list", "boolean"
    semantic_type: Optional[str] = None
    description: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    provenance: ProvenanceType = ProvenanceType.CODE_PROVEN
    source_file: str
    line_number: int = 1
    raw_snippet: str = ""


class SideEffectEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    side_effect_type: SideEffectType
    target: str
    operation: str
    source_file: str
    line_number: int = 1
    evidence: str = ""


class FunctionDefEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    name: str
    arguments: List[str] = Field(default_factory=list)
    decorators: List[str] = Field(default_factory=list)
    docstring: Optional[str] = None
    source_file: str
    line_number: int = 1


class CallGraphEdge(BaseModel):
    caller: str
    callee: str
    source_file: str
    line_number: int
    is_conditional: bool = False
    condition_snippet: Optional[str] = None


class ConditionalBranchEvidence(BaseModel):
    id: str
    artifact_id: str = ""
    condition_code: str
    branch_type: str         # "if", "elif", "else", "try", "except"
    source_file: str
    line_number: int


class FieldConfidenceScore(BaseModel):
    field_name: str
    score: float             # 0.0 to 1.0
    certainty: CertaintyLevel
    evidence_count: int
    notes: str = ""


class EvidencePacket(BaseModel):
    artifact_id: str
    entrypoint: str
    source_files: Dict[str, str] = Field(default_factory=dict)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    functions: List[FunctionDefEvidence] = Field(default_factory=list)
    cli_arguments: List[CLIOptionEvidence] = Field(default_factory=list)
    llm_constructors: List[LLMConstructorEvidence] = Field(default_factory=list)
    security_surfaces: List[SecuritySurfaceEvidence] = Field(default_factory=list)
    decision_surfaces: List[DecisionSurfaceEvidence] = Field(default_factory=list)
    output_structures: List[OutputStructureEvidence] = Field(default_factory=list)
    call_graph: List[CallGraphEdge] = Field(default_factory=list)
    conditional_branches: List[ConditionalBranchEvidence] = Field(default_factory=list)
    framework_constructs: List[Dict[str, Any]] = Field(default_factory=list)
    detected_packages: List[str] = Field(default_factory=list)
    environment_variables: List[str] = Field(default_factory=list)
    side_effects: List[SideEffectEvidence] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)

    def get_evidence_by_id(self, ev_id: str) -> Optional[EvidenceItem]:
        for item in self.evidence_items:
            if item.id == ev_id:
                return item
        return None

    def get_evidence_by_category(self, cat: EvidenceCategory) -> List[EvidenceItem]:
        return [item for item in self.evidence_items if item.category == cat]
