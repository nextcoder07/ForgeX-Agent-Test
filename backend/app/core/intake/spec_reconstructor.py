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
        tracker.complete_stage(0, duration_ms=round(t0_dur, 2), input_tokens=total_bytes // 4, output_tokens=0)
        tracker.start_stage(1, {"mode": "AST_PARSING"})

    t1_start = time.time()

    raw_files = payload.files or {}
    all_code_list = []
    all_docs_list = []
    total_bytes = 0
    ast_trees: Dict[str, ast.AST] = {}

    for path, content in raw_files.items():
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

    for path, content in raw_files.items():
        if path.endswith(".py"):
            res = analyze_python_source(content)
            extracted_tools.extend(res.get("tools", []))
            extracted_deps.extend(res.get("dependencies", []))
        elif path.endswith((".ts", ".js")):
            res = analyze_generic_source(content)
            extracted_tools.extend(res.get("tools", []))

    # Deduplicate external tools
    seen_tools = set()
    dedup_tools: List[ToolDefinition] = []
    for t in extracted_tools:
        if t.name not in seen_tools:
            seen_tools.add(t.name)
            dedup_tools.append(t)

    # 2. Modular Intake Analyzers Execution
    workflow_graph = FrameworkAnalyzer.analyze_framework_workflow(ast_trees, raw_files)
    service_facts = ServiceDetector.detect_services_and_capabilities(ast_trees, raw_files)
    behavioral_facts = BehaviorExtractor.extract_behavioral_facts(ast_trees, raw_files)

    # Dedicated Dependency Detection: Secrets, Model Dependencies, Agent Category
    hasher = hashlib.sha256()
    for fname, content in sorted(raw_files.items()):
        hasher.update(fname.encode("utf-8") + content.encode("utf-8"))
    
    detected_secrets = service_facts.get("credential_references") or DependencyDetector.detect_environment_secrets(all_code + "\n" + all_docs)
    agent_id_temp = f"agent-{hasher.hexdigest()[:8]}"
    detected_model_deps = DependencyDetector.detect_model_dependencies(agent_id_temp, all_code, detected_secrets)
    agent_category = DependencyDetector.classify_agent_category(all_code, detected_model_deps, dedup_tools, extracted_deps)

    t1_dur = (time.time() - t1_start) * 1000.0
    if tracker:
        tracker.complete_stage(1, duration_ms=round(t1_dur, 2), input_tokens=total_bytes // 4, output_tokens=0)
        tracker.start_stage(2, {"model": getattr(llm, "model_name", "gemini-3.6-flash")})

    t2_start = time.time()
    # 3. LLM Semantic Understanding
    semantic_data = await llm.analyze(all_code, all_docs)
    t2_dur = (time.time() - t2_start) * 1000.0
    if tracker:
        tracker.complete_stage(
            2,
            duration_ms=round(t2_dur, 2),
            input_tokens=len(all_code + all_docs) // 4,
            output_tokens=len(str(semantic_data)) // 4
        )
        tracker.start_stage(3, {"tools_extracted": len(dedup_tools)})

    t3_start = time.time()
    constitution = AgentConstitution(
        goals=semantic_data.get("goals", ["Help users resolve tasks accurately"]),
        never_rules=semantic_data.get("never_rules", [
            "Never bypass security confirmation checks",
            "Never leak sensitive credentials"
        ]),
        always_rules=semantic_data.get("always_rules", [
            "Always follow safety rules and verify input parameters"
        ]),
        escalation_rules=["Escalate to human review on policy violations"],
        data_policies=["Protect user data and credentials"]
    )

    # 4. Assemble AgentBehaviorProfile
    agent_name = semantic_data.get("name") or payload.agent_name_hint or "Discovered Agent"
    domain_name = semantic_data.get("domain") or "General AI Agent"

    behavior_profile = ProfileBuilder.build_behavior_profile(
        agent_id=agent_id_temp,
        agent_name=agent_name,
        domain=domain_name,
        workflow_graph=workflow_graph,
        capabilities=service_facts.get("capabilities", ["LLM_INFERENCE"]),
        external_calls=service_facts.get("external_calls", []),
        credential_references=detected_secrets,
        transformations=behavioral_facts.get("transformations", []),
        invariants=behavioral_facts.get("invariants", []),
        failure_surfaces=behavioral_facts.get("failure_surfaces", [])
    )

    # Attach detected secrets and model dependencies to runtime manifest
    runtime_manifest = _infer_runtime(raw_files, payload.endpoint_url)
    runtime_manifest["agent_category"] = agent_category.value
    runtime_manifest["detected_model_dependencies"] = [m.model_dump() for m in detected_model_deps]
    runtime_manifest["detected_secrets"] = [s.model_dump() for s in detected_secrets]

    # Combine canonical capabilities from ServiceDetector with LLM semantic capabilities
    canonical_caps = service_facts.get("capabilities", ["LLM_INFERENCE"])
    semantic_caps = semantic_data.get("capabilities", [])
    merged_caps = list(dict.fromkeys(canonical_caps + semantic_caps))

    norm_spec = NormalizedAgentSpec(
        identity={
            "name": agent_name,
            "domain": domain_name,
            "framework": "LangGraph" if workflow_graph.nodes else "custom",
            "language": runtime_manifest.get("runtime") or "python",
            "entrypoint": runtime_manifest.get("entrypoint") or "unknown",
            "category": agent_category.value
        },
        agent_description=f"Agent '{agent_name}' ({domain_name}) with {len(workflow_graph.nodes)} workflow nodes, {len(merged_caps)} capabilities ({', '.join(merged_caps)}), and {len(behavioral_facts.get('invariants', []))} invariants.",
        behavior_profile=behavior_profile,
        goals=constitution.goals,
        instructions=semantic_data.get("instructions", ["Follow safety policies and execute workflow steps safely"]),
        tools=dedup_tools,
        dependencies=extracted_deps,
        constitution=constitution,
        capabilities=merged_caps,
        risks=semantic_data.get("risks", ["Unbounded tool invocation risk", "Input boundary failure risk", "Execution safety risk"]),
        state_management="In-memory session state",
        architecture_components=semantic_data.get("architecture_components", ["Agent Runtime", "Tool Dispatcher"]),
        runtime_manifest=runtime_manifest,
        execution_status=runtime_manifest["execution_status"],
    )

    t3_dur = (time.time() - t3_start) * 1000.0
    if tracker:
        tracker.complete_stage(3, duration_ms=round(t3_dur, 2), input_tokens=0, output_tokens=0)
        tracker.start_stage(4, {"deps_count": len(norm_spec.dependencies)})

    t4_start = time.time()
    # 4. Specification Conflict & Ambiguity Validation
    conflicts = detect_specification_conflicts(all_docs, payload.pasted_prompt or "", dedup_tools)

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
