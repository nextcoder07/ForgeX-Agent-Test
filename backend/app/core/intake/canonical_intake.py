"""
Canonical Intake Construction Engine.
Synthesizes the single source of truth CanonicalIntake representation
derived from AST, EvidencePacket, Framework Analysis, Dependency Detector, and Auditor Findings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from app.core.intake.evidence_models import (
    CanonicalIntake,
    CanonicalCredentialDependency,
    DependencyState,
    EvidencePacket,
    CertaintyLevel,
    ProvenanceType,
    FieldConfidenceScore
)
from app.models.intake import NormalizedAgentSpec
from app.core.intake.intake_auditor import IntakeAuditReport

logger = logging.getLogger(__name__)

# Framework primitive symbols that are NOT executable user tools
FRAMEWORK_PRIMITIVES = {
    "StateGraph", "END", "START", "Agent", "Task", "Crew", "LLMChain",
    "SystemMessage", "HumanMessage", "AIMessage", "ChatMessage",
    "PromptTemplate", "ChatPromptTemplate", "MessagesPlaceholder",
    "BaseModel", "TypedDict", "Field", "dataclass", "argparse",
    "ArgumentParser", "load_dotenv"
}

# LLM constructor class names
LLM_CONSTRUCTORS = {
    "ChatOpenAI", "OpenAI", "ChatGoogleGenerativeAI", "GoogleGenerativeAI",
    "ChatGroq", "Groq", "ChatAnthropic", "Anthropic", "Ollama", "ChatOllama",
    "ChatOpenRouter", "OpenRouter"
}


class CanonicalIntakeBuilder:
    @classmethod
    def build_canonical_intake(
        cls,
        spec: NormalizedAgentSpec,
        evidence_packet: EvidencePacket,
        audit_report: Optional[IntakeAuditReport] = None,
        artifact_hash: str = ""
    ) -> CanonicalIntake:
        """Constructs the canonical single-source-of-truth representation for downstream consumption."""

        # 1. Identity & Interface
        agent_id = getattr(spec, "agent_id", "") or getattr(evidence_packet, "artifact_id", "agent-0")
        spec_name = spec.identity.get("name") if isinstance(spec.identity, dict) else None
        # Prefer explicit agent_name_hint or AST name over MockLLM generic default "Customer Support Agent"
        if spec_name and spec_name != "Customer Support Agent":
            name = spec_name
        else:
            name = (spec.identity.get("agent_name") if isinstance(spec.identity, dict) else None) or "Discovered Agent"
        
        domain = spec.identity.get("domain") if isinstance(spec.identity, dict) else "General"
        description = (spec.identity.get("description") if isinstance(spec.identity, dict) else None) or getattr(spec, "agent_description", "") or "Autonomous agent"
        entrypoint = evidence_packet.entrypoint or "agent.py"
        
        interface_contract = getattr(spec, "interface_contract", None)
        if isinstance(interface_contract, dict):
            interface_type = interface_contract.get("type", "UNKNOWN")
        elif isinstance(spec.identity, dict) and (spec.identity.get("interface_type") or spec.identity.get("interface")):
            interface_type = spec.identity.get("interface_type") or spec.identity.get("interface")
        elif evidence_packet.cli_arguments:
            interface_type = "CLI"
        else:
            interface_type = "UNKNOWN"

        # 2. Public Inputs vs Internal State
        public_inputs: List[Dict[str, Any]] = []
        for opt in evidence_packet.cli_arguments:
            public_inputs.append({
                "name": opt.name,
                "flags": opt.flags,
                "type": opt.argument_type,
                "required": opt.required,
                "default": opt.default_value,
                "help_text": opt.help_text,
                "provenance": ProvenanceType.CODE_PROVEN.value,
                "source_file": opt.source_file,
                "line_number": opt.line_number
            })
        if not public_inputs and spec.inputs:
            for inp in spec.inputs:
                public_inputs.append({
                    "name": inp.name if hasattr(inp, "name") else inp.get("name", "input"),
                    "type": inp.type if hasattr(inp, "type") else inp.get("type", "string"),
                    "required": getattr(inp, "required", False),
                    "default": getattr(inp, "default", None),
                    "provenance": ProvenanceType.SEMANTIC_INFERENCE.value
                })

        # Public Outputs vs Intermediate State
        public_outputs: List[Dict[str, Any]] = []
        intermediate_artifacts: List[Dict[str, Any]] = []

        for out in evidence_packet.output_structures:
            out_dict = {
                "field_name": out.field_name,
                "field_type": out.field_type,
                "semantic_type": out.semantic_type,
                "description": out.description,
                "provenance": out.provenance.value,
                "source_file": out.source_file,
                "line_number": out.line_number
            }
            if out.provenance in (ProvenanceType.CODE_PROVEN, ProvenanceType.CONFIG_PROVEN):
                public_outputs.append(out_dict)
            else:
                intermediate_artifacts.append(out_dict)

        if not public_outputs and spec.outputs:
            for out in spec.outputs:
                public_outputs.append({
                    "field_name": out.name if hasattr(out, "name") else out.get("name", "result"),
                    "field_type": out.type if hasattr(out, "type") else out.get("type", "string"),
                    "provenance": ProvenanceType.DOC_DECLARED.value
                })

        # 3. User Tools vs Framework Primitives
        user_tools: List[Dict[str, Any]] = []
        framework_primitives: List[Dict[str, Any]] = []

        for tool in spec.tools:
            t_name = tool.name if hasattr(tool, "name") else tool.get("name", "")
            t_desc = tool.description if hasattr(tool, "description") else tool.get("description", "")
            t_risk = tool.risk if hasattr(tool, "risk") else tool.get("risk", "low")

            if t_name in FRAMEWORK_PRIMITIVES or t_name in LLM_CONSTRUCTORS:
                framework_primitives.append({
                    "name": t_name,
                    "type": "FRAMEWORK_PRIMITIVE",
                    "provenance": ProvenanceType.CODE_PROVEN.value
                })
            else:
                user_tools.append({
                    "name": t_name,
                    "description": t_desc,
                    "risk": t_risk.value if hasattr(t_risk, "value") else str(t_risk),
                    "provenance": ProvenanceType.CODE_PROVEN.value
                })

        # 4. LLM & Model Catalog
        detected_models: List[Dict[str, Any]] = []
        for llm_ev in evidence_packet.llm_constructors:
            detected_models.append({
                "provider": llm_ev.provider,
                "model_name": llm_ev.model_name,
                "certainty": llm_ev.model_certainty.value,
                "is_dynamic": llm_ev.is_dynamic_model,
                "temperature": llm_ev.temperature,
                "max_tokens": llm_ev.max_tokens,
                "source_class": llm_ev.source_class,
                "source_file": llm_ev.source_file,
                "line_number": llm_ev.line_number
            })

        # 5. Dependency & Credential Catalog
        package_dependencies: List[Dict[str, Any]] = []
        credentials: List[CanonicalCredentialDependency] = []
        seen_cred_names = set()

        for dep in spec.dependencies:
            dep_name = dep.name if hasattr(dep, "name") else dep.get("name", "")
            dep_type = dep.type if hasattr(dep, "type") else dep.get("type", "package")
            dep_type_str = dep_type.value if hasattr(dep_type, "value") else str(dep_type).lower()

            if dep_type_str in ("api_key", "secret", "credential", "service"):
                prov = dep_name.split("_")[0].title() if "_" in dep_name else dep_name.title()
                seen_cred_names.add(dep_name)
                credentials.append(CanonicalCredentialDependency(
                    name=dep_name,
                    provider=prov,
                    required=getattr(dep, "required", True),
                    state=DependencyState.USER_REQUIRED if getattr(dep, "required", True) else DependencyState.READY,
                    requires_user_value=True,
                    platform_has_compatible_default=(prov.upper() in {"OPENAI", "GEMINI", "GROQ", "OPENROUTER", "OLLAMA"}),
                    substitution_safe=False,
                    source_file=getattr(dep, "detected_from", "requirements.txt")
                ))
            else:
                package_dependencies.append({
                    "name": dep_name,
                    "type": dep_type_str,
                    "required": getattr(dep, "required", True),
                    "detected_from": getattr(dep, "detected_from", "requirements.txt"),
                    "state": DependencyState.READY.value
                })

        # Also extract credentials from evidence_packet environment_variables
        for env_var in evidence_packet.environment_variables:
            if env_var not in seen_cred_names and any(kw in env_var.upper() for kw in ("KEY", "SECRET", "TOKEN", "CREDENTIAL", "PASSWORD", "AUTH")):
                prov = env_var.split("_")[0].title() if "_" in env_var else env_var.title()
                seen_cred_names.add(env_var)
                credentials.append(CanonicalCredentialDependency(
                    name=env_var,
                    provider=prov,
                    required=True,
                    state=DependencyState.USER_REQUIRED,
                    requires_user_value=True,
                    platform_has_compatible_default=(prov.upper() in {"OPENAI", "GEMINI", "GROQ", "OPENROUTER", "OLLAMA"}),
                    substitution_safe=False,
                    source_file=entrypoint
                ))

        # 6. Workflow Graph
        workflow_nodes: List[Dict[str, Any]] = []
        workflow_edges: List[Dict[str, Any]] = []

        for node in spec.workflow:
            node_dict = node.model_dump() if hasattr(node, "model_dump") else (node.dict() if hasattr(node, "dict") else node)
            workflow_nodes.append(node_dict)

        for edge in evidence_packet.call_graph:
            workflow_edges.append({
                "source": edge.caller,
                "target": edge.callee,
                "is_conditional": edge.is_conditional,
                "source_file": edge.source_file,
                "line_number": edge.line_number
            })

        orchestration_mode = "state_graph" if any("StateGraph" in str(f) for f in evidence_packet.framework_constructs) else "sequential"

        # 7. Side Effects & Surfaces
        side_effects = [s.model_dump() for s in evidence_packet.side_effects]
        security_surfaces = [s.model_dump() for s in evidence_packet.security_surfaces]
        decision_surfaces = [d.model_dump() for d in evidence_packet.decision_surfaces]

        # 8. Contradictions & Known Unknowns
        contradictions: List[Dict[str, Any]] = []
        known_unknowns: List[str] = []

        if audit_report:
            for disc in audit_report.discrepancies:
                contradictions.append({
                    "type": disc.discrepancy_type if hasattr(disc, "discrepancy_type") else disc.get("discrepancy_type"),
                    "field": disc.field if hasattr(disc, "field") else disc.get("field"),
                    "claimed": disc.claimed_value if hasattr(disc, "claimed_value") else disc.get("claimed_value"),
                    "evidence": disc.evidence_fact if hasattr(disc, "evidence_fact") else disc.get("evidence_fact"),
                    "severity": disc.severity if hasattr(disc, "severity") else disc.get("severity")
                })

        # Detect Known Unknowns
        if not detected_models:
            known_unknowns.append("LLM Model constructor unstated in source code")
        if not public_inputs:
            known_unknowns.append("Explicit CLI/HTTP input contract unstated")
        if not public_outputs:
            known_unknowns.append("Explicit return output structure unstated")
        if not credentials:
            known_unknowns.append("No explicit API key secrets detected in AST")

        field_confidences = audit_report.field_confidences if audit_report else []
        overall_score = audit_report.overall_quality_score if audit_report else 85.0
        completeness_score = audit_report.completeness_score if audit_report else 0.85
        quality_gate = (audit_report.audit_verdict != "DEFECT") if audit_report else True

        return CanonicalIntake(
            artifact_id=evidence_packet.artifact_id,
            artifact_hash=artifact_hash or f"sha256:{evidence_packet.artifact_id}",
            agent_id=agent_id,
            agent_name=name,
            domain=domain,
            description=description,
            entrypoint=entrypoint,
            interface_type=interface_type,
            public_inputs=public_inputs,
            public_outputs=public_outputs,
            intermediate_artifacts=intermediate_artifacts,
            user_tools=user_tools,
            framework_primitives=framework_primitives,
            detected_models=detected_models,
            package_dependencies=package_dependencies,
            credentials=credentials,
            workflow_nodes=workflow_nodes,
            workflow_edges=workflow_edges,
            orchestration_mode=orchestration_mode,
            side_effects=side_effects,
            security_surfaces=security_surfaces,
            decision_surfaces=decision_surfaces,
            field_confidences=field_confidences,
            contradictions=contradictions,
            known_unknowns=known_unknowns,
            completeness_score=completeness_score,
            overall_quality_score=overall_score,
            quality_gate_passed=quality_gate
        )
