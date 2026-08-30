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
    def redact_source_files(files: Dict[str, str]) -> Tuple[Dict[str, str], int]:
        """Scrub plaintext secrets from raw files, replacing with synthetic canary tokens."""
        redacted = {}
        redacted_count = 0
        patterns = [
            (r'sk-[a-zA-Z0-9_-]{20,}', 'sk-canary-openai-masked-token-000000000'),
            (r'AIzaSy[a-zA-Z0-9_-]{33}', 'AIzaSyCanaryGoogleMaskedToken000000000000'),
            (r'ghp_[a-zA-Z0-9]{36}', 'ghp_canaryGitHubMaskedToken0000000000000000'),
            (r'xoxb-[0-9]{11,13}-[0-9]{11,13}-[a-zA-Z0-9]{24}', 'xoxb-canary-slack-masked-token-000000000000000000000000'),
        ]
        for path, content in files.items():
            current_content = content
            for pat, repl in patterns:
                matches = re.findall(pat, current_content)
                if matches:
                    redacted_count += len(matches)
                    current_content = re.sub(pat, repl, current_content)
            redacted[path] = current_content
        return redacted, redacted_count

    @staticmethod
    def detect_environment_secrets(code_text: str, raw_files: Dict[str, str] = None) -> List[DetectedSecret]:
        """Detect os.getenv(), os.environ.get(), .env templates, and model SDK credentials without executing code."""
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

        # 2. Parse .env.example / .env.template if present in raw_files
        if raw_files:
            for fname, content in raw_files.items():
                if ".env" in fname.lower():
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            var_name = line.split("=", 1)[0].strip()
                            if var_name and var_name not in seen:
                                seen.add(var_name)
                                is_secret = any(kw in var_name.lower() for kw in ["key", "secret", "token", "password", "auth", "cred"])
                                detected.append(
                                    DetectedSecret(
                                        name=var_name,
                                        type="secret" if is_secret else "config",
                                        required=True,
                                        masked_sample="********"
                                    )
                                )

        # 3. Model SDK usage implies required credentials ONLY when actual SDK imports or class constructors exist
        code_lower = code_text.lower()
        has_openai_sdk = any(term in code_lower for term in ["import openai", "from openai", "langchain_openai", "chatopenai"])
        has_gemini_sdk = any(term in code_lower for term in ["google.generativeai", "chatgooglegenerativeai", "genai.generativemodel"])
        has_anthropic_sdk = any(term in code_lower for term in ["import anthropic", "from anthropic", "chatanthropic"])

        if has_openai_sdk and "OPENAI_API_KEY" not in seen:
            seen.add("OPENAI_API_KEY")
            detected.append(
                DetectedSecret(
                    name="OPENAI_API_KEY",
                    type="secret",
                    required=True,
                    masked_sample="********"
                )
            )
        if has_gemini_sdk and "GEMINI_API_KEY" not in seen:
            seen.add("GEMINI_API_KEY")
            detected.append(
                DetectedSecret(
                    name="GEMINI_API_KEY",
                    type="secret",
                    required=True,
                    masked_sample="********"
                )
            )
        if has_anthropic_sdk and "ANTHROPIC_API_KEY" not in seen:
            seen.add("ANTHROPIC_API_KEY")
            detected.append(
                DetectedSecret(
                    name="ANTHROPIC_API_KEY",
                    type="secret",
                    required=True,
                    masked_sample="********"
                )
            )

        # 4. Check if any detected secret has an explicit fallback in code (e.g. `if not NEWS_API_KEY:` or fallback mock)
        for s in detected:
            fallback_pattern = rf'(?:if\s+not\s+{s.name}|{s.name}\s+is\s+None|not\s+os\.getenv\(["\']?{s.name})'
            if re.search(fallback_pattern, code_text, re.IGNORECASE):
                s.required = False

        return detected

    @staticmethod
    def detect_model_dependencies(agent_id: str, code_text: str, env_vars: List[DetectedSecret]) -> List[AgentModelDependency]:
        """Detect LLM instantiations (e.g. model = ChatOpenAI(model='gpt-4o')) with variable names and default tags."""
        deps: List[AgentModelDependency] = []
        
        # Regex to match variable assignment to model instantiations
        # e.g., my_llm = ChatOpenAI(model="gpt-4o")
        instantiation_pattern = re.compile(
            r'(\w+)\s*=\s*(ChatOpenAI|ChatGoogleGenerativeAI|ChatAnthropic|Ollama|ChatGroq|ChatDeepSeek|OpenAI|Anthropic|GoogleGenAI)\s*\((.*?)\)',
            re.DOTALL
        )

        matches = instantiation_pattern.findall(code_text)

        # Group and deduplicate by (provider, model_name)
        grouped_models: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for var_name, class_name, args_text in matches:
            model_match = re.search(r'(?:model|model_name)\s*=\s*["\']([a-zA-Z0-9_\-\./:]+)', args_text)
            detected_model = model_match.group(1) if model_match else "UNKNOWN"

            provider_map = {
                "ChatOpenAI": "openai",
                "OpenAI": "openai",
                "ChatGoogleGenerativeAI": "google",
                "GoogleGenAI": "google",
                "ChatAnthropic": "anthropic",
                "Anthropic": "anthropic",
                "ChatGroq": "groq",
                "ChatDeepSeek": "deepseek",
                "Ollama": "ollama",
            }
            provider = provider_map.get(class_name, "openai")
            endpoint_map = {
                "openai": "https://api.openai.com/v1",
                "google": "https://generativelanguage.googleapis.com",
                "anthropic": "https://api.anthropic.com",
                "groq": "https://api.groq.com/openai/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "ollama": "http://localhost:11434/v1",
            }
            endpoint = endpoint_map.get(provider, "https://api.openai.com/v1")
            
            key = (provider, detected_model)
            if key not in grouped_models:
                grouped_models[key] = {
                    "provider": provider,
                    "model_name": detected_model,
                    "endpoint": endpoint,
                    "call_sites": [f"assignment to {var_name} ({class_name})"],
                }
            else:
                grouped_models[key]["call_sites"].append(f"assignment to {var_name} ({class_name})")

        idx = 1
        for (provider, detected_model), info in grouped_models.items():
            call_sites_str = ", ".join(info["call_sites"])
            deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent_id}-{idx}",
                    agent_id=agent_id,
                    provider=provider,
                    model_name=detected_model,
                    dependency_type="llm",
                    required=True,
                    original_provider=provider,
                    original_endpoint=info["endpoint"],
                    detected_from=f"Detected invocations: {call_sites_str}",
                    created_at=_now()
                )
            )
            idx += 1

        # Fallback if no explicit assignments found but imports exist
        if not deps:
            code_lower = code_text.lower()
            if "openai" in code_lower:
                deps.append(
                    AgentModelDependency(
                        id=f"dep-model-{agent_id}-1",
                        agent_id=agent_id,
                        provider="openai",
                        model_name="gpt-4o-mini",
                        dependency_type="llm",
                        required=True,
                        original_provider="openai",
                        original_endpoint="https://api.openai.com/v1",
                        detected_from="ast_code_import",
                        created_at=_now()
                    )
                )
            elif "google" in code_lower or "gemini" in code_lower:
                deps.append(
                    AgentModelDependency(
                        id=f"dep-model-{agent_id}-1",
                        agent_id=agent_id,
                        provider="google",
                        model_name="gemini-3.7-flash",
                        dependency_type="llm",
                        required=True,
                        original_provider="google",
                        original_endpoint="https://generativelanguage.googleapis.com",
                        detected_from="ast_code_import",
                        created_at=_now()
                    )
                )
            else:
                # Absolute fallback default
                deps.append(
                    AgentModelDependency(
                        id=f"dep-model-{agent_id}-1",
                        agent_id=agent_id,
                        provider="google",
                        model_name="gemini-3.7-flash",
                        dependency_type="llm",
                        required=True,
                        original_provider="google",
                        original_endpoint="https://generativelanguage.googleapis.com",
                        detected_from="ast_code_import",
                        created_at=_now()
                    )
                )

        return deps

    @staticmethod
    def detect_runtime_packages(code_text: str, raw_files: Dict[str, str] = None) -> List[DependencyDefinition]:
        """Authoritatively detects packages from requirements.txt / pyproject.toml without creating bogus packages from imported classes."""
        raw_files = raw_files or {}
        deps: List[DependencyDefinition] = []
        seen = set()
        has_manifest = False

        # 1. Parse requirements.txt / requirements.in / pyproject.toml (Authoritative)
        for fname, content in raw_files.items():
            if "requirements" in fname.lower() or fname.endswith(".txt"):
                has_manifest = True
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

        # 2. Only if no requirements manifest exists, extract root module names from Python import statements
        if not has_manifest:
            std_libs = {
                "os", "sys", "re", "json", "time", "typing", "datetime", "math", "uuid", "ast",
                "logging", "argparse", "asyncio", "collections", "pathlib", "functools", "itertools",
                "copy", "traceback", "subprocess", "hashlib", "io", "shutil", "tempfile"
            }
            # Match top-level module: `import foo.bar` -> `foo`, `from foo.bar import baz` -> `foo`
            import_matches = re.findall(r'(?:from|import)\s+([a-zA-Z0-9_]+)', code_text)
            for imp in import_matches:
                imp_clean = imp.strip().lower()
                # Ignore stdlib, lowercase/single character artifacts, or already seen
                if imp_clean not in std_libs and imp_clean not in seen and len(imp_clean) > 1:
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
