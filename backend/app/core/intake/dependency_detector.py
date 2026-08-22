"""
Dedicated Dependency Detector Module.
Statically analyzes agent source code, configuration files, and manifests to detect:
- Agent Category (LLM-powered, Local model, Rule-based, Tool-heavy)
- LLM Providers (OpenAI, Gemini, Anthropic, Ollama, HuggingFace, vLLM)
- External Services (Databases, REST APIs, Search, Email, Storage, Browser)
- Environment Variables & Secrets (e.g. os.getenv("OPENAI_API_KEY"))
- Runtime Requirements (Python, Node.js, Packages)

NEVER executes untrusted code during analysis.
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

        # Python patterns: os.getenv("KEY"), os.environ["KEY"], os.environ.get("KEY")
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

        # JS/TS patterns: process.env.KEY
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
        """Detect LLM and local model SDK usage and specific model names."""
        deps: List[AgentModelDependency] = []
        code_lower = code_text.lower()
        idx = 1

        # 1. OpenAI Detection
        if "openai" in code_lower or any("openai" in sec.name.lower() for sec in env_vars):
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "gpt-5"
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
        if "google.genai" in code_lower or "gemini" in code_lower or any("gemini" in sec.name.lower() for sec in env_vars):
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "gemini-2.5-flash"
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
        if "anthropic" in code_lower or "claude" in code_lower or any("anthropic" in sec.name.lower() for sec in env_vars):
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider="anthropic",
                    model_name="claude-3-5-sonnet",
                    dependency_type="llm",
                    required=True,
                    original_provider="anthropic",
                    original_endpoint="https://api.anthropic.com",
                    detected_from="ast_code_scan",
                    created_at=_now()
                )
            )
            idx += 1

        # 4. Ollama Detection (Local Model — NO API KEY ASSUMED!)
        if "ollama" in code_lower:
            model_match = re.search(r'model\s*=\s*["\']([a-zA-Z0-9_\-\.]+)', code_text)
            detected_model = model_match.group(1) if model_match else "llama3"
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

        # 5. HuggingFace / vLLM Detection (Local Model)
        if "vllm" in code_lower or "huggingface" in code_lower or "transformers" in code_lower:
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider="huggingface",
                    model_name="local-huggingface-model",
                    dependency_type="local_model",
                    required=False,
                    original_provider="huggingface",
                    original_endpoint="http://localhost:8000",
                    detected_from="ast_code_scan",
                    created_at=_now()
                )
            )
            idx += 1

        return deps

    @staticmethod
    def detect_runtime_packages(code_text: str, raw_files: Dict[str, str]) -> List[DependencyDefinition]:
        """Statically detects runtime packages (langgraph, python-dotenv, argparse, etc.) that do NOT require credentials."""
        deps: List[DependencyDefinition] = []
        seen = set()

        code_lower = code_text.lower()

        # Check requirements.txt or raw files
        req_text = raw_files.get("requirements.txt", "") + "\n" + raw_files.get("requirements.in", "")

        package_rules = [
            ("langgraph", "LangGraph Framework", "framework"),
            ("langchain", "LangChain Core", "framework"),
            ("tavily", "Tavily Search Client", "package"),
            ("dotenv", "Python DotEnv", "package"),
            ("argparse", "CLI Parameter Parser", "package"),
            ("requests", "Requests HTTP Library", "package"),
            ("httpx", "HTTPX REST Client", "package"),
            ("pydantic", "Pydantic Data Validation", "package"),
        ]

        for pkg_kw, pkg_name, pkg_type in package_rules:
            if pkg_kw in code_lower or pkg_kw in req_text.lower():
                if pkg_name not in seen:
                    seen.add(pkg_name)
                    deps.append(
                        DependencyDefinition(
                            id=f"dep-{pkg_kw}",
                            name=pkg_name,
                            type=pkg_type,
                            detected_from="REQUIREMENTS_AND_IMPORT_SCAN"
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
        has_local_model = any(m.dependency_type == "local_model" for m in model_deps) or "ollama" in code_lower or "vllm" in code_lower
        if has_local_model:
            return AgentCategory.LOCAL_MODEL

        # Check for external LLM API dependency
        has_llm_api = len(model_deps) > 0 or any(kw in code_lower for kw in ["openai", "gemini", "anthropic", "chat.completions", "responses.create"])

        # Check for tool count & external services
        has_heavy_tools = len(tools) >= 3 or len([d for d in ext_deps if d.type in ["external_service", "database", "http", "email"]]) >= 2 or any(kw in code_lower for kw in ["database", "sendgrid", "playwright", "stripe", "postgres", "redis", "elasticsearch"])

        if not has_llm_api:
            # Type 3: Rule-based agent (e.g. pure if/else, dictionary lookups)
            return AgentCategory.RULE_BASED

        if has_heavy_tools:
            # Type 4: Tool-heavy agent
            return AgentCategory.TOOL_HEAVY

        # Default Type 1: LLM-powered agent
        return AgentCategory.LLM_POWERED
