"""
Normalized Agent Specification Reconstructor and Universal Ingestion Pipeline.
"""

from __future__ import annotations

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
import ast
import logging

logger = logging.getLogger(__name__)


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
        if path.endswith((".py", ".ts", ".js", ".json", ".yaml", ".yml")):
            all_code_list.append(f"# --- {path} ---\n{content}\n")
            if path.endswith(".py"):
                try:
                    ast_trees[path] = ast.parse(content)
                except Exception:
                    pass
        elif path.endswith((".md", ".txt", "README", "metadata.yaml")):
            all_docs_list.append(f"# --- {path} ---\n{content}\n")

    all_code = "\n".join(all_code_list)
    all_docs = "\n".join(all_docs_list)

    # 1. AST Analysis for External Tools & Dependencies
    extracted_tools: List[ToolDefinition] = []
    extracted_deps: List[DependencyDefinition] = []

    for path, content in analysis_files.items():
        if path.endswith(".py"):
            res = analyze_python_source(content, filename=path)
            extracted_tools.extend(res.get("tools", []))
            extracted_deps.extend(res.get("dependencies", []))
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
    agent_category = DependencyDetector.classify_agent_category(all_code, detected_model_deps, dedup_tools, extracted_deps)

    # 3. Build Structured Evidence Packet
    typed_source_files = []
    for fpath, fcontent in analysis_files.items():
        lower_f = fpath.lower()
        if lower_f.endswith(".py"):
            ftype = "python"
        elif lower_f.endswith((".ts", ".js")):
            ftype = "javascript"
        elif lower_f.endswith((".md", ".txt", ".rst")):
            ftype = "documentation"
        elif "requirements" in lower_f or lower_f.endswith((".toml", ".lock")):
            ftype = "dependency_manifest"
        elif ".env" in lower_f:
            ftype = "configuration_template"
        elif lower_f.endswith((".yaml", ".yml", ".json")):
            ftype = "metadata"
        else:
            ftype = "file"
        typed_source_files.append({
            "path": fpath,
            "type": ftype,
            "content": fcontent
        })

    deterministic_evidence = {
        "ast": {
            "tools_count": len(dedup_tools),
            "tools": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in dedup_tools],
        },
        "framework": {
            "name": framework_name,
            "workflow_nodes_count": len(workflow_graph.nodes),
            "workflow_edges_count": len(workflow_graph.edges),
        },
        "services": service_facts,
        "credentials": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in detected_secrets],
        "dependencies": [d.model_dump() if hasattr(d, "model_dump") else d.dict() for d in extracted_deps],
        "runtime": runtime_manifest,
        "behavioral_facts": {
            "transformations": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in behavioral_facts.get("transformations", [])],
            "invariants": [inv.model_dump() if hasattr(inv, "model_dump") else inv.dict() for inv in behavioral_facts.get("invariants", [])],
            "failure_surfaces": [f.model_dump() if hasattr(f, "model_dump") else f.dict() for f in behavioral_facts.get("failure_surfaces", [])],
        }
    }

    evidence_packet = {
        "analysis_context": {
            "analysis_run_id": f"run-{hasher.hexdigest()[:8]}",
            "artifact_id": artifact_record.artifact_id,
            "agent_version_id": agent_id_temp,
            "input_type": payload.input_type,
            "agent_name_hint": payload.agent_name_hint
        },
        "source_files": typed_source_files,
        "deterministic_evidence": deterministic_evidence,
        "user_instructions": payload.pasted_prompt or None
    }

    t2_start = time.time()
    # 4. LLM Semantic Understanding via Structured Evidence Packet
    try:
        if hasattr(llm, "analyze_evidence_packet"):
            semantic_data = await llm.analyze_evidence_packet(evidence_packet)
        else:
            semantic_data = await llm.analyze(all_code, all_docs)
        semantic_status = "AI_ANALYSIS_COMPLETED"
    except Exception as e:
        logger.warning(f"LLM semantic analysis unavailable: {e}")
        semantic_data = {
            "name": payload.agent_name_hint or "Discovered Agent",
            "domain": "General AI Agent",
            "archetypes": ["UTILITY", "LLM_POWERED"] if agent_category.value == "llm_powered" else ["UTILITY"],
            "goals": [],
            "instructions": [],
            "status": "AI_ANALYSIS_FAILED"
        }
        semantic_status = "AI_ANALYSIS_FAILED"

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
    constitution = AgentConstitution(
        goals=semantic_data.get("goals", []),
        never_rules=semantic_data.get("never_rules", []),
        always_rules=semantic_data.get("always_rules", []),
        escalation_rules=semantic_data.get("escalation_rules", []),
        data_policies=semantic_data.get("data_policies", [])
    )

    # 4. Assemble AgentBehaviorProfile
    agent_name = semantic_data.get("name") or payload.agent_name_hint or "Discovered Agent"
    domain_name = semantic_data.get("domain") or "General AI Agent"

    behavior_profile = ProfileBuilder.build_behavior_profile(
        agent_id=agent_id_temp,
        agent_name=agent_name,
        domain=domain_name,
        workflow_graph=workflow_graph,
        capabilities=service_facts.get("capabilities", []),
        external_calls=service_facts.get("external_calls", []),
        credential_references=detected_secrets,
        transformations=behavioral_facts.get("transformations", []),
        invariants=behavioral_facts.get("invariants", []),
        failure_surfaces=behavioral_facts.get("failure_surfaces", []),
        state_model=behavioral_facts.get("state_model", {}),
        inputs=behavioral_facts.get("inputs", []),
        outputs=behavioral_facts.get("outputs", []),
        security_surfaces=behavioral_facts.get("security_surfaces", []),
        conflicts=behavioral_facts.get("conflicts", [])
    )

    # Compute derived execution status from behavior profile readiness breakdown
    derived_exec_status = "EXECUTION_READY" if behavior_profile.readiness.execution_ready else "EXECUTION_BLOCKED"

    # Attach detected secrets and model dependencies to runtime manifest
    runtime_manifest = _infer_runtime(analysis_files, payload.endpoint_url)
    runtime_manifest["agent_category"] = agent_category.value
    runtime_manifest["detected_model_dependencies"] = [m.model_dump() for m in detected_model_deps]
    runtime_manifest["detected_secrets"] = [s.model_dump() for s in detected_secrets]
    runtime_manifest["execution_status"] = derived_exec_status
    runtime_manifest["interface_contract"] = _infer_interface_contract(
        runtime_manifest, ast_trees, behavioral_facts, payload.endpoint_url
    )
    runtime_manifest["output_contract"] = _build_output_contract(behavioral_facts)

    # Combine canonical capabilities from ServiceDetector with LLM semantic capabilities
    canonical_caps = service_facts.get("capabilities", [])
    semantic_caps = semantic_data.get("capabilities", [])
    merged_caps = list(dict.fromkeys(canonical_caps + semantic_caps))

    norm_spec = NormalizedAgentSpec(
        identity={
            "name": agent_name,
            "domain": domain_name,
            "framework": framework_name,
            "language": runtime_manifest.get("runtime") or "python",
            "entrypoint": runtime_manifest.get("entrypoint") or "unknown",
            "category": agent_category.value
        },
        agent_description=f"Agent '{agent_name}' ({domain_name}) with {len(workflow_graph.nodes)} workflow nodes, {len(merged_caps)} capabilities ({', '.join(merged_caps)}), and {len(behavioral_facts.get('invariants', []))} invariants.",
        behavior_profile=behavior_profile,
        goals=constitution.goals,
        instructions=semantic_data.get("instructions", []),
        tools=dedup_tools,
        dependencies=extracted_deps,
        constitution=constitution,
        capabilities=merged_caps,
        archetypes=semantic_data.get("archetypes", ["UTILITY", "LLM_POWERED"] if agent_category.value == "llm_powered" else ["UTILITY"]),
        risks=semantic_data.get("risks", []),
        state_management="In-memory session state" if behavioral_facts.get("state_model") else "Stateless",
        architecture_components=semantic_data.get("architecture_components", [n.name for n in workflow_graph.nodes] if workflow_graph.nodes else []),
        runtime_manifest=runtime_manifest,
        execution_status=derived_exec_status,
    )

    t3_dur = (time.time() - t3_start) * 1000.0
    if tracker:
        tracker.complete_stage(3, duration_ms=round(t3_dur, 2), input_tokens=0, output_tokens=0)
        tracker.start_stage(4, {"deps_count": len(norm_spec.dependencies)})

    t4_start = time.time()
    # 4. Specification Conflict & Ambiguity Validation
    conflicts = detect_specification_conflicts(constitution, dedup_tools, all_code, all_docs)

    # 5. Visual Architecture Map Graph Generation
    nodes: List[GraphNode] = [
        GraphNode(id="node-agent", label=norm_spec.identity["name"], type="agent", risk="low", details="LLM Controller & Decision Engine")
    ]
    edges: List[GraphEdge] = []

    for tool in dedup_tools:
        tid = f"node-tool-{tool.name}"
        nodes.append(
            GraphNode(
                id=tid,
                label=f"{tool.name}()",
                type="tool",
                risk=tool.risk.value if hasattr(tool.risk, "value") else str(tool.risk),
                details=tool.description or f"Tool function {tool.name}"
            )
        )
        edges.append(GraphEdge(source="node-agent", target=tid, label="invokes"))

    # Backend target system nodes based on extracted dependencies
    for dep in norm_spec.dependencies:
        dep_node_id = f"node-{dep.id}"
        nodes.append(GraphNode(id=dep_node_id, label=dep.name, type=dep.type, risk="medium", details=f"External dependency: {dep.type}"))
        # Link relevant tools
        for tool in dedup_tools:
            tid = f"node-tool-{tool.name}"
            edges.append(GraphEdge(source=tid, target=dep_node_id, label="uses"))

    t4_dur = (time.time() - t4_start) * 1000.0
    if tracker:
        tracker.complete_stage(4, duration_ms=round(t4_dur, 2), input_tokens=0, output_tokens=0)

    return AgentUnderstandingResult(
        artifact=artifact_record,
        normalized_spec=norm_spec,
        conflicts=conflicts,
        confidence_score=96.4,
        ambiguities=[
            "Exact managerial authorization workflow for refunds above ₹10,000 is unstated in source code.",
            "Address update customer verification policy is unstated."
        ],
        graph_nodes=nodes,
        graph_edges=edges
    )
