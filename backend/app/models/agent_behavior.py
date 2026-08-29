"""
Agent Behavior Profile and Deep Understanding Data Models.
Establishes versioned behavioral facts, workflow graphs, data transformations,
code invariants, failure surfaces, security exposures, and multi-stage readiness breakdowns.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FunctionClassification(str, Enum):
    ENTRYPOINT = "entrypoint"                    # e.g. main(), run()
    INTERNAL_FUNCTION = "internal_function"        # e.g. helper functions
    WORKFLOW_NODE = "workflow_node"              # e.g. search_web, synthesize_report
    WORKFLOW_CONSTRUCTOR = "workflow_constructor"# e.g. build_graph
    AGENT_TOOL = "agent_tool"                    # e.g. custom tool decorators
    EXTERNAL_SERVICE_CALL = "external_service_call" # e.g. TavilySearch, Stripe
    MODEL_CALL = "model_call"                    # e.g. ChatOpenAI, Gemini
    PACKAGE_DEPENDENCY = "package_dependency"    # e.g. langgraph, requests
    RUNTIME_DEPENDENCY = "runtime_dependency"    # e.g. python 3.12
    CONFIGURATION = "configuration"              # e.g. config parameters
    CREDENTIAL_REFERENCE = "credential_reference"# e.g. OPENAI_API_KEY


class WorkflowNode(BaseModel):
    id: str
    name: str
    implementation: str                          # Name of actual python function
    node_type: str = "node"                      # "entrypoint", "node", "decision", "terminal"
    external_dependencies: List[str] = Field(default_factory=list) # e.g. ["Tavily", "OpenAI"]
    state_dependencies: List[str] = Field(default_factory=list)    # e.g. ["query", "messages"]
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)


class WorkflowGraph(BaseModel):
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[Dict[str, str]] = Field(default_factory=list)      # [{"source": "search", "target": "synthesize"}]
    entrypoint: str = "START"
    terminal_nodes: List[str] = Field(default_factory=list)


class DataTransformation(BaseModel):
    field: str                                   # e.g. "search_results[].content"
    operation: str                               # e.g. "truncate", "format", "normalize"
    parameters: Dict[str, Any] = Field(default_factory=dict) # e.g. {"max_length": 500}
    evidence: str = ""                           # Source code line/snippet


class CodeInvariant(BaseModel):
    statement: str                               # e.g. "Tavily max_results = 5"
    type: str = "observed"                      # "observed", "declared", "inferred"
    enforcement_level: str = "hard"              # "hard" (code enforced) | "soft" (prompt request)
    testability: str = "deterministic"           # "deterministic", "deterministic_output_assertion", "llm_judge"
    source_file: str = "agent.py"
    source_location: Optional[str] = None
    evidence: str = ""
    confidence: float = 1.0


class FailureSurface(BaseModel):
    id: str
    component: str                               # e.g. "TAVILY", "OPENAI", "INPUT", "WORKFLOW"
    surface_type: str                            # "input", "external_service", "data", "llm", "workflow", "security", "resource"
    description: str                             # e.g. "Empty or whitespace query input"
    evidence: str                                # Source snippet or inference rationale
    is_inferred: bool = False                    # True if derived exposure vs observed code branch
    severity: str = "medium"                     # "low", "medium", "high", "critical"


class DeclaredVsImplementedConflict(BaseModel):
    declared_behavior: str                       # e.g. "Protect customer PII"
    implementation_evidence: str                 # e.g. "Not found in AST analysis"
    has_conflict: bool = True
    explanation: str


class InterfaceType(str, Enum):
    CLI = "CLI"
    HTTP = "HTTP"
    FUNCTION = "FUNCTION"
    CHAT = "CHAT"
    EVENT = "EVENT"
    BATCH = "BATCH"
    DIRECTORY = "DIRECTORY"
    UNKNOWN = "UNKNOWN"


class InterfaceContract(BaseModel):
    interface_type: InterfaceType = InterfaceType.UNKNOWN
    entrypoint: Optional[str] = None          # e.g., "python main.py", "app.py:main"
    invocation_pattern: Dict[str, Any] = Field(default_factory=dict) # flags, argv format, HTTP route
    input_artifacts: List[str] = Field(default_factory=list)          # e.g., ["resume.pdf", "data.json"]
    stdin_supported: bool = False
    interactive: bool = False
    endpoint: Optional[str] = None
    env_vars_required: List[str] = Field(default_factory=list)


class OutputContract(BaseModel):
    stdout_format: str = "TEXT"               # "JSON", "TEXT", "TABLE", "RAW"
    output_files: List[str] = Field(default_factory=list)            # e.g., ["output.json"]
    exit_codes: Dict[int, str] = Field(default_factory=lambda: {0: "SUCCESS"})
    schema_definition: Optional[Dict[str, Any]] = None


class ReadinessBreakdown(BaseModel):
    analysis_ready: bool = True
    runtime_ready: bool = True
    dependencies_ready: bool = True
    credentials_ready: bool = False
    sandbox_ready: bool = False
    execution_ready: bool = False
    blocked_reasons: List[str] = Field(default_factory=list)


class AgentBehaviorProfile(BaseModel):
    id: str
    agent_id: str
    agent_version_id: Optional[str] = None
    schema_version: str = "v1"
    identity: Dict[str, str] = Field(default_factory=dict)
    goal: str = ""
    interface_contract: InterfaceContract = Field(default_factory=InterfaceContract)
    output_contract: OutputContract = Field(default_factory=OutputContract)
    dependency_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    inputs: List[Dict[str, Any]] = Field(default_factory=list)
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    state_model: Dict[str, Any] = Field(default_factory=dict)
    external_calls: List[Dict[str, Any]] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    data_transformations: List[DataTransformation] = Field(default_factory=list)
    invariants: List[CodeInvariant] = Field(default_factory=list)
    failure_surfaces: List[FailureSurface] = Field(default_factory=list)
    security_surfaces: List[Dict[str, Any]] = Field(default_factory=list)
    decision_surfaces: List[Dict[str, Any]] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    declared_behaviors: List[str] = Field(default_factory=list)
    observed_behaviors: List[str] = Field(default_factory=list)
    conflicts: List[DeclaredVsImplementedConflict] = Field(default_factory=list)
    readiness: ReadinessBreakdown = Field(default_factory=ReadinessBreakdown)
    confidence_score: float = 1.0
    analysis_run_id: Optional[str] = None
    created_at: str = ""
