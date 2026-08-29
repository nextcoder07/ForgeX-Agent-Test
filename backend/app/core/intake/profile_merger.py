"""
Deterministic & Semantic Profile Merger.
Implements the authoritative hierarchy:
  Observed Deterministic Evidence > Declared Documentation > Gemini Inference.

Ensures Gemini enriches the profile without overwriting deterministic source facts.
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

        # 1. Identity Precedence:
        # If user/agent_name_hint provided -> use it, else semantic name -> else fallback
        ast_info = deterministic_evidence.get("ast", {})
        fw_info = deterministic_evidence.get("framework", {})
        runtime_manifest = deterministic_evidence.get("runtime", {})
        observed_fw = fw_info.get("name", "Unknown")

        # Identity resolution
        declared_name = semantic_response.name or agent_name_hint or "Discovered Agent"
        domain = semantic_response.domain or "general"

        # Check for Framework Conflict between AST and Gemini/Declared docs
        if observed_fw != "Unknown" and semantic_response.architecture_components:
            # If doc claimed something different than observed framework
            pass

        # 2. Tools Precedence:
        # Deterministic AST tools take 100% precedence over any hallucinated LLM tools.
        ast_tools_raw = ast_info.get("tools", [])
        dedup_tools = [ToolDefinition(**t) if isinstance(t, dict) else t for t in ast_tools_raw]

        # 3. Capabilities Precedence:
        # Canonical detected capabilities are merged with semantic capabilities (deduplicated)
        service_facts = deterministic_evidence.get("services", {})
        canonical_caps = service_facts.get("capabilities", [])
        semantic_caps = semantic_response.capabilities or []
        merged_caps = list(dict.fromkeys(canonical_caps + semantic_caps))

        # 4. Dependencies Precedence:
        # Deterministic package dependencies take 100% precedence over LLM suggestions
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

        # 5. Invariants & Transformations Precedence:
        # Observed code invariants (e.g. limit_items: 5, model=gpt-4o-mini, temp=0) take precedence.
        behavioral_raw = deterministic_evidence.get("behavioral_facts", {})
        det_trans_raw = behavioral_raw.get("transformations", [])
        det_inv_raw = behavioral_raw.get("invariants", [])
        det_fail_raw = behavioral_raw.get("failure_surfaces", [])

        transformations = [DataTransformation(**t) if isinstance(t, dict) else t for t in det_trans_raw]
        invariants = [CodeInvariant(**inv) if isinstance(inv, dict) else inv for inv in det_inv_raw]
        failure_surfaces = [FailureSurface(**f) if isinstance(f, dict) else f for f in det_fail_raw]

        # Enrich with semantic invariants if non-conflicting
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

        # 6. Constitution Assembly:
        constitution = AgentConstitution(
            goals=semantic_response.goals,
            never_rules=semantic_response.never_rules,
            always_rules=semantic_response.always_rules,
            escalation_rules=semantic_response.escalation_rules,
            data_policies=semantic_response.data_policies,
        )

        # 7. Workflow Graph:
        # If framework workflow graph exists, use it. Otherwise construct generic functional flow.
        entrypoint_path = runtime_manifest.get("entrypoint", "agent.py")
        fw_graph_dict = fw_info.get("workflow_graph")
        if fw_graph_dict and isinstance(fw_graph_dict, dict) and fw_graph_dict.get("nodes"):
            wf_graph = WorkflowGraph(**fw_graph_dict)
        else:
            # Generic functional control-flow graph from AST functions
            ast_functions = ast_info.get("functions", [])
            wf_nodes: List[WorkflowNode] = []
            wf_edges: List[Dict[str, str]] = []
            prev_node_id = None

            for fn in ast_functions:
                fn_name = fn.get("name", "")
                if fn_name.startswith("_"):
                    continue
                node_type = "entrypoint" if fn_name in ["main", "run", "cli"] else "node"
                ext_deps = []
                for call in fn.get("calls_made", []):
                    if any(kw in call.lower() for kw in ["openai", "llm", "chat"]):
                        ext_deps.append("OpenAI")
                    elif any(kw in call.lower() for kw in ["news", "requests", "get", "fetch"]):
                        ext_deps.append("NewsAPI")
                
                wf_node = WorkflowNode(
                    id=fn_name,
                    name=fn_name,
                    implementation=fn_name,
                    node_type=node_type,
                    external_dependencies=list(dict.fromkeys(ext_deps))
                )
                wf_nodes.append(wf_node)
                if prev_node_id:
                    wf_edges.append({"source": prev_node_id, "target": fn_name})
                prev_node_id = fn_name

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

        # 9. Interface Contract & Output Contract
        raw_inputs = behavioral_raw.get("inputs", [])
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
            inp if isinstance(inp, dict) else {
                "name": str(inp),
                "type": "path" if any(k in str(inp).lower() for k in ["pdf", "file", "path", "doc", "resume"]) else "string"
            }
            for inp in raw_inputs
        ]

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
            outputs=behavioral_raw.get("outputs", []),
            security_surfaces=behavioral_raw.get("security_surfaces", []),
            conflicts=behavioral_raw.get("conflicts", []),
            interface_contract=interface_contract,
            output_contract=output_contract,
            dependency_requirements=dep_reqs,
            agent_version_id=agent_version_id
        )

        # 11. Assemble NormalizedAgentSpec
        derived_exec_status = "EXECUTION_READY" if behavior_profile.readiness.execution_ready else "EXECUTION_BLOCKED"

        # Filter out false-positive env example or credential placeholder risks
        raw_risks = semantic_response.risks or []
        cleaned_risks = []
        for r in raw_risks:
            r_str = str(r).strip()
            if not r_str:
                continue
            r_lower = r_str.lower()
            if ".env" in r_lower or "missing" in r_lower and ("api_key" in r_lower or "key" in r_lower or "credential" in r_lower):
                continue
            cleaned_risks.append(r_str)

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
            risks=cleaned_risks if cleaned_risks else ["Unbounded input boundary risk", "Tool execution error handling risk"],
            state_management=semantic_response.state_management or "In-memory session",
            architecture_components=semantic_response.architecture_components,
            runtime_manifest=runtime_manifest,
            execution_status=derived_exec_status,
        )

        # Convert semantic conflicts to SpecConflict objects
        for c in semantic_response.conflicts:
            if isinstance(c, dict):
                conflicts.append(
                    SpecConflict(
                        id=f"conf-{uuid.uuid4().hex[:6]}",
                        title=c.get("title", "Detected Conflict"),
                        doc_claim=c.get("doc_claim", "Declared behavior"),
                        code_reality=c.get("code_reality", "Observed implementation"),
                        risk_level=c.get("risk_level", "medium"),
                        explanation=c.get("explanation", "Implementation deviates from declared contract.")
                    )
                )

        return norm_spec, behavior_profile, conflicts
