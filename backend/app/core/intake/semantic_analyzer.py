"""
Agent Intake & Semantic Analyzer for Member 1.
Statically analyzes agent directories and extracts semantic specifications.
"""
from __future__ import annotations

import os
import uuid
import yaml  # In requirements, supabase/fastapi apps usually have yaml or we fallback safely
from typing import Any, Dict, List, Optional

from app.models.agent import ToolDefinition, DependencyDefinition
from app.models.agent_test_spec import AgentTestSpecification, Capability
from app.core.intake.ast_analyzer import analyze_python_source, analyze_generic_source
from app.core.intake.capability_extractor import CapabilityExtractor
from app.core.llm.gemini_provider import GeminiProvider
from app.core.llm.fallback_mock import FallbackMockEngine

def _parse_yaml_metadata(filepath: str) -> Dict[str, Any]:
    """Parse YAML metadata safely."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Simple line parsing if yaml module is somehow missing, but we attempt yaml first
            try:
                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
            
            # Simple fallback parser
            data = {}
            for line in content.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip().strip("'\"")
            return data
    except Exception:
        return {}

async def analyze_agent(agent_path: str, api_key: Optional[str] = None) -> AgentTestSpecification:
    """
    Main entrypoint: Understands an arbitrary AI agent, extracts semantic capabilities,
    and returns an AgentTestSpecification.
    """
    if not os.path.exists(agent_path):
        raise FileNotFoundError(f"Agent path '{agent_path}' does not exist.")

    # 1. Walk files and collect code/documentation evidence
    code_evidence_list: List[str] = []
    doc_evidence_list: List[str] = []
    
    extracted_tools: List[ToolDefinition] = []
    extracted_deps: List[DependencyDefinition] = []
    
    metadata: Dict[str, Any] = {}
    
    # Track files to compile manifest/details
    for root, _, files in os.walk(agent_path):
        for file in files:
            fpath = os.path.join(root, file)
            rel_path = os.path.relpath(fpath, agent_path).replace(os.sep, "/")
            
            # Skip hidden folders or build directories
            if any(part.startswith(".") for part in rel_path.split("/")):
                continue
                
            lower_name = file.lower()
            if lower_name.endswith((".yaml", ".yml")):
                if "metadata" in lower_name:
                    metadata.update(_parse_yaml_metadata(fpath))
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        doc_evidence_list.append(f"### File: {rel_path}\n{f.read()}")
                except Exception:
                    pass
            elif lower_name.endswith((".md", ".txt", ".json")):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        doc_evidence_list.append(f"### File: {rel_path}\n{f.read()}")
                except Exception:
                    pass
            elif lower_name.endswith(".py"):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        code_evidence_list.append(f"# File: {rel_path}\n{content}")
                        # AST static parsing
                        ast_res = analyze_python_source(content)
                        extracted_tools.extend(ast_res.get("tools", []))
                        extracted_deps.extend(ast_res.get("dependencies", []))
                except Exception:
                    pass
            elif lower_name.endswith((".ts", ".tsx", ".js", ".jsx")):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        code_evidence_list.append(f"// File: {rel_path}\n{content}")
                        # Generic regex tools extraction
                        gen_res = analyze_generic_source(content)
                        extracted_tools.extend(gen_res.get("tools", []))
                except Exception:
                    pass

    # Deduplicate tools
    seen_tools = set()
    dedup_tools = []
    for t in extracted_tools:
        if t.name not in seen_tools:
            seen_tools.add(t.name)
            dedup_tools.append(t)

    # Deduplicate dependencies
    seen_deps = set()
    dedup_deps = []
    for d in extracted_deps:
        if d.id not in seen_deps:
            seen_deps.add(d.id)
            dedup_deps.append(d)

    code_evidence = "\n\n".join(code_evidence_list)
    doc_evidence = "\n\n".join(doc_evidence_list)

    # 2. Extract semantic data from LLM or fallback
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    name_hint = metadata.get("title") or metadata.get("name") or os.path.basename(os.path.normpath(agent_path))
    
    # Try calling LLM Provider
    from app.core.llm.providers import get_platform_provider
    provider = get_platform_provider()
    
    # Check if Gemini key is available or fallback
    if api_key or os.getenv("GEMINI_API_KEY"):
        try:
            semantic_data = await provider.analyze(code_evidence, doc_evidence)
        except Exception:
            semantic_data = FallbackMockEngine.mock_agent_understanding(code_evidence, name_hint)
    else:
        semantic_data = FallbackMockEngine.mock_agent_understanding(code_evidence, name_hint)

    # Override defaults with yaml metadata if present
    agent_name = metadata.get("title") or metadata.get("name") or semantic_data.get("name", name_hint)
    purpose = metadata.get("description") or semantic_data.get("purpose") or semantic_data.get("domain", "General utility agent")
    
    instructions = semantic_data.get("instructions", [])
    if not instructions and "system_prompt" in semantic_data:
        instructions = [semantic_data["system_prompt"]]
    instructions_summary = "; ".join(instructions) if instructions else "Assist user requests."

    inputs = semantic_data.get("inputs", {})
    if not inputs:
        # Infer inputs from metadata or tools
        inputs = {
            "topic": "string (topic to query)",
            "count": "integer (number of items)"
        } if "news" in agent_name.lower() or "summarize" in agent_name.lower() else {
            "query": "string (user request payload)"
        }

    outputs = semantic_data.get("outputs", {})
    if not outputs:
        outputs = {
            "status": "success/error indicator",
            "result": "structured briefing or transaction log"
        }

    workflow = semantic_data.get("workflow_summary") or "Reads user requests, fetches database entries, processes mathematical transformations, and prints formatted output."
    risks = semantic_data.get("risks", ["Input boundary override risk", "Tool execution failure risk"])
    
    # 3. Extract Capabilities
    llm_caps = []
    # If the semantic data contains details about capabilities, convert them
    raw_caps = semantic_data.get("capabilities", [])
    for cap in raw_caps:
        if isinstance(cap, dict) and "capability_id" in cap:
            llm_caps.append(cap)
        elif isinstance(cap, str):
            llm_caps.append({"capability_id": cap.upper().replace(" ", "_")})
            
    capabilities = CapabilityExtractor.extract_capabilities(dedup_tools, llm_caps)

    # Construct AgentTestSpecification
    spec = AgentTestSpecification(
        agent_id=agent_id,
        name=agent_name,
        purpose=purpose,
        instructions_summary=instructions_summary,
        inputs=inputs,
        outputs=outputs,
        tools=dedup_tools,
        dependencies=dedup_deps,
        capabilities=capabilities,
        risks=risks,
        workflow_summary=workflow
    )
    
    return spec
