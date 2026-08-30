"""
Execution Manifest Builder.
Constructs canonical, immutable ExecutionManifest objects from AgentRecord,
Scenario, and active dependency/credential bindings before sandbox provisioning.
"""

from __future__ import annotations

import re
import uuid
import hashlib
from typing import Dict, Any, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution_manifest import (
    ExecutionManifest,
    AgentExecutionSpec,
    InterfaceExecutionSpec,
    DependencyExecutionSpec,
    ModelExecutionSpec,
    CredentialExecutionSpec,
    ScenarioExecutionSpec,
)

PACKAGE_TO_IMPORT_MAP = {
    "python-dotenv": "dotenv",
    "python_dotenv": "dotenv",
    "langchain-openai": "langchain_openai",
    "langchain-community": "langchain_community",
    "langchain-core": "langchain_core",
    "langchain-tavily": "langchain_tavily",
    "tavily-python": "tavily",
    "pyyaml": "yaml",
    "pillow": "PIL",
    "scikit-learn": "sklearn",
    "beautifulsoup4": "bs4",
    "psycopg2-binary": "psycopg2",
    "opencv-python": "cv2",
}


def build_execution_manifest(
    agent: AgentRecord,
    scenario: Scenario,
    provided_secrets: Optional[Dict[str, str]] = None
) -> ExecutionManifest:
    """Builds a complete, deterministic ExecutionManifest snapshot prior to execution."""
    provided_secrets = provided_secrets or {}
    raw_manifest = agent.runtime_manifest or {}
    entrypoint = raw_manifest.get("entrypoint", "agent.py")

    # Artifact hash calculation
    combined_code = ""
    if agent.source_files:
        for fname in sorted(agent.source_files.keys()):
            combined_code += agent.source_files[fname]
    art_hash = hashlib.sha256((agent.id + combined_code).encode("utf-8")).hexdigest()[:16]

    agent_spec = AgentExecutionSpec(
        agent_id=agent.id,
        agent_version_id=getattr(agent, "version_label", None) or scenario.agent_version_id or "v1.0",
        artifact_hash=art_hash,
        entrypoint=entrypoint,
        working_directory="/workspace",
        language="python",
        runtime_version="3.12"
    )

    # Interface Spec
    iface_type = (scenario.interface_type or "CHAT").upper()
    invoc = scenario.invocation or {}
    iface_spec = InterfaceExecutionSpec(
        interface_type=iface_type,
        command=invoc.get("command"),
        args=invoc.get("args", []),
        endpoint=invoc.get("endpoint") or getattr(agent, "endpoint", None),
        user_messages=scenario.user_messages or ([scenario.user_input] if scenario.user_input else ["Hello"]),
        input_artifacts=[art if isinstance(art, dict) else {"path": str(art)} for art in scenario.input_artifacts]
    )

    # Dependencies Spec
    deps_spec: List[DependencyExecutionSpec] = []
    for dep in agent.dependencies:
        dep_type_str = str(dep.type).lower() if hasattr(dep.type, "value") else str(dep.type).lower()
        if dep_type_str in ("package", "framework", "library"):
            raw_name = dep.name.strip()
            clean_pkg = re.split(r'[=><~!]', raw_name)[0].strip()
            clean_key = clean_pkg.replace("-", "_").lower()
            import_name = PACKAGE_TO_IMPORT_MAP.get(clean_pkg.lower(), clean_pkg.replace("-", "_"))
            deps_spec.append(DependencyExecutionSpec(
                package_name=clean_pkg,
                import_name=import_name,
                requested_version=raw_name if "==" in raw_name else None,
                required=dep.required,
                resolution_state="BOUND"
            ))

    # Credentials Spec
    creds_spec: List[CredentialExecutionSpec] = []
    for dep in agent.dependencies:
        dep_type_str = str(dep.type).lower() if hasattr(dep.type, "value") else str(dep.type).lower()
        if dep_type_str == "credential" or dep.name.endswith("_KEY") or dep.name.endswith("_TOKEN"):
            k_name = dep.name.strip()
            has_val = bool(provided_secrets.get(k_name) or provided_secrets.get("TEST_AGENT_" + k_name))
            status = "AVAILABLE" if has_val else ("USER_REQUIRED" if dep.required else "OPTIONAL")
            creds_spec.append(CredentialExecutionSpec(
                key_name=k_name,
                provider=getattr(dep, "provider", "UNKNOWN") or "UNKNOWN",
                required=dep.required,
                status=status,
                masked_value="***BOUND***" if has_val else "***MISSING***"
            ))

    # Models Spec
    models_spec: List[ModelExecutionSpec] = []
    raw_models = raw_manifest.get("detected_model_dependencies", [])
    if raw_models:
        for m in raw_models:
            p_name = m.get("provider", "openai") if isinstance(m, dict) else getattr(m, "provider", "openai")
            m_name = m.get("model_name", "gpt-4o-mini") if isinstance(m, dict) else getattr(m, "model_name", "gpt-4o-mini")
            b_url = m.get("base_url") if isinstance(m, dict) else getattr(m, "base_url", None)
            models_spec.append(ModelExecutionSpec(
                provider=p_name,
                model_name=m_name,
                base_url=b_url,
                credential_key=f"{p_name.upper()}_API_KEY",
                is_local="localhost" in str(b_url) or "127.0.0.1" in str(b_url) or p_name.lower() == "ollama"
            ))

    # Scenario Spec
    scenario_spec = ScenarioExecutionSpec(
        scenario_id=scenario.id,
        title=scenario.title,
        category=getattr(scenario.category, "value", str(scenario.category)),
        target_tool=getattr(scenario, "target_tool", None),
        target_function=getattr(scenario, "target_function", None),
        target_workflow_node=getattr(scenario, "target_workflow_node", None),
        target_service=getattr(scenario, "target_service", None),
        fault_injections=[f.dict() if hasattr(f, "dict") else f for f in scenario.fault_injections],
        assertions=[a.dict() if hasattr(a, "dict") else a for a in scenario.assertions]
    )

    manifest_id = f"mfst-{uuid.uuid4().hex[:10]}"
    return ExecutionManifest(
        id=manifest_id,
        agent=agent_spec,
        interface=iface_spec,
        dependencies=deps_spec,
        models=models_spec,
        credentials=creds_spec,
        scenario=scenario_spec
    )
