"""
Normalized Agent Specification Reconstructor and Universal Ingestion Pipeline.
"""

from __future__ import annotations

import json
import hashlib
import datetime as dt
from typing import Any, Dict, List
from app.models.agent import ToolDefinition, ToolRisk, DependencyDefinition, AgentConstitution
from app.models.intake import (
    AgentIntakePayload,
    AgentUnderstandingResult,
    NormalizedAgentSpec,
    ArtifactRecord,
    GraphNode,
    GraphEdge,
)
from app.core.intake.ast_analyzer import analyze_python_source, analyze_generic_source
from app.core.intake.conflict_detector import detect_specification_conflicts
from app.core.intake.dependency_detector import DependencyDetector, redact_secret_string
from app.core.intake.framework_analyzer import FrameworkAnalyzer
from app.core.intake.service_detector import ServiceDetector
from app.core.intake.behavior_extractor import BehaviorExtractor
from app.core.intake.profile_builder import ProfileBuilder
from app.core.llm.base import LLMProvider
from app.services.activity_log import activity_log
import ast
import logging
from enum import Enum
import uuid
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def to_json_safe(val: Any) -> Any:
    """Recursively converts any object (Pydantic models, dataclasses, Enums, UUIDs, datetimes, sets) into standard JSON-serializable primitives."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, BaseModel):
        if hasattr(val, "model_dump"):
            return to_json_safe(val.model_dump(mode="json"))
        return to_json_safe(val.dict())
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (dt.datetime, dt.date)):
        return val.isoformat()
    if isinstance(val, (uuid.UUID, Path)):
        return str(val)
    if isinstance(val, dict):
        return {str(k): to_json_safe(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [to_json_safe(item) for item in val]
    if hasattr(val, "__dict__"):
        return to_json_safe(vars(val))
    return str(val)


def _now() -> str:
    return dt.datetime.utcnow().isoformat()


def _infer_runtime(files: Dict[str, str], endpoint_url: str = None) -> Dict[str, Any]:
    paths = sorted(files)
    lower_paths = [path.lower() for path in paths]
    python_files = [path for path in paths if path.lower().endswith(".py")]
    node_files = [path for path in paths if path.lower().endswith((".ts", ".tsx", ".js", ".jsx"))]
    has_python_manifest = any(path.endswith(("requirements.txt", "pyproject.toml", "poetry.lock")) for path in lower_paths)
    has_node_manifest = any(path.endswith(("package.json", "package-lock.json")) for path in lower_paths)

    if endpoint_url:
        return {"runtime": "endpoint", "endpoint_url": endpoint_url, "entrypoint": None, "execution_status": "READY"}
    if has_node_manifest or node_files:
        runtime = "node"
        candidates = [path for path in node_files if path.lower().endswith(("/index.ts", "/index.js", "index.ts", "index.js", "agent.ts", "agent.js"))]
        entrypoint = candidates[0] if candidates else (node_files[0] if len(node_files) == 1 else None)
        install = "npm install" if has_node_manifest else None
    elif has_python_manifest or python_files:
        runtime = "python"
        candidates = [path for path in python_files if path.lower().endswith(("/main.py", "/run.py", "/agent.py", "main.py", "run.py", "agent.py"))]
        entrypoint = candidates[0] if candidates else (python_files[0] if len(python_files) == 1 else None)
        install = "pip install -r requirements.txt" if any(path.lower().endswith("requirements.txt") for path in paths) else None
    else:
        return {"runtime": None, "entrypoint": None, "execution_status": "EXECUTION_BLOCKED"}

    return {
        "runtime": runtime,
        "entrypoint": entrypoint,
        "install": install,
        "execution_status": "READY" if entrypoint else "EXECUTION_BLOCKED",
    }


def _infer_interface_contract(
    runtime_manifest: Dict[str, Any],
    ast_trees: Dict[str, ast.AST],
    behavioral_facts: Dict[str, Any],
    endpoint_url: str = None,
) -> Dict[str, Any]:
    if endpoint_url or runtime_manifest.get("runtime") == "endpoint":
        interface_type = "HTTP"
    else:
        has_argparse = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "argparse"
            and node.func.attr == "ArgumentParser"
            for tree in ast_trees.values()
            for node in ast.walk(tree)
        )
        interface_type = "CLI" if has_argparse else "FUNCTION"

    arguments: List[Dict[str, Any]] = []
    for tree in ast_trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "add_argument" or not node.args:
                continue
            flags = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
            if not flags:
                continue
            kwargs = {
                keyword.arg: keyword.value.value
                for keyword in node.keywords
                if keyword.arg in {"required", "default", "type"}
                and isinstance(keyword.value, ast.Constant)
            }
            arguments.append({"flags": flags, **kwargs})

    return {
        "type": interface_type,
        "entrypoint": runtime_manifest.get("entrypoint"),
        "endpoint_url": endpoint_url,
        "arguments": arguments,
        "inputs": behavioral_facts.get("inputs", []),
        "stdin": False,
    }


def _build_output_contract(behavioral_facts: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "outputs": behavioral_facts.get("outputs", []),
        "transformations": [t.model_dump() for t in behavioral_facts.get("transformations", [])],
        "observed_invariants": [i.model_dump() for i in behavioral_facts.get("invariants", [])],
    }


async def process_agent_intake(
    payload: AgentIntakePayload,
    llm: LLMProvider,
    tracker: Any = None
) -> AgentUnderstandingResult:
    import time
    t0_start = time.time()
    if tracker:
        tracker.start_stage(0, {"file_count": len(payload.files)})

    # 1. Compute Immutable SHA256 Artifact Hash
    hasher = hashlib.sha256()
    total_bytes = 0
    file_list = []

    for fname, content in sorted(payload.files.items()):
        file_list.append(fname)
        encoded = content.encode("utf-8")
        hasher.update(fname.encode("utf-8") + encoded)
        total_bytes += len(encoded)

    if payload.pasted_code:
        hasher.update(payload.pasted_code.encode("utf-8"))
        total_bytes += len(payload.pasted_code)
        file_list.append("pasted_source.py")

    if payload.pasted_prompt:
        hasher.update(payload.pasted_prompt.encode("utf-8"))
        total_bytes += len(payload.pasted_prompt)
        file_list.append("system_prompt.txt")

    artifact_hash = f"sha256:{hasher.hexdigest()}"
    runtime_files = dict(payload.files)
    if payload.pasted_code:
        runtime_files["pasted_source.py"] = payload.pasted_code
    runtime_manifest = _infer_runtime(runtime_files, payload.endpoint_url)
    artifact_record = ArtifactRecord(
        artifact_id=f"art-{hasher.hexdigest()[:12]}",
        artifact_hash=artifact_hash,
        file_count=len(file_list),
        total_bytes=total_bytes,
        files_list=file_list,
        input_type=payload.input_type,
        created_at=_now()
    )

    t0_dur = (time.time() - t0_start) * 1000.0
    if tracker:
        tracker.complete_stage(0, duration_ms=round(t0_dur, 2), input_tokens=0, output_tokens=0)
        tracker.start_stage(1, {"mode": "AST_PARSING"})

    t1_start = time.time()

    raw_files = dict(payload.files or {})
    if payload.pasted_code:
        raw_files["pasted_source.py"] = payload.pasted_code
    if payload.pasted_prompt:
        raw_files["system_prompt.txt"] = payload.pasted_prompt

    analysis_files = raw_files
    all_code_list = []
    all_docs_list = []
    total_bytes = 0
    ast_trees: Dict[str, ast.AST] = {}

    for path, content in analysis_files.items():
        total_bytes += len(content.encode("utf-8"))
        lower_p = path.lower()
        if lower_p.endswith((".py", ".ts", ".js", ".json", ".yaml", ".yml", ".toml", ".sh", ".sql")):
            all_code_list.append(f"# --- {path} ---\n{content}\n")
            if lower_p.endswith(".py"):
                try:
                    ast_trees[path] = ast.parse(content)
                except Exception:
                    pass
        else:
            all_docs_list.append(f"# --- {path} ---\n{content}\n")

    all_code = "\n".join(all_code_list)
    all_docs = "\n".join(all_docs_list)

    # 1. AST Analysis for External Tools & Dependencies
    extracted_tools: List[ToolDefinition] = []
    extracted_deps: List[DependencyDefinition] = []
    ast_info = {"docstrings": []}

    for path, content in analysis_files.items():
        if path.endswith(".py"):
            res = analyze_python_source(content, filename=path)
            extracted_tools.extend(res.get("tools", []))
            extracted_deps.extend(res.get("dependencies", []))
            if res.get("docstring"):
                ast_info["docstrings"].append(res["docstring"])
        elif path.endswith((".ts", ".js")):
            res = analyze_generic_source(content, filename=path)
            extracted_tools.extend(res.get("tools", []))

    # Deduplicate external tools
    seen_tools = set()
    dedup_tools: List[ToolDefinition] = []
    for t in extracted_tools:
        if t.name not in seen_tools:
            seen_tools.add(t.name)
            dedup_tools.append(t)

    # 2. Modular Intake Analyzers Execution
    fw_result = FrameworkAnalyzer.analyze_framework_workflow(ast_trees, analysis_files)
    workflow_graph = fw_result["workflow_graph"]
    framework_name = fw_result["framework"]
    
    service_facts = ServiceDetector.detect_services_and_capabilities(ast_trees, analysis_files)
    behavioral_facts = BehaviorExtractor.extract_behavioral_facts(ast_trees, analysis_files)

    # Detect package & framework dependencies
    package_deps = DependencyDetector.detect_runtime_packages(all_code, analysis_files)
    for pd in package_deps:
        if not any(d.name == pd.name for d in extracted_deps):
            extracted_deps.append(pd)

    # Dedicated Dependency Detection: Secrets, Model Dependencies, Agent Category
    hasher = hashlib.sha256()
    for fname, content in sorted(analysis_files.items()):
        hasher.update(fname.encode("utf-8") + content.encode("utf-8"))
    
    detected_secrets = service_facts.get("credential_references") or DependencyDetector.detect_environment_secrets(all_code + "\n" + all_docs)
    agent_id_temp = f"agent-{hasher.hexdigest()[:8]}"
    detected_model_deps = DependencyDetector.detect_model_dependencies(agent_id_temp, all_code, detected_secrets)
    runtime_manifest["detected_model_dependencies"] = [
        d.model_dump() if hasattr(d, "model_dump") else d.dict() if hasattr(d, "dict") else d
        for d in detected_model_deps
    ]
    agent_category = DependencyDetector.classify_agent_category(all_code, detected_model_deps, dedup_tools, extracted_deps)

    # 3. Build Authoritative Deterministic Evidence Packet
    from app.core.intake.evidence_builder import EvidencePacketBuilder
    canonical_evidence_packet = EvidencePacketBuilder.build_packet(
        source_files=analysis_files,
        artifact_id=artifact_record.artifact_id,
        entrypoint=runtime_manifest.get("entrypoint", "agent.py")
    )

    deterministic_evidence = {
        "ast": {
            "tools_count": len(dedup_tools),
            "tools": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in dedup_tools],
            "cli_arguments": [opt.model_dump() for opt in canonical_evidence_packet.cli_arguments],
            "llm_constructors": [llm.model_dump() for llm in canonical_evidence_packet.llm_constructors],
        },
        "framework": {
            "name": framework_name,
            "constructs": canonical_evidence_packet.framework_constructs,
            "workflow_nodes_count": len(workflow_graph.nodes),
            "workflow_edges_count": len(workflow_graph.edges),
        },
        "services": service_facts,
        "credentials": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in detected_secrets],
        "dependencies": [d.model_dump() if hasattr(d, "model_dump") else d.dict() for d in extracted_deps],
        "runtime": runtime_manifest,
        "security_surfaces": [s.model_dump() for s in canonical_evidence_packet.security_surfaces],
        "call_graph": [e.model_dump() for e in canonical_evidence_packet.call_graph],
        "behavioral_facts": {
            "transformations": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in behavioral_facts.get("transformations", [])],
            "invariants": [inv.model_dump() if hasattr(inv, "model_dump") else inv.dict() for inv in behavioral_facts.get("invariants", [])],
            "failure_surfaces": [f.model_dump() if hasattr(f, "model_dump") else f.dict() for f in behavioral_facts.get("failure_surfaces", [])],
            "inputs": [opt.name for opt in canonical_evidence_packet.cli_arguments] or behavioral_facts.get("inputs", []),
            "outputs": behavioral_facts.get("outputs", []),
            "security_surfaces": behavioral_facts.get("security_surfaces", []),
            "conflicts": [c.model_dump() if hasattr(c, "model_dump") else c for c in behavioral_facts.get("conflicts", [])],
            "interface_details": behavioral_facts.get("interface_details", {}),
            "state_model": behavioral_facts.get("state_model", {})
        }
    }

    safe_deterministic_evidence = to_json_safe(deterministic_evidence)

    typed_source_files = [{"path": fpath, "content": fcontent} for fpath, fcontent in analysis_files.items()]

    evidence_packet = {
        "analysis_context": {
            "analysis_run_id": f"run-{hasher.hexdigest()[:8]}",
            "artifact_id": artifact_record.artifact_id,
            "agent_version_id": agent_id_temp,
            "input_type": payload.input_type,
            "agent_name_hint": payload.agent_name_hint
        },
        "analysis_contract": {
            "instruction": "Reconstruct the behavioral specification strictly from the supplied deterministic evidence facts. Do NOT hallucinate tools, dependencies, or inputs. For inferred properties, distinguish FACT from INFERRED. Mark unstated properties as UNKNOWN.",
            "required_outputs": [
                "identity",
                "interface_contract",
                "output_contract",
                "workflow",
                "capabilities",
                "dependencies",
                "credentials",
                "dataflows",
                "invariants",
                "failure_surfaces",
                "security_surfaces",
                "fallbacks",
                "readiness"
            ]
        },
        "source_files": typed_source_files,
        "deterministic_evidence": safe_deterministic_evidence,
        "evidence_items": [item.model_dump() for item in canonical_evidence_packet.evidence_items],
        "user_instructions": payload.pasted_prompt or None
    }

    safe_evidence_packet = to_json_safe(evidence_packet)
    serialized_bytes = len(json.dumps(safe_evidence_packet))

    activity_log.emit(
        category="INTAKE",
        action="EVIDENCE_PACKET_READY",
        detail=f"Evidence packet normalized: {len(typed_source_files)} files, {len(canonical_evidence_packet.evidence_items)} static evidence items ({serialized_bytes} bytes).",
        request_summary=f"Run: run-{hasher.hexdigest()[:8]} | Size: {serialized_bytes}b",
        status="success"
    )

    t2_start = time.time()
    # 4. LLM Semantic Understanding via Structured Evidence Packet & Pydantic Validation
    try:
        activity_log.emit(
            category="INTAKE",
            action="GEMINI_SEMANTIC_START",
            detail="Calling Gemini Semantic Analyzer with normalized evidence packet...",
            status="success"
        )
        if hasattr(llm, "analyze_evidence_packet"):
            semantic_raw = await llm.analyze_evidence_packet(safe_evidence_packet)
        else:
            semantic_raw = await llm.analyze(all_code, all_docs)
        
        # Strict Pydantic Schema Validation
        from app.models.intake import AgentAnalysisResponse
        validated_response = AgentAnalysisResponse.model_validate(semantic_raw)
        semantic_status = "AI_ANALYSIS_COMPLETED"
        analysis_status = "COMPLETE"
        activity_log.emit(
            category="INTAKE",
            action="GEMINI_SEMANTIC_SUCCESS",
            detail=f"Gemini semantic analysis completed for {validated_response.name}.",
            status="success"
        )
    except Exception as e:
        logger.warning(f"LLM semantic analysis schema error / failure: {e}")
        from app.models.intake import AgentAnalysisResponse
        
        # Try to parse metadata.yaml / metadata.json / metadata.yml if present
        manifest_facts = {}
        for fname, content in analysis_files.items():
            if "metadata" in fname.lower() and (fname.endswith(".yaml") or fname.endswith(".yml")):
                try:
                    import yaml
                    manifest_facts = yaml.safe_load(content) or {}
                except Exception:
                    pass
            elif "metadata" in fname.lower() and fname.endswith(".json"):
                try:
                    manifest_facts = json.loads(content) or {}
                except Exception:
                    pass

        # Build robust deterministic fallback facts from metadata, docstrings, and invariants
        fallback_name = manifest_facts.get("title") or manifest_facts.get("name") or payload.agent_name_hint or "Discovered Agent"
        fallback_domain = manifest_facts.get("industry") or manifest_facts.get("domain") or "General"
        fallback_goals = []
        if manifest_facts.get("description"):
            fallback_goals.append(str(manifest_facts["description"]))
        if ast_info.get("docstrings"):
            for d in ast_info["docstrings"][:2]:
                first_line = d.strip().split("\n")[0].strip()
                if len(first_line) > 10 and not any(first_line in g for g in fallback_goals):
                    fallback_goals.append(first_line)
        if not fallback_goals:
            fallback_goals = [f"Execute {fallback_domain} workflow and process inputs."]

        fallback_always = [
            inv.statement if hasattr(inv, "statement") else inv.get("statement", "")
            for inv in behavioral_facts.get("invariants", [])
        ][:5]

        validated_response = AgentAnalysisResponse(
            name=fallback_name,
            domain=fallback_domain,
            archetypes=["CLI_PROCESSOR", "LLM_POWERED"] if "cli" in fallback_name.lower() or "news" in fallback_name.lower() else (["UTILITY", "LLM_POWERED"] if agent_category.value == "llm_powered" else ["UTILITY"]),
            goals=fallback_goals,
            instructions=[d for d in ast_info.get("docstrings", [])[:2]],
            always_rules=fallback_always,
            never_rules=[],
            escalation_rules=[],
            data_policies=[f"Enforce observed code invariants: {', '.join(fallback_always[:2])}"] if fallback_always else []
        )
        semantic_status = "AI_ANALYSIS_SCHEMA_ERROR" if "validation" in str(e).lower() else "AI_ANALYSIS_FAILED"
        analysis_status = "PARTIAL"
        activity_log.emit(
            category="INTAKE",
            action="GEMINI_SEMANTIC_FAILED",
            detail=f"Gemini semantic analysis failed ({semantic_status}): {e}. Preserving deterministic AST facts.",
            status="warning"
        )

    t2_dur = (time.time() - t2_start) * 1000.0
    if tracker:
        tracker.complete_stage(
            2,
            duration_ms=round(t2_dur, 2),
            input_tokens=getattr(llm, "last_input_tokens", 0),
            output_tokens=getattr(llm, "last_output_tokens", 0)
        )
        tracker.start_stage(3, {"tools_extracted": len(dedup_tools)})

    t3_start = time.time()
    # 5. Profile Merger: Precedence (Observed Deterministic > Declared Documentation > Gemini Inference)
    from app.core.intake.profile_merger import ProfileMerger
    norm_spec, behavior_profile, merged_conflicts = ProfileMerger.merge_profiles(
        deterministic_evidence=safe_deterministic_evidence,
        semantic_response=validated_response,
        artifact_id=artifact_record.artifact_id,
        agent_version_id=agent_id_temp,
        input_type=payload.input_type,
        agent_name_hint=payload.agent_name_hint,
        custom_instructions=payload.pasted_prompt
    )
    norm_spec.semantic_status = semantic_status
    norm_spec.analysis_status = analysis_status
    constitution = norm_spec.constitution

    t3_dur = (time.time() - t3_start) * 1000.0
    if tracker:
        tracker.complete_stage(3, duration_ms=round(t3_dur, 2), input_tokens=0, output_tokens=0)
        tracker.start_stage(4, {"deps_count": len(norm_spec.dependencies)})

    t4_start = time.time()
    # 4. Canonical Subsystem Extraction & Architecture Synthesis
    from app.core.intake.subsystem_detector import SubsystemDetector
    canonical_subsystems = SubsystemDetector.analyze_source_files(
        agent_id=agent_id_temp,
        agent_name=norm_spec.identity.get("name", payload.agent_name_hint or "Discovered Agent"),
        files=analysis_files
    )
    norm_spec.canonical_subsystems = canonical_subsystems

    # 5. Specification Conflict & Ambiguity Validation
    conflicts = detect_specification_conflicts(constitution, dedup_tools, all_code, all_docs)

    # 6. Visual Architecture Map Graph Generation
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    # Center / Core Agent Node
    main_agent_id = "node-agent-core"
    nodes.append(GraphNode(
        id=main_agent_id,
        label=norm_spec.identity["name"],
        type="agent",
        risk="low",
        details=f"Core Controller ({canonical_subsystems.archetype})"
    ))

    # Add Model Slot Nodes
    for slot in canonical_subsystems.model_slots:
        slot_node_id = f"node-slot-{slot.slot_id}"
        nodes.append(GraphNode(
            id=slot_node_id,
            label=slot.name,
            type="subagent" if "reviewer" in slot.role.value.lower() or "planner" in slot.role.value.lower() else "agent",
            risk="low",
            details=f"Role: {slot.role.value} | Model: {slot.detected_model} ({slot.detected_provider})"
        ))
        edges.append(GraphEdge(source=main_agent_id, target=slot_node_id, label="powers"))

    # Add Planning Node if planning present
    if canonical_subsystems.planning.planning_present:
        plan_node_id = "node-subsystem-planning"
        nodes.append(GraphNode(
            id=plan_node_id,
            label=f"Planning ({canonical_subsystems.planning.planning_type.value})",
            type="agent",
            risk="low",
            details=f"Strategy: {canonical_subsystems.planning.planning_type.value} | Dynamic: {canonical_subsystems.planning.dynamic_replanning}"
        ))
        edges.append(GraphEdge(source=main_agent_id, target=plan_node_id, label="orchestrates"))

    # Add Memory Subsystem Node if memory present
    if canonical_subsystems.memory.memory_present:
        mem_node_id = "node-subsystem-memory"
        nodes.append(GraphNode(
            id=mem_node_id,
            label=f"Memory ({canonical_subsystems.memory.storage_backend})",
            type="memory",
            risk="low",
            details=f"Scope: {canonical_subsystems.memory.persistence_scope} | Types: {', '.join(t.value for t in canonical_subsystems.memory.memory_types)}"
        ))
        edges.append(GraphEdge(source=main_agent_id, target=mem_node_id, label="reads/writes"))

    # Add Context / RAG Node if RAG present
    if canonical_subsystems.context.retrieval_present:
        rag_node_id = "node-subsystem-rag"
        nodes.append(GraphNode(
            id=rag_node_id,
            label="RAG Retriever",
            type="database",
            risk="low",
            details=f"Retriever: {canonical_subsystems.context.retriever or 'VectorStore'} | Backend: {canonical_subsystems.context.retrieval_backend}"
        ))
        edges.append(GraphEdge(source=main_agent_id, target=rag_node_id, label="queries"))

    # Add Tool Nodes
    for tool in canonical_subsystems.tools:
        tid = f"node-tool-{tool.name}"
        nodes.append(
            GraphNode(
                id=tid,
                label=f"{tool.name}()",
                type="tool",
                risk="critical" if tool.destructive else ("high" if tool.authorization_required else "low"),
                details=tool.description or f"Tool function: {tool.name}"
            )
        )
        edges.append(GraphEdge(source=main_agent_id, target=tid, label="invokes"))

    # Add External Service Nodes
    for svc in canonical_subsystems.external_services:
        sid = f"node-svc-{svc.service_id}"
        nodes.append(GraphNode(
            id=sid,
            label=f"{svc.provider} Gateway",
            type="api",
            risk="medium",
            details=f"External Service Provider: {svc.provider} ({svc.mock_adapter})"
        ))
        edges.append(GraphEdge(source=main_agent_id, target=sid, label="integrates"))

    # Fallback to general tool list if canonical tools empty
    if not canonical_subsystems.tools and dedup_tools:
        for tool in dedup_tools:
            tid = f"node-tool-{tool.name}"
            if not any(n.id == tid for n in nodes):
                nodes.append(GraphNode(id=tid, label=f"{tool.name}()", type="tool", risk=str(tool.risk), details=tool.description or ""))
                edges.append(GraphEdge(source=main_agent_id, target=tid, label="invokes"))

    # 7. Authoritative Hard Intake Gate Validation & Secret Scrubbing
    from app.core.intake.intake_validator import IntakeValidator
    validation_gate = IntakeValidator.validate_and_remediate(
        spec=norm_spec,
        source_files=analysis_files,
        agent_name_hint=payload.agent_name_hint or ""
    )
    norm_spec = validation_gate.remediated_spec

    # Synchronize purged tools with canonical subsystems
    if validation_gate.purged_tools:
        canonical_subsystems.tools = [t for t in canonical_subsystems.tools if t.name not in validation_gate.purged_tools]
        nodes = [n for n in nodes if not any(f"node-tool-{pt}" == n.id for pt in validation_gate.purged_tools)]
        edges = [e for e in edges if not any(f"node-tool-{pt}" in (e.source, e.target) for pt in validation_gate.purged_tools)]

    # 8. 4-Layer Intake Quality Audit
    from app.core.intake.intake_auditor import IntakeAuditor
    audit_report = IntakeAuditor.audit_spec_against_evidence(norm_spec, canonical_evidence_packet)

    t4_dur = (time.time() - t4_start) * 1000.0
    if tracker:
        tracker.complete_stage(4, duration_ms=round(t4_dur, 2), input_tokens=0, output_tokens=0)

    ambiguities = [
        "Exact managerial authorization workflow for sensitive actions is unstated in source code.",
        "Session isolation parameters across concurrent invocations require runtime verification."
    ]
    if validation_gate.validation_errors:
        ambiguities = validation_gate.validation_errors + ambiguities

    return AgentUnderstandingResult(
        artifact=artifact_record,
        normalized_spec=norm_spec,
        agent_description=norm_spec.agent_description,
        behavior_profile=behavior_profile,
        canonical_subsystems=canonical_subsystems,
        conflicts=conflicts,
        confidence_score=audit_report.overall_quality_score if validation_gate.is_valid and analysis_status == "COMPLETE" else 82.0,
        ambiguities=ambiguities,
        graph_nodes=nodes,
        graph_edges=edges,
        audit_report=audit_report.model_dump(),
        evidence_packet=canonical_evidence_packet.model_dump(),
        semantic_status=semantic_status,
        analysis_status=analysis_status
    )

