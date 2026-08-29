"""
Intake Contract Extractor.

Derives the canonical ground-truth interface constraints from an AgentRecord.
Used by the hard deterministic scenario validator to reject any scenario that
invents CLI flags, unknown workflow nodes, or impossible assertions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class OutputFieldContract:
    field_name: str
    semantic_type: str          # e.g. "EMAIL_DRAFT", "EMAIL_BRIEF", "JSON"
    description: str
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntakeContract:
    """Ground-truth constraints extracted from an AgentRecord's Intake evidence."""

    # Interface
    interface_type: str                        # "CLI" | "HTTP" | "CHAT"
    entrypoint: str                            # e.g. "05-email-drafting-agent/agent.py"
    invocation_command: str                    # e.g. "python 05-email-drafting-agent/agent.py"

    # CLI flags — the ONLY flags the generator is allowed to use
    valid_cli_flags: Set[str]                  # e.g. {"--context", "--tone", "--recipient"}
    all_inputs_have_defaults: bool             # True → empty invocation = valid run

    # Workflow nodes — the ONLY node IDs target_workflow_node may reference
    valid_workflow_node_ids: Set[str]          # e.g. {"main", "build_email_crew", "analyze_task", "write_task"}

    # Multi-agent topology
    agent_personas: List[str]                  # e.g. ["Email Context Analyst", "Professional Email Writer"]
    multi_agent: bool                          # True if >1 agent persona detected

    # Capabilities — the ONLY values required_capabilities may contain
    valid_capabilities: Set[str]               # e.g. {"EMAIL", "LLM_INFERENCE"}

    # Known side-effect targets for fault_injections
    valid_fault_targets: Set[str]              # e.g. {"ChatOpenAI", "openai"}

    # Output contracts for semantic assertion generation
    output_contracts: List[OutputFieldContract]

    # Source file content for invented-assertion detection
    source_content_combined: str              # All source files concatenated for substring checks


def build_intake_contract(agent) -> IntakeContract:
    """
    Derives an IntakeContract from an AgentRecord.
    Falls back gracefully when evidence packet fields are missing.
    """
    manifest: Dict[str, Any] = getattr(agent, "runtime_manifest", None) or {}
    spec: Dict[str, Any] = getattr(agent, "agent_spec", None) or {}
    if not isinstance(spec, dict):
        spec = {}
    evidence: Dict[str, Any] = spec.get("evidence_packet", {}) if isinstance(spec, dict) else {}
    if not evidence:
        ep = getattr(agent, "evidence_packet", None)
        if isinstance(ep, dict):
            evidence = ep


    # --- Interface ---
    entrypoint = manifest.get("entrypoint", "agent.py")
    detected_interface = manifest.get("detected_interface") or manifest.get("interface_type", "")
    if not detected_interface:
        detected_interface = "CLI" if (entrypoint.endswith(".py") and not agent.tools) else ("CHAT" if agent.tools else "UNKNOWN")
    invocation_cmd = f"python {entrypoint}"

    # --- CLI flags from evidence_packet.cli_arguments ---
    valid_flags: Set[str] = set()
    all_defaults = True

    cli_args = evidence.get("cli_arguments", [])
    spec_inputs = spec.get("inputs", []) if isinstance(spec, dict) else []
    if not cli_args and spec_inputs:
        for inp in spec_inputs:
            name = inp.get("name", "")
            if name:
                valid_flags.add(f"--{name}")
                if inp.get("required", False) and inp.get("default") is None:
                    all_defaults = False
    else:
        for cli_arg in cli_args:
            for flag in cli_arg.get("flags", []):
                valid_flags.add(flag)
            if cli_arg.get("required", False) and cli_arg.get("default_value") is None:
                all_defaults = False

    # --- Workflow nodes ---
    workflow_nodes: Set[str] = set()
    workflow_list = spec.get("workflow", []) if isinstance(spec, dict) else []
    for node in workflow_list:
        node_id = node.get("id") or node.get("name")
        if node_id:
            workflow_nodes.add(str(node_id))

    # --- Multi-agent topology from framework_constructs ---
    agent_personas: List[str] = []
    framework_constructs = evidence.get("framework_constructs", [])
    for fc in framework_constructs:
        if fc.get("type") == "crewai_agent":
            role = fc.get("role")
            if role:
                agent_personas.append(role)
    multi_agent = len(agent_personas) > 1

    # --- Capabilities ---
    capabilities_raw = spec.get("capabilities", []) if isinstance(spec, dict) else []
    valid_caps: Set[str] = set()
    if isinstance(capabilities_raw, list):
        for cap in capabilities_raw:
            if isinstance(cap, str):
                valid_caps.add(cap.upper())
            elif isinstance(cap, dict):
                cname = cap.get("name") or cap.get("id")
                if cname:
                    valid_caps.add(str(cname).upper())

    # --- Fault targets from side_effects + LLM constructors ---
    fault_targets: Set[str] = set()
    side_effects = spec.get("side_effects", []) if isinstance(spec, dict) else []
    for se in side_effects:
        if isinstance(se, str):
            # e.g. "MODEL_INFERENCE: ChatOpenAI"
            parts = se.split(":")
            if len(parts) == 2:
                fault_targets.add(parts[1].strip())
        elif isinstance(se, dict):
            target = se.get("target") or se.get("name")
            if target:
                fault_targets.add(str(target))

    llm_constructors = evidence.get("llm_constructors", [])
    for lc in llm_constructors:
        src_class = lc.get("source_class")
        provider = lc.get("provider")
        if src_class:
            fault_targets.add(src_class)
        if provider:
            fault_targets.add(provider)
    # Allow requests.get for agents with HTTP call graph edges
    call_graph = evidence.get("call_graph", [])
    for edge in call_graph:
        callee = edge.get("callee", "")
        if callee in ("requests", "get", "post", "httpx"):
            fault_targets.add("requests.get")

    # --- Output contracts ---
    output_contracts: List[OutputFieldContract] = []
    output_structures = evidence.get("output_structures", [])
    for os_entry in output_structures:
        output_contracts.append(OutputFieldContract(
            field_name=os_entry.get("field_name", "output"),
            semantic_type=os_entry.get("semantic_type", "STRING"),
            description=os_entry.get("description", ""),
            constraints=os_entry.get("constraints", {}),
        ))
    if not output_contracts:
        spec_outputs = spec.get("outputs", []) if isinstance(spec, dict) else []
        for out in spec_outputs:
            output_contracts.append(OutputFieldContract(
                field_name=out.get("name", "output"),
                semantic_type=out.get("semantic_type", "STRING"),
                description=out.get("description", ""),
                constraints=out.get("constraints", {}),
            ))

    # --- Combined source content for invented-assertion detection ---
    source_files = evidence.get("source_files", {}) or spec.get("source_files", {}) or {}
    combined_source = "\n".join(
        v if isinstance(v, str) else ""
        for v in source_files.values()
    )

    return IntakeContract(
        interface_type=detected_interface.upper(),
        entrypoint=entrypoint,
        invocation_command=invocation_cmd,
        valid_cli_flags=valid_flags,
        all_inputs_have_defaults=all_defaults,
        valid_workflow_node_ids=workflow_nodes,
        agent_personas=agent_personas,
        multi_agent=multi_agent,
        valid_capabilities=valid_caps,
        valid_fault_targets=fault_targets,
        output_contracts=output_contracts,
        source_content_combined=combined_source,
    )


def cli_args_from_invocation(invocation: Dict[str, Any]) -> List[str]:
    """Extracts all '--flag' strings from a scenario invocation dict."""
    args = invocation.get("args") or invocation.get("arguments") or []
    return [a for a in args if isinstance(a, str) and a.startswith("--")]


def assertion_value_is_in_source(expected_value: Any, source_content: str) -> bool:
    """
    Returns True if the expected_value string is plausibly producible by the agent
    (found literally in source files OR is a generic pattern).
    Used to detect invented exact-string error messages.
    """
    if not isinstance(expected_value, str) or not source_content:
        return True  # can't determine → allow
    return expected_value.lower() in source_content.lower()
