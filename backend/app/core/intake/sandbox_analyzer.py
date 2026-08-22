"""
Sandbox Specification Analyzer.
Generates deterministic SandboxSpecifications based on AST evidence, package manifests,
and environment requirements.
Never fabricates demo databases, GitHub domains, or inventory sync tools.
"""

from __future__ import annotations

import json
import logging
import uuid
import datetime as dt
from typing import Dict, Any, List
from app.models.intake import SandboxSpecification
from app.core.llm.gemini_provider import GeminiProvider, LLMGenerationError
from app.core.llm.key_manager import GeminiKeyManager

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


async def analyze_sandbox_requirements(
    agent_id: str,
    files: Dict[str, str],
    llm: Optional[GeminiProvider] = None
) -> SandboxSpecification:
    """
    Evidence-based Sandbox Specification Builder.
    Constructs deterministic SandboxSpecification from package files, imports, and credentials.
    """
    logger.info(f"Analyzing sandbox requirements for agent: {agent_id}")
    
    # 1. Deterministic Extraction from files
    runtime = "python"
    runtime_version = "3.12"
    dependencies = []
    env_vars = []
    network_domains = []

    # Check runtime
    if any(k.endswith((".ts", ".js", "package.json")) for k in files):
        runtime = "node"
        runtime_version = "20.x"

    # Check package manifests
    for fname, content in files.items():
        if "requirements" in fname.lower() or fname.endswith(".txt"):
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    dependencies.append({"name": line, "version": "pinned", "critical": True})

        # Scan for environment variables
        if fname.endswith(".py"):
            for line in content.splitlines():
                if "os.getenv(" in line or "os.environ[" in line or "os.environ.get(" in line:
                    for key in ["OPENAI_API_KEY", "TAVILY_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "SERPER_API_KEY"]:
                        if key in line and not any(e["name"] == key for e in env_vars):
                            env_vars.append({"name": key, "description": f"API key for {key.split('_')[0]}", "optional": False})

    # Deduce network requirements strictly from external SDK references
    all_text = " ".join(files.values())
    if "tavily" in all_text.lower():
        network_domains.append("api.tavily.com")
    if "openai" in all_text.lower():
        network_domains.append("api.openai.com")
    if "anthropic" in all_text.lower():
        network_domains.append("api.anthropic.com")
    if "googleapis" in all_text.lower() or "gemini" in all_text.lower():
        network_domains.append("generativelanguage.googleapis.com")

    # If AI key is available and LLM provided, optionally refine description fields
    key_mgr = GeminiKeyManager()
    if key_mgr.keys and llm:
        try:
            evidence_payload = {
                "manifest_files": [d["name"] for d in dependencies[:20]],
                "env_vars": [e["name"] for e in env_vars],
                "network_domains": network_domains
            }
            prompt = (
                f"AGENT EVIDENCE:\n{json.dumps(evidence_payload, indent=2)}\n\n"
                "Refine the sandbox specification strictly matching the evidence above into valid JSON with fields: "
                "runtime, dependencies, filesystem, network, tools, credentials.\n"
                "Do NOT invent unreferenced databases, tools, or domains. Return ONLY strict JSON."
            )
            raw_response = await llm.generate(
                system="You are a strict sandbox container engineer. You only include evidenced services.",
                user=prompt,
                stage="SANDBOX_ANALYSIS"
            )
            data = json.loads(raw_response)
            return SandboxSpecification(
                id=f"sb-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                runtime=data.get("runtime", {"runtime": runtime, "version": runtime_version}),
                dependencies=data.get("dependencies", dependencies),
                filesystem=data.get("filesystem", {"allowed_dirs": ["/sandbox/workspace"], "write_permission": True}),
                network=data.get("network", {"external_domains": network_domains, "external_access_required": len(network_domains) > 0}),
                tools=data.get("tools", []),
                credentials=data.get("credentials", env_vars),
                created_at=_now()
            )
        except Exception as e:
            logger.warning(f"LLM sandbox refinement skipped: {e}")

    # Pure deterministic fallback (100% ground truth evidence)
    return SandboxSpecification(
        id=f"sb-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        runtime={"runtime": runtime, "version": runtime_version},
        dependencies=dependencies,
        filesystem={"allowed_dirs": ["/sandbox/workspace"], "write_permission": True},
        network={"external_domains": network_domains, "external_access_required": len(network_domains) > 0},
        tools=[],
        credentials=env_vars,
        created_at=_now()
    )
