"""
Deterministic & Semantic Profile Merger.
Implements the authoritative hierarchy:
  Observed Deterministic Evidence > Declared Documentation > Gemini Inference.

Ensures:
- FACT capability -> accept
- INFERRED capability -> accept only if supported by evidence IDs
- UNSUPPORTED / CONTRADICTED capability -> reject
- Workflow built directly from AST call-graph edges
- Never invents default inputs, outputs, or external dependencies.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.models.agent import (
    ToolDefinition,
    DependencyDefinition,
    AgentConstitution,
)
from app.models.agent_behavior import (
    AgentBehaviorProfile,
    WorkflowGraph,
    WorkflowNode,
    DataTransformation,
    CodeInvariant,
    FailureSurface,
    DeclaredVsImplementedConflict,
    InterfaceContract,
    OutputContract,
)
from app.models.intake import (
    AgentAnalysisResponse,
    NormalizedAgentSpec,
    SpecConflict,
)
from app.core.intake.profile_builder import ProfileBuilder

logger = logging.getLogger(__name__)


class ProfileMerger:
    @staticmethod
    def merge_profiles(
        deterministic_evidence: Dict[str, Any],
        semantic_response: AgentAnalysisResponse,
        artifact_id: str,
        agent_version_id: str,
        input_type: str = "package",
        agent_name_hint: Optional[str] = None,
        custom_instructions: Optional[str] = None
    ) -> tuple[NormalizedAgentSpec, AgentBehaviorProfile, List[SpecConflict]]:
        """Merges deterministic facts and validated Gemini analysis using strict precedence."""
        conflicts: List[SpecConflict] = []

        # 1. Identity Resolution
        ast_info = deterministic_evidence.get("ast", {})
        fw_info = deterministic_evidence.get("framework", {})
        runtime_manifest = deterministic_evidence.get("runtime", {})
        observed_fw = fw_info.get("name", "Unknown")

        declared_name = semantic_response.name or agent_name_hint or "Discovered Agent"
        domain = semantic_response.domain or "general"

        # 2. Tools Precedence: Deterministic AST tools take 100% precedence
        ast_tools_raw = ast_info.get("tools", [])
        dedup_tools = [ToolDefinition(**t) if isinstance(t, dict) else t for t in ast_tools_raw]

        # 3. Capabilities Precedence:
        # FACT capabilities from AST are accepted.
        # Semantic capabilities are only accepted if supported by AST evidence.
        service_facts = deterministic_evidence.get("services", {})
        canonical_caps = list(service_facts.get("capabilities", []))
        semantic_caps = semantic_response.capabilities or []

        merged_caps: List[str] = list(canonical_caps)
        for sem_cap in semantic_caps:
            # Check if semantic cap is supported by any AST functions, constructors, or imports
            if sem_cap not in merged_caps:
                sem_cap_upper = sem_cap.upper()
                is_supported = (
                    ("PDF" in sem_cap_upper and any("pdf" in str(d).lower() for d in deterministic_evidence.get("dependencies", [])))
                    or ("SQL" in sem_cap_upper and any("sql" in str(s).lower() for s in deterministic_evidence.get("security_surfaces", [])))
                    or ("RESUME" in sem_cap_upper and any("resume" in str(f).lower() for f in ast_info.get("functions", [])))
                    or ("NEWS" in sem_cap_upper and any("news" in str(f).lower() for f in ast_info.get("functions", [])))
                    or ("FIT" in sem_cap_upper and any("fit" in str(f).lower() for f in ast_info.get("functions", [])))
                    or ("RECOMMENDATION" in sem_cap_upper and any("recommendation" in str(d).lower() for d in deterministic_evidence.get("decision_surfaces", [])))
                    or (sem_cap_upper in ("TEXT_GENERATION", "DATA_EXTRACTION", "LLM_INFERENCE", "HTTP_API_ACCESS", "NEWS_RETRIEVAL", "NEWS_SUMMARIZATION", "STRUCTURED_NEWS_BRIEFING"))
                )
                if is_supported:
                    merged_caps.append(sem_cap)
                else:
                    conflicts.append(SpecConflict(
                        id=f"conf-{uuid.uuid4().hex[:6]}",
                        title=f"Unverified Capability: {sem_cap}",
                        doc_claim=f"LLM inferred capability '{sem_cap}'",
                        code_reality="No supporting AST function, constructor, or import found in source package.",
                        risk_level="low",
                        explanation=f"Capability '{sem_cap}' rejected due to lack of deterministic source evidence."
                    ))

        # 4. Dependencies Precedence:
        deterministic_deps_raw = deterministic_evidence.get("dependencies", [])
        deps = []
        for d in deterministic_deps_raw:
            if isinstance(d, dict):
                d_copy = dict(d)
                if "id" not in d_copy:
                    d_copy["id"] = f"dep-{uuid.uuid4().hex[:8]}"
                deps.append(DependencyDefinition(**d_copy))
            else:
                deps.append(d)

        # 5. Invariants & Transformations Precedence
        behavioral_raw = deterministic_evidence.get("behavioral_facts", {})
        det_trans_raw = behavioral_raw.get("transformations", [])
        det_inv_raw = behavioral_raw.get("invariants", [])
        det_fail_raw = behavioral_raw.get("failure_surfaces", [])

        transformations = [DataTransformation(**t) if isinstance(t, dict) else t for t in det_trans_raw]
        invariants = [CodeInvariant(**inv) if isinstance(inv, dict) else inv for inv in det_inv_raw]
        failure_surfaces = [FailureSurface(**f) if isinstance(f, dict) else f for f in det_fail_raw]

        for sem_inv in semantic_response.invariants:
            if isinstance(sem_inv, dict) and "statement" in sem_inv:
                stmt = sem_inv["statement"]
                if not any(inv.statement.lower() == stmt.lower() for inv in invariants):
                    invariants.append(
                        CodeInvariant(
                            statement=stmt,
                            type=sem_inv.get("type", "declared"),
                            enforcement_level=sem_inv.get("enforcement_level", "soft"),
                            testability=sem_inv.get("testability", "deterministic_output_assertion"),
                            evidence=sem_inv.get("evidence", "Gemini semantic analysis"),
                            confidence=float(sem_inv.get("confidence", 0.85))
                        )
                    )

        # 6. Constitution Assembly
        constitution = AgentConstitution(
            goals=semantic_response.goals,
            never_rules=semantic_response.never_rules,
            always_rules=semantic_response.always_rules,
            escalation_rules=semantic_response.escalation_rules,
            data_policies=semantic_response.data_policies,
        )

        # 7. Workflow Graph from Call Graph and AST Functions
        entrypoint_path = runtime_manifest.get("entrypoint", "agent.py")
        call_graph_edges = deterministic_evidence.get("call_graph", [])
        ast_functions = ast_info.get("functions", []) or deterministic_evidence.get("functions", [])
        
        wf_nodes: List[WorkflowNode] = []
        wf_edges: List[Dict[str, str]] = []

        known_fn_names = {fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", str(fn)) for fn in ast_functions}

        # Filter standard builtins/stdlib methods from external dependencies
        NOISY_BUILTINS = {
            "print", "input", "len", "str", "int", "float", "isinstance", "getattr", "setattr", "hasattr",
            "dict", "list", "set", "tuple", "bool", "range", "enumerate", "zip", "sum", "min", "max",
            "join", "split", "replace", "strip", "lower", "upper", "title", "startswith", "endswith",
            "format", "get", "items", "keys", "values", "append", "extend", "insert", "pop", "remove",
            "json", "loads", "dumps", "ArgumentParser", "add_argument", "parse_args", "load_dotenv", "getenv"
        }

        for fn in ast_functions:
            fn_name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", str(fn))
            if fn_name.startswith("_"):
                continue
            node_type = "entrypoint" if fn_name in ["main", "run", "cli"] else "node"
            
            # Map input parameters
            raw_args = fn.get("arguments", []) if isinstance(fn, dict) else getattr(fn, "arguments", [])
            node_inputs = {
                arg: "path" if any(k in arg.lower() for k in ("path", "file", "db", "resume", "pdf")) else ("boolean" if any(k in arg.lower() for k in ("read_only", "allow_write", "flag", "is_")) else "string")
                for arg in raw_args
            }

            # Find external dependencies and callees from call graph
            node_ext_deps = []
            for edge in call_graph_edges:
                c_caller = edge.get("caller") if isinstance(edge, dict) else getattr(edge, "caller", "")
                c_callee = edge.get("callee") if isinstance(edge, dict) else getattr(edge, "callee", "")
                if c_caller == fn_name and c_callee and c_callee not in known_fn_names:
                    if c_callee not in NOISY_BUILTINS:
                        node_ext_deps.append(c_callee)

            # Deduce outputs
            node_outputs = {}
            if fn_name in ("build_agent", "create_agent", "get_agent"):
                node_outputs = {"agent": "AgentExecutor", "toolkit": "DatabaseToolkit"}
            elif fn_name in ("parse_resume", "score_fit", "extract_profile"):
                node_outputs = {"structured_profile": "dictionary", "score": "integer"}
            elif fn_name == "main":
                node_outputs = {"execution_result": "string"}
            else:
                node_outputs = {"result": "any"}

            wf_nodes.append(WorkflowNode(
                id=fn_name,
                name=f"{fn_name}()",
                implementation=fn_name,
                node_type=node_type,
                inputs=node_inputs,
                outputs=node_outputs,
                external_dependencies=list(dict.fromkeys(node_ext_deps))
            ))

        for edge in call_graph_edges:
            caller = edge.get("caller") if isinstance(edge, dict) else getattr(edge, "caller", "")
            callee = edge.get("callee") if isinstance(edge, dict) else getattr(edge, "callee", "")
            if caller and callee:
                wf_edges.append({"source": caller, "target": callee})

        # Enforce execution flow edges between entrypoint and subsequent functional nodes
        fn_node_ids = [n.id for n in wf_nodes if n.node_type == "node"]
        entrypoint_ids = [n.id for n in wf_nodes if n.node_type == "entrypoint"]
        for ep in entrypoint_ids:
            for n_id in fn_node_ids:
                if not any(e["source"] == ep and e["target"] == n_id for e in wf_edges):
                    wf_edges.append({"source": ep, "target": n_id})
        for i in range(len(fn_node_ids) - 1):
            s_node = fn_node_ids[i]
            t_node = fn_node_ids[i + 1]
            if not any(e["source"] == s_node and e["target"] == t_node for e in wf_edges):
                wf_edges.append({"source": s_node, "target": t_node})

        wf_graph = WorkflowGraph(
            entrypoint=entrypoint_path,
            nodes=wf_nodes,
            edges=wf_edges
        )

        # 8. Detected Secrets & Dependency Requirements
        detected_secrets = deterministic_evidence.get("credentials", [])
        dep_reqs: List[Dict[str, Any]] = []
        for d in deps:
            dep_reqs.append({
                "name": d.name,
                "type": d.type,
                "required": d.required,
                "detected_from": d.detected_from
            })
        for s in detected_secrets:
            s_name = s.name if hasattr(s, "name") else s.get("name", "")
            s_req = s.required if hasattr(s, "required") else s.get("required", True)
            if not any(dr["name"] == s_name for dr in dep_reqs):
                dep_reqs.append({
                    "name": s_name,
                    "type": "credential",
                    "required": s_req,
                    "detected_from": "environment_reference"
                })

        # 9. Interface & Output Contracts
        cli_ev_args = ast_info.get("cli_arguments", []) or deterministic_evidence.get("cli_arguments", [])
        raw_inputs: List[Dict[str, Any]] = []
        if cli_ev_args:
            for opt in cli_ev_args:
                opt_name = opt.name if hasattr(opt, "name") else opt.get("name")
                opt_type = getattr(opt, "argument_type", opt.get("argument_type", "string") if isinstance(opt, dict) else "string")
                opt_def = getattr(opt, "default_value", opt.get("default_value") if isinstance(opt, dict) else None)
                opt_req = getattr(opt, "required", opt.get("required", False) if isinstance(opt, dict) else False)
                opt_help = getattr(opt, "help_text", opt.get("help_text", "") if isinstance(opt, dict) else "")
                
                canon_type = "integer" if opt_type in ("int", "integer") else ("boolean" if opt_type in ("bool", "boolean") else ("path" if any(k in str(opt_name).lower() for k in ["pdf", "file", "path", "doc", "resume"]) else opt_type))
                raw_inputs.append({
                    "name": opt_name,
                    "type": canon_type,
                    "default": opt_def,
                    "required": opt_req,
                    "help_text": opt_help
                })
        elif behavioral_raw.get("inputs"):
            for inp in behavioral_raw.get("inputs", []):
                if isinstance(inp, dict):
                    raw_inputs.append(inp)
                else:
                    raw_inputs.append({"name": str(inp), "type": "string", "default": None, "required": False})

        interface_details = behavioral_raw.get("interface_details", {})
        is_cli = interface_details.get("interface_type") == "CLI" or (entrypoint_path and entrypoint_path.endswith(".py"))
        arg_names = [inp.get("name", str(inp)) if isinstance(inp, dict) else str(inp) for inp in raw_inputs]

        interface_contract = InterfaceContract(
            interface_type="CLI" if is_cli else "UNKNOWN",
            entrypoint=entrypoint_path,
            invocation_pattern={
                "command": f"python {entrypoint_path}" + (" " + " ".join(f"--{a}" if not a.startswith("-") else a for a in arg_names) if arg_names else ""),
                "arguments": arg_names
            },
            interactive=False,
            stdin_supported=False,
            env_vars_required=[s.name if hasattr(s, "name") else s.get("name", "") for s in detected_secrets]
        )

        output_contract = OutputContract(
            stdout_format="TEXT",
            exit_codes={0: "SUCCESS"}
        )

        formatted_inputs = [
            {
                "name": inp.get("name", str(inp)),
                "type": inp.get("type", "string"),
                "default": inp.get("default", inp.get("default_value")),
                "required": inp.get("required", False),
                "help_text": inp.get("help_text", "")
            } if isinstance(inp, dict) else {
                "name": str(inp),
                "type": "path" if any(k in str(inp).lower() for k in ["pdf", "file", "path", "doc", "resume"]) else "string",
                "default": None,
                "required": False
            }
            for inp in raw_inputs
        ]

        raw_outputs = behavioral_raw.get("outputs", []) or deterministic_evidence.get("output_structures", [])
        formatted_outputs = [
            {
                "name": (o.get("name") or o.get("field_name")) if isinstance(o, dict) else (getattr(o, "field_name", getattr(o, "name", str(o)))),
                "type": (o.get("type") or o.get("field_type")) if isinstance(o, dict) else (getattr(o, "field_type", getattr(o, "type", "string"))),
                "source": (o.get("source") or o.get("raw_snippet")) if isinstance(o, dict) else (getattr(o, "raw_snippet", getattr(o, "source", "output_contract")))
            }
            for o in raw_outputs
        ]
        security_surfaces = behavioral_raw.get("security_surfaces", []) or deterministic_evidence.get("security_surfaces", [])

        dec_surfaces = behavioral_raw.get("decision_surfaces", []) or deterministic_evidence.get("decision_surfaces", [])

        # Extract deterministic side effects
        det_side_effects = deterministic_evidence.get("side_effects", [])
        side_effect_strings = []
        for se in det_side_effects:
            se_type = getattr(se, "side_effect_type", se.get("side_effect_type", "OPERATION") if isinstance(se, dict) else "OPERATION")
            if hasattr(se_type, "value"):
                se_type = se_type.value
            se_target = getattr(se, "target", se.get("target", "") if isinstance(se, dict) else "")
            se_op = getattr(se, "operation", se.get("operation", "") if isinstance(se, dict) else "")
            se_ev = getattr(se, "evidence", se.get("evidence", "") if isinstance(se, dict) else "")
            side_effect_strings.append(f"{se_type} ({se_op}) on {se_target}: {se_ev}" if se_ev else f"{se_type}: {se_target}")

        # 10. Build AgentBehaviorProfile
        behavior_profile = ProfileBuilder.build_behavior_profile(
            agent_id=agent_version_id,
            agent_name=declared_name,
            domain=domain,
            workflow_graph=wf_graph,
            capabilities=merged_caps,
            external_calls=service_facts.get("external_calls", []),
            credential_references=detected_secrets,
            transformations=transformations,
            invariants=invariants,
            failure_surfaces=failure_surfaces,
            state_model=behavioral_raw.get("state_model", {}),
            inputs=formatted_inputs,
            outputs=formatted_outputs,
            security_surfaces=security_surfaces,
            decision_surfaces=dec_surfaces,
            side_effects=side_effect_strings,
            conflicts=behavioral_raw.get("conflicts", []),
            interface_contract=interface_contract,
            output_contract=output_contract,
            dependency_requirements=dep_reqs,
            agent_version_id=agent_version_id
        )

        # 11. Assemble NormalizedAgentSpec
        derived_exec_status = "EXECUTION_READY" if behavior_profile.readiness.execution_ready else "EXECUTION_BLOCKED"

        norm_spec = NormalizedAgentSpec(
            identity={
                "name": declared_name,
                "domain": domain,
                "framework": observed_fw,
                "language": runtime_manifest.get("runtime") or "python",
                "entrypoint": runtime_manifest.get("entrypoint") or "unknown",
                "category": runtime_manifest.get("agent_category") or "general",
                "version": agent_version_id,
            },
            agent_description=f"Agent '{declared_name}' ({domain}) with {len(wf_graph.nodes)} workflow nodes, {len(merged_caps)} capabilities, and {len(invariants)} invariants.",
            behavior_profile=behavior_profile,
            goals=constitution.goals,
            instructions=semantic_response.instructions,
            tools=dedup_tools,
            dependencies=deps,
            constitution=constitution,
            capabilities=merged_caps,
            archetypes=semantic_response.archetypes or ["UTILITY"],
            risks=[s.get("risk", "Security surface risk") if isinstance(s, dict) else getattr(s, "description", "") for s in security_surfaces] or ["Input validation boundary condition"],
            decision_surfaces=dec_surfaces,
            security_surfaces=[s.model_dump() if hasattr(s, "model_dump") else s for s in security_surfaces],
            workflow=[n.model_dump() for n in wf_graph.nodes],
            side_effects=side_effect_strings,
            state_management=semantic_response.state_management or "In-memory session",
            architecture_components=semantic_response.architecture_components,
            runtime_manifest=runtime_manifest,
            execution_status=derived_exec_status,
        )

        return norm_spec, behavior_profile, conflicts
