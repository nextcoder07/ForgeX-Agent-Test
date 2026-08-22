"""
Dedicated Dependency Detector Module.
Statically analyzes agent source code, configuration files, and manifests to detect:
- Agent Category (LLM-powered, Local model, Rule-based, Tool-heavy)
- Model Dependencies without invented model names
- Runtime Requirements & Packages dynamically from requirements.txt and imports
"""

from __future__ import annotations

import re
import datetime as dt
from typing import Any, Dict, List, Tuple
from app.models.agent import ToolDefinition, DependencyDefinition
from app.models.dependency_model import (
    AgentCategory,
    AgentModelDependency,
    DetectedSecret,
)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


def redact_secret_string(value: str) -> str:
    """Mask secret strings for safe display in logs and UI."""
    if not value:
        return "********"
    if len(value) <= 8:
        return "********"
    return f"{value[:3]}...{value[-3:]}"


class DependencyDetector:
    @staticmethod
    def detect_environment_secrets(code_text: str) -> List[DetectedSecret]:
        """Detect os.getenv(), os.environ.get(), process.env references without executing code."""
        detected: List[DetectedSecret] = []
        seen = set()

        py_patterns = [
            r'os\.(?:getenv|environ\.get)\s*\(\s*["\']([A-Z0-9_]+)["\']',
            r'os\.environ\s*\[\s*["\']([A-Z0-9_]+)["\']\s*\]',
            r'getenv\s*\(\s*["\']([A-Z0-9_]+)["\']',
        ]
        for pat in py_patterns:
            for match in re.findall(pat, code_text):
                if match not in seen:
                    seen.add(match)
                    is_secret = any(kw in match.lower() for kw in ["key", "secret", "token", "password", "auth", "cred"])
                    detected.append(
                        DetectedSecret(
                            name=match,
                            type="secret" if is_secret else "config",
                            required=True,
                            masked_sample="********"
                        )
                    )

        js_patterns = [
            r'process\.env\.([A-Z0-9_]+)',
            r'process\.env\[["\']([A-Z0-9_]+)["\']\]',
        ]
        for pat in js_patterns:
            for match in re.findall(pat, code_text):
                if match not in seen:
                    seen.add(match)
                    is_secret = any(kw in match.lower() for kw in ["key", "secret", "token", "password", "auth"])
                    detected.append(
                        DetectedSecret(
                            name=match,
                            type="secret" if is_secret else "config",
                            required=True,
                            masked_sample="********"
                        )
                    )

        return detected

    @staticmethod
    def detect_model_dependencies(agent_id: str, code_text: str, env_vars: List[DetectedSecret]) -> List[AgentModelDependency]:
        """Detect LLM and local model SDK usage and specific model names without inventing fake defaults."""
        deps: List[AgentModelDependency] = []
        code_lower = code_text.lower()
        idx = 1

        # 1. OpenAI Detection
        if "openai" in code_lower:
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "UNKNOWN"
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider="openai",
                    model_name=detected_model,
                    dependency_type="llm",
                    required=True,
                    original_provider="openai",
                    original_endpoint="https://api.openai.com/v1",
                    detected_from="ast_code_scan",
                    created_at=_now()
                )
            )
            idx += 1

        # 2. Google Gemini Detection
        if "google.genai" in code_lower or "google.generativeai" in code_lower:
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "UNKNOWN"
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider="google",
                    model_name=detected_model,
                    dependency_type="llm",
                    required=True,
                    original_provider="google",
                    original_endpoint="https://generativelanguage.googleapis.com",
                    detected_from="ast_code_scan",
                    created_at=_now()
                )
            )
            idx += 1

        # 3. Anthropic Detection
        if "anthropic" in code_lower:
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "UNKNOWN"
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider="anthropic",
                    model_name=detected_model,
                    dependency_type="llm",
                    required=True,
                    original_provider="anthropic",
                    original_endpoint="https://api.anthropic.com",
                    detected_from="ast_code_scan",
                    created_at=_now()
                )
            )
            idx += 1

        # 4. Ollama Detection (Local Model)
        if "ollama" in code_lower:
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "UNKNOWN"
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider="ollama",
                    model_name=detected_model,
                    dependency_type="local_model",
                    required=False,
                    original_provider="ollama",
                    original_endpoint="http://localhost:11434",
                    detected_from="ast_code_scan",
                    created_at=_now()
                )
            )
            idx += 1

        return deps

    @staticmethod
    def detect_runtime_packages(code_text: str, raw_files: Dict[str, str]) -> List[DependencyDefinition]:
        """Dynamically detects packages from requirements.txt, pyproject.toml, and imports without hardcoding."""
        deps: List[DependencyDefinition] = []
        seen = set()

        # 1. Parse requirements.txt / requirements.in
        for fname, content in raw_files.items():
            if "requirements" in fname.lower() or fname.endswith(".txt"):
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        pkg_raw = re.split(r'[=><~]', line)[0].strip()
                        if pkg_raw and pkg_raw.lower() not in seen:
                            seen.add(pkg_raw.lower())
                            is_fw = any(fw in pkg_raw.lower() for fw in ["langgraph", "crewai", "autogen", "langchain", "llamaindex", "fastapi"])
                            deps.append(
                                DependencyDefinition(
                                    id=f"dep-pkg-{pkg_raw.lower()}",
                                    name=line,
                                    type="framework" if is_fw else "package",
                                    detected_from=fname
                                )
                            )

        # 2. Parse top-level Python import statements from code
        import_matches = re.findall(r'(?:from|import)\s+([a-zA-Z0-9_]+)', code_text)
        std_libs = {"os", "sys", "re", "json", "time", "typing", "datetime", "math", "uuid", "ast", "logging", "argparse", "asyncio", "collections", "pathlib"}
        for imp in import_matches:
            imp_clean = imp.strip().lower()
            if imp_clean not in std_libs and imp_clean not in seen:
                seen.add(imp_clean)
                deps.append(
                    DependencyDefinition(
                        id=f"dep-import-{imp_clean}",
                        name=imp_clean,
                        type="package",
                        detected_from="IMPORT_STATEMENT"
                    )
                )

        return deps

    @staticmethod
    def classify_agent_category(
        code_text: str,
        model_deps: List[AgentModelDependency],
        tools: List[ToolDefinition],
        ext_deps: List[DependencyDefinition]
    ) -> AgentCategory:
        """Classify agent into Type 1 (LLM-powered), Type 2 (Local model), Type 3 (Rule-based), or Type 4 (Tool-heavy)."""
        code_lower = code_text.lower()

        # Check for local models first
        has_local_model = any(m.dependency_type == "local_model" for m in model_deps) or "ollama" in code_lower
        if has_local_model:
            return AgentCategory.LOCAL_MODEL

        # Check for external LLM API dependency
        has_llm_api = len(model_deps) > 0 or any(kw in code_lower for kw in ["openai", "gemini", "anthropic", "chat.completions"])

        # Check for tool count & external services
        has_heavy_tools = len(tools) >= 3 or len([d for d in ext_deps if d.type in ["external_service", "database", "http", "email"]]) >= 2

        if not has_llm_api:
            # Type 3: Rule-based agent
            return AgentCategory.RULE_BASED

        if has_heavy_tools:
            # Type 4: Tool-heavy agent
            return AgentCategory.TOOL_HEAVY

        # Default Type 1: LLM-powered agent
        return AgentCategory.LLM_POWERED
