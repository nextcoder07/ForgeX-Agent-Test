import json
import logging
import uuid
import datetime as dt
from typing import Dict, Any, List
from app.models.intake import SandboxSpecification
from app.core.llm.gemini_provider import GeminiProvider, LLMGenerationError
from app.core.llm.fallback_mock import FallbackMockEngine
from app.core.llm.key_manager import GeminiKeyManager

logger = logging.getLogger(__name__)

def _now() -> str:
    return dt.datetime.utcnow().isoformat()

async def analyze_sandbox_requirements(
    agent_id: str,
    files: Dict[str, str],
    llm: GeminiProvider
) -> SandboxSpecification:
    """
    AI-Assisted Sandbox Environment & Vulnerability Surface Analyzer.
    Analyzes code files, manifests (requirements.txt, package.json), environment variables,
    and imports to construct a real SandboxSpecification.
    """
    logger.info(f"Analyzing sandbox needs for agent: {agent_id}")
    
    # 1. Pre-scan files to extract manifest context and imports
    package_manifests = {}
    imports_list = []
    env_vars_found = []
    
    for fname, content in files.items():
        fname_lower = fname.lower()
        if fname_lower.endswith(("requirements.txt", "package.json", "pyproject.toml", "setup.py")):
            package_manifests[fname] = content[:1000] # Pass snippet of dependencies
        
        # Simple scan for imports
        if fname_lower.endswith(".py"):
            for line in content.splitlines():
                line_strip = line.strip()
                if line_strip.startswith("import ") or (line_strip.startswith("from ") and " import " in line_strip):
                    imports_list.append(line_strip)
                if "os.environ" in line_strip or "os.getenv" in line_strip:
                    env_vars_found.append(line_strip)
        elif fname_lower.endswith((".js", ".ts", ".tsx", ".jsx")):
            for line in content.splitlines():
                line_strip = line.strip()
                if "require(" in line_strip or line_strip.startswith("import "):
                    imports_list.append(line_strip)
                if "process.env" in line_strip:
                    env_vars_found.append(line_strip)

    # 2. Setup prompt for LLM
    evidence_payload = {
        "manifest_files": package_manifests,
        "detected_imports": list(set(imports_list))[:30],
        "env_var_access": list(set(env_vars_found))[:20]
    }
    
    prompt = (
        f"AGENT SOURCE EVIDENCE:\n{json.dumps(evidence_payload, indent=2)}\n\n"
        "Analyze the package dependencies, import declarations, and environment variable accesses of this AI agent.\n"
        "Construct a detailed SandboxSpecification with the following JSON schema:\n"
        "{\n"
        '  "runtime": {"runtime": "python" | "node" | "endpoint", "version": "3.12" | "20.x"},\n'
        '  "dependencies": [{"name": "package-name", "version": "version-spec", "critical": true|false}],\n'
        '  "filesystem": {"allowed_dirs": ["/sandbox/workspace", "/tmp"], "write_permission": true|false},\n'
        '  "network": {"external_domains": ["api.openai.com", "api.github.com"], "external_access_required": true|false},\n'
        '  "tools": [{"name": "tool_name", "description": "what tool does", "requires_gateway": true|false}],\n'
        '  "credentials": [{"name": "ENV_VAR_NAME", "description": "required credential", "optional": true|false}]\n'
        "}\n"
        "Return ONLY the strict JSON object."
    )

    key_mgr = GeminiKeyManager()
    if not key_mgr.keys:
        # Offline fallback spec
        logger.info("No keys configured. Returning offline mock sandbox specification.")
        return SandboxSpecification(
            id=f"sb-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            runtime={"runtime": "python", "version": "3.12"},
            dependencies=[{"name": "requests", "version": "latest", "critical": True}],
            filesystem={"allowed_dirs": ["/sandbox/workspace"], "write_permission": True},
            network={"external_domains": ["api.github.com"], "external_access_required": True},
            tools=[{"name": "sync_inventory_database", "description": "Database sync", "requires_gateway": True}],
            credentials=[{"name": "DATABASE_URL", "description": "Postgres connection string", "optional": False}],
            created_at=_now()
        )

    raw_response = await llm.generate(
        system="You are an expert sandbox container architecture engineer and vulnerability response analyst.",
        user=prompt,
        stage="SANDBOX_ANALYSIS"
    )

    try:
        data = json.loads(raw_response)
        return SandboxSpecification(
            id=f"sb-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            runtime=data.get("runtime", {"runtime": "python", "version": "3.12"}),
            dependencies=data.get("dependencies", []),
            filesystem=data.get("filesystem", {"allowed_dirs": ["/sandbox/workspace"], "write_permission": True}),
            network=data.get("network", {"external_domains": [], "external_access_required": False}),
            tools=data.get("tools", []),
            credentials=data.get("credentials", []),
            created_at=_now()
        )
    except Exception as e:
        logger.error(f"Error parsing sandbox analysis JSON: {e}")
        raise LLMGenerationError(f"Failed to generate valid sandbox specification JSON: {e}")
