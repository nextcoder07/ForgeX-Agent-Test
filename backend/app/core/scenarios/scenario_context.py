"""
ScenarioContext — compact, typed NAS snapshot used by all Stage 2 components.

Built from AgentRecord + IntakeContract. Replaces the loose evidence_pack dict.
Every field is authoritative and deterministic — no LLM inference.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ScenarioContext:
    agent_id: str
    agent_version_id: Optional[str]
    interface_type: str                  # CLI / HTTP / CHAT
    entrypoint: str
    inputs: List[Dict[str, Any]]         # {name, type, required, default, flag}
    outputs: List[Dict[str, Any]]        # {name, semantic_type, constraints}
    tools: List[str]                     # canonical tool names
    framework_tools: List[str]           # LangChain tools, CrewAI agent roles
    capabilities: List[str]              # validated capability IDs
    workflow_nodes: List[str]            # node IDs from workflow[]
    dependencies: List[str]              # external service names (e.g. "NewsAPI")
    external_services: List[str]         # from side_effects / call_graph / llm_constructors
    side_effects: List[str]              # raw side_effects strings
    security_surfaces: List[str]         # surface types from NAS
    failure_surfaces: List[str]          # from NAS
    decision_surfaces: List[str]         # from NAS
    data_surfaces: Dict[str, Any]        # pii_detected, etc.
    constitution: Dict[str, Any]         # goals, never_rules, always_rules
    model: Optional[str]                 # primary LLM model name
    execution_limits: Dict[str, Any]     # timeout_seconds, max_output_tokens
    all_inputs_have_defaults: bool
    valid_cli_flags: Set[str]
    multi_agent: bool
    agent_personas: List[str]
    source_content_combined: str         # concatenated source file contents
    produces_json: bool                  # agent contract produces JSON output
    produces_email: bool                 # agent contract produces email output
    has_destructive_tools: bool          # any tool is_destructive or has write side effects
    has_monetary_caps: bool              # constitution references monetary/refund limits
    primary_capability: str              # most important capability for happy path


def _infer_produces_json(spec: Dict, source_content: str) -> bool:
    """Infer from output semantic_types OR source analysis (json.dumps/loads)."""
    outputs = spec.get("outputs", []) if isinstance(spec, dict) else []
    for out in outputs:
        if isinstance(out, dict):
            st = (out.get("semantic_type") or "").upper()
            if "JSON" in st:
                return True
    # Source file analysis fallback
    if source_content:
        if "json.dumps(" in source_content or "json.loads(" in source_content:
            if "print(json" in source_content or "return json" in source_content:
                return True
    return False


def _infer_produces_email(spec: Dict) -> bool:
    outputs = spec.get("outputs", []) if isinstance(spec, dict) else []
    for out in outputs:
        if isinstance(out, dict):
            st = (out.get("semantic_type") or "").upper()
            name = (out.get("name") or "").upper()
            if "EMAIL" in st or "EMAIL" in name:
                return True
    return False


def _extract_external_services(spec: Dict, manifest: Dict, evidence: Dict) -> List[str]:
    """Build the list of real external services from all available sources."""
    services: Set[str] = set()

    # From side_effects
    for se in (spec.get("side_effects") or []):
        if isinstance(se, str):
            # "MODEL_INFERENCE: ChatOpenAI" → "ChatOpenAI"
            if ":" in se:
                services.add(se.split(":", 1)[1].strip())
            else:
                services.add(se.strip())

    # From dependencies
    for dep in (spec.get("dependencies") or []):
        if isinstance(dep, dict):
            services.add(dep.get("name", ""))
        elif isinstance(dep, str):
            services.add(dep)

    # From evidence_packet.llm_constructors
    for lc in evidence.get("llm_constructors", []):
        src = lc.get("source_class") or lc.get("provider") or ""
        if src:
            services.add(src)

    # From manifest call_graph targets
    for edge in (manifest.get("call_graph") or []):
        if isinstance(edge, dict):
            target = edge.get("target") or edge.get("callee") or ""
            if target and any(kw in target.lower() for kw in ["api", "openai", "news", "google", "stripe", "sql"]):
                services.add(target)

    # Well-known service aliases
    aliases = {
        "ChatOpenAI": "OpenAI",
        "OpenAI": "OpenAI",
        "newsapi": "NewsAPI",
        "sqlite": "SQLite",
        "postgresql": "PostgreSQL",
    }
    normalized = set()
    for svc in services:
        normalized.add(aliases.get(svc, svc))

    return sorted(s for s in normalized if s)


def _extract_model(evidence: Dict, source_content: str) -> Optional[str]:
    for lc in evidence.get("llm_constructors", []):
        m = lc.get("model") or lc.get("model_name")
        if m:
            return m
    # Source scan for common model patterns
    for pattern in [r'"(gpt-[\w-]+)"', r'"(gemini-[\w-]+)"', r'"(claude-[\w-]+)"']:
        match = re.search(pattern, source_content)
        if match:
            return match.group(1)
    return None


def _primary_capability(capabilities: List[str], category: str = "") -> str:
    if not capabilities:
        return "GENERAL_TASK"
    # For known domains pick the most representative cap
    pref_order = ["NEWS_RETRIEVAL", "EMAIL", "SQL_QUERY_EXECUTION", "JOB_FIT_SCORING",
                  "DATA_EXTRACTION", "TEXT_GENERATION", "LLM_INFERENCE"]
    for pref in pref_order:
        if pref in capabilities:
            return pref
    return capabilities[0]


def build_scenario_context(agent) -> "ScenarioContext":
    """
    Derive a ScenarioContext from an AgentRecord.
    Pulls from agent_spec, runtime_manifest, and evidence_packet.
    All access is guarded against missing attributes.
    """
    manifest: Dict[str, Any] = getattr(agent, "runtime_manifest", None) or {}
    spec: Dict[str, Any] = getattr(agent, "agent_spec", None) or {}
    if not isinstance(spec, dict):
        spec = {}

    # Evidence packet: prefer spec["evidence_packet"] then agent.evidence_packet
    evidence: Dict[str, Any] = spec.get("evidence_packet", {}) if isinstance(spec, dict) else {}
    if not evidence:
        ep = getattr(agent, "evidence_packet", None)
        if isinstance(ep, dict):
            evidence = ep

    # --- Interface ---
    interface_type: str = (
        manifest.get("interface_type")
        or manifest.get("detected_interface")
        or spec.get("interface_type")
        or ("CLI" if not getattr(agent, "tools", None) else "CHAT")
    )
    entrypoint: str = manifest.get("entrypoint", "agent.py")

    # --- Inputs ---
    raw_inputs = spec.get("inputs", []) or []
    inputs: List[Dict[str, Any]] = []
    valid_cli_flags: Set[str] = set()
    all_have_defaults = True
    for inp in raw_inputs:
        if not isinstance(inp, dict):
            continue
        flag = None
        # Try evidence_packet.cli_arguments for exact flags
        for cli_arg in evidence.get("cli_arguments", []):
            if isinstance(cli_arg, dict):
                flags = cli_arg.get("flags", [])
                for f in flags:
                    # Match by stripping --
                    stripped = f.lstrip("-")
                    if stripped == inp.get("name", ""):
                        flag = f
                        valid_cli_flags.add(f)
                        break
        if flag is None:
            # Derive flag from name
            flag = f"--{inp.get('name', '').replace('_', '-')}"
            valid_cli_flags.add(flag)
        required = inp.get("required", False)
        has_default = inp.get("default") is not None or not required
        if required and inp.get("default") is None:
            all_have_defaults = False
        inputs.append({
            "name": inp.get("name", ""),
            "type": inp.get("type", "string"),
            "required": required,
            "default": inp.get("default"),
            "flag": flag,
        })

    # Also pick up any CLI flags from evidence_packet not covered by spec.inputs
    for cli_arg in evidence.get("cli_arguments", []):
        if isinstance(cli_arg, dict):
            for f in cli_arg.get("flags", []):
                valid_cli_flags.add(f)

    # --- Outputs ---
    outputs: List[Dict[str, Any]] = []
    for out in (spec.get("outputs") or []):
        if isinstance(out, dict):
            outputs.append({
                "name": out.get("name", ""),
                "semantic_type": out.get("semantic_type", ""),
                "description": out.get("description", ""),
                "constraints": out.get("constraints", {}),
            })

    # --- Tools ---
    agent_tools = getattr(agent, "tools", None) or []
    tools = [t.name for t in agent_tools if hasattr(t, "name")]
    framework_tools: List[str] = []
    for fc in evidence.get("framework_constructs", []):
        if isinstance(fc, dict):
            role = fc.get("role") or fc.get("name") or fc.get("var_name") or ""
            if role:
                framework_tools.append(role)

    # --- Capabilities ---
    capabilities: List[str] = []
    raw_caps = spec.get("capabilities") or []
    if isinstance(raw_caps, list):
        capabilities = [c for c in raw_caps if isinstance(c, str)]
    if not capabilities:
        capabilities = [t.canonical_capability for t in agent_tools if getattr(t, "canonical_capability", None)]

    # --- Workflow nodes ---
    workflow_nodes: List[str] = []
    for wf in (spec.get("workflow") or []):
        if isinstance(wf, dict):
            nid = wf.get("id") or wf.get("name") or ""
            if nid:
                workflow_nodes.append(nid)
    # Also derive from evidence_packet function names
    for fn in evidence.get("function_definitions", []):
        if isinstance(fn, dict):
            fname = fn.get("name") or fn.get("function_name") or ""
            if fname and fname not in workflow_nodes:
                workflow_nodes.append(fname)

    # --- Source content ---
    source_files = evidence.get("source_files") or {}
    source_content_combined = "\n".join(
        v for v in source_files.values() if isinstance(v, str)
    )

    # --- External services & dependencies ---
    external_services = _extract_external_services(spec, manifest, evidence)
    dep_names = [d.get("name", "") if isinstance(d, dict) else str(d) for d in (spec.get("dependencies") or [])]
    dep_names += [d.name for d in getattr(agent, "dependencies", []) if hasattr(d, "name")]

    # --- Security / failure / decision surfaces ---
    security_surfaces: List[str] = []
    for ss in (getattr(agent, "security_surfaces", None) or spec.get("security_surfaces", [])):
        if isinstance(ss, dict):
            security_surfaces.append(ss.get("type") or ss.get("surface_type") or str(ss))
        elif isinstance(ss, str):
            security_surfaces.append(ss)

    failure_surfaces: List[str] = []
    for fs in (getattr(agent, "failure_surfaces", None) or spec.get("failure_surfaces", [])):
        if isinstance(fs, dict):
            failure_surfaces.append(str(fs.get("name") or fs))
        elif isinstance(fs, str):
            failure_surfaces.append(fs)

    decision_surfaces: List[str] = []
    for ds in (getattr(agent, "decision_surfaces", None) or spec.get("decision_surfaces", [])):
        if isinstance(ds, dict):
            decision_surfaces.append(str(ds.get("name") or ds))
        elif isinstance(ds, str):
            decision_surfaces.append(ds)

    data_surfaces: Dict[str, Any] = getattr(agent, "data_surfaces", None) or spec.get("data_surfaces", {}) or {}

    # --- Multi-agent ---
    agent_personas: List[str] = []
    for fc in evidence.get("framework_constructs", []):
        if isinstance(fc, dict) and "crewai" in (fc.get("type") or "").lower():
            role = fc.get("role") or ""
            if role:
                agent_personas.append(role)
    multi_agent = len(agent_personas) > 1 or bool(spec.get("multi_agent"))

    # --- Model ---
    model = _extract_model(evidence, source_content_combined)

    # --- Execution limits ---
    execution_limits = manifest.get("execution_limits") or spec.get("execution_limits") or {}
    if not execution_limits:
        execution_limits = {"timeout_seconds": 30}

    # --- Destructive / monetary ---
    has_destructive_tools = any(getattr(t, "is_destructive", False) for t in agent_tools)
    has_monetary_caps = any(
        any(kw in rule.lower() for kw in ["₹", "$", "refund", "monetary", "payment", "charge"])
        for rule in (getattr(agent, "constitution", None) and agent.constitution.never_rules or [])
    )

    # --- Produces JSON / Email ---
    produces_json = _infer_produces_json(spec, source_content_combined)
    produces_email = _infer_produces_email(spec)

    # --- Constitution ---
    constitution_obj = getattr(agent, "constitution", None)
    constitution: Dict[str, Any] = {}
    if constitution_obj:
        constitution = {
            "goals": getattr(constitution_obj, "goals", []),
            "never_rules": getattr(constitution_obj, "never_rules", []),
            "always_rules": getattr(constitution_obj, "always_rules", []),
        }

    return ScenarioContext(
        agent_id=agent.id,
        agent_version_id=getattr(agent, "version_label", None),
        interface_type=interface_type,
        entrypoint=entrypoint,
        inputs=inputs,
        outputs=outputs,
        tools=tools,
        framework_tools=framework_tools,
        capabilities=capabilities,
        workflow_nodes=workflow_nodes,
        dependencies=dep_names,
        external_services=external_services,
        side_effects=list(spec.get("side_effects") or []),
        security_surfaces=security_surfaces,
        failure_surfaces=failure_surfaces,
        decision_surfaces=decision_surfaces,
        data_surfaces=data_surfaces,
        constitution=constitution,
        model=model,
        execution_limits=execution_limits,
        all_inputs_have_defaults=all_have_defaults,
        valid_cli_flags=valid_cli_flags,
        multi_agent=multi_agent,
        agent_personas=agent_personas,
        source_content_combined=source_content_combined,
        produces_json=produces_json,
        produces_email=produces_email,
        has_destructive_tools=has_destructive_tools,
        has_monetary_caps=has_monetary_caps,
        primary_capability=_primary_capability(capabilities),
    )
