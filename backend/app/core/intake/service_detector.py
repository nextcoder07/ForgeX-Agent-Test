"""
Service & Capability Detector Module.
Generic SDK/client and credential detector that maps external integrations to capabilities
(e.g., TavilySearch -> WEB_SEARCH, ChatOpenAI -> LLM_INFERENCE) and extracts credential references
without hardcoding agent-specific function rules.
"""

from __future__ import annotations

import ast
import re
from typing import Dict, List, Any
from app.models.dependency_model import DetectedSecret


class ServiceDetector:
    # Generic mapping patterns: SDK / Class Name -> Capability
    CAPABILITY_PATTERNS = {
        r"Tavily|Serper|DuckDuckGo|BraveSearch|GoogleSearch": "WEB_SEARCH",
        r"ChatOpenAI|ChatGoogleGenerativeAI|Anthropic|ChatAnthropic|LLM|OpenAI": "LLM_INFERENCE",
        r"Stripe|PayPal|Razorpay": "PAYMENT",
        r"SMTP|SendGrid|Mailgun|Email": "EMAIL",
        r"Postgres|MySQL|MongoDB|Supabase|SQLite|Redis|SQLAlchemy": "DATABASE",
        r"S3|GoogleDrive|Dropbox|FileSystem": "FILESYSTEM",
    }

    # Credential Patterns
    CREDENTIAL_PATTERNS = [
        r"([A-Z0-9_]+_API_KEY)",
        r"([A-Z0-9_]+_TOKEN)",
        r"([A-Z0-9_]+_SECRET)",
        r"([A-Z0-9_]+_PASSWORD)",
        r"DATABASE_URL",
        r"SUPABASE_URL"
    ]

    @staticmethod
    def detect_services_and_capabilities(ast_trees: Dict[str, ast.AST], raw_files: Dict[str, str]) -> Dict[str, Any]:
        """Detects external service calls, capabilities, and required credential references."""
        external_calls: List[Dict[str, Any]] = []
        capabilities: List[str] = []
        credential_refs: List[DetectedSecret] = []
        discovered_secrets_set = set()

        # 1. Parse raw env files (.env, .env.example) for credentials
        for fname, content in raw_files.items():
            if ".env" in fname.lower():
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key_name = line.split("=")[0].strip()
                        if key_name and key_name not in discovered_secrets_set:
                            discovered_secrets_set.add(key_name)
                            credential_refs.append(
                                DetectedSecret(
                                    name=key_name,
                                    type="credential",
                                    required=True,
                                    masked_sample="KEY_*****"
                                )
                            )

        # 2. Parse AST trees for SDK class instantiations, imports, and os.getenv calls
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # Detect Class Instantiation (e.g., TavilySearch(), ChatOpenAI())
                if isinstance(node, ast.Call):
                    class_name = ServiceDetector._get_callable_name(node.func)
                    if class_name:
                        for pattern, cap in ServiceDetector.CAPABILITY_PATTERNS.items():
                            if re.search(pattern, class_name, re.IGNORECASE):
                                if cap not in capabilities:
                                    capabilities.append(cap)
                                external_calls.append({
                                    "class_name": class_name,
                                    "capability": cap,
                                    "file": fname,
                                    "line": getattr(node, "lineno", 1)
                                })

                # Detect Imports (e.g. from langchain_tavily import TavilySearch)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        full_name = f"{mod}.{alias.name}"
                        for pattern, cap in ServiceDetector.CAPABILITY_PATTERNS.items():
                            if re.search(pattern, full_name, re.IGNORECASE) or re.search(pattern, alias.name, re.IGNORECASE):
                                if cap not in capabilities:
                                    capabilities.append(cap)

                # Detect os.getenv / os.environ credential references
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ["getenv", "get"] and len(node.args) >= 1:
                        if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                            sec_name = node.args[0].value
                            if any(re.search(pat, sec_name) for pat in ServiceDetector.CREDENTIAL_PATTERNS):
                                if sec_name not in discovered_secrets_set:
                                    discovered_secrets_set.add(sec_name)
                                    credential_refs.append(
                                        DetectedSecret(
                                            name=sec_name,
                                            type="credential",
                                            required=True,
                                            masked_sample="KEY_*****"
                                        )
                                    )

        # Fallback default capabilities if none discovered
        if not capabilities:
            capabilities.append("LLM_INFERENCE")

        return {
            "external_calls": external_calls,
            "capabilities": capabilities,
            "credential_references": credential_refs
        }

    @staticmethod
    def _get_callable_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
