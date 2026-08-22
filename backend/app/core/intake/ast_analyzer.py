"""
AST Static Code Analyzer for Python and TypeScript Agent Projects.
Extracts classes, function signatures, parameters, decorators, docstrings, and imports.
"""

from __future__ import annotations

import ast
import re
import logging
from typing import Any, Dict, List
from app.models.agent import ToolDefinition, ToolRisk, DependencyDefinition

logger = logging.getLogger(__name__)


def analyze_python_source(code: str) -> Dict[str, Any]:
    """Parse Python code using AST module to extract functions, classes, and tool definitions."""
    classes: List[str] = []
    functions: List[str] = []
    tools: List[ToolDefinition] = []
    dependencies: List[DependencyDefinition] = []
    docstrings: List[str] = []

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
                doc = ast.get_docstring(node) or ""
                if doc:
                    docstrings.append(f"{node.name}: {doc}")

                fname_lower = node.name.lower()
                is_destructive = any(k in fname_lower for k in ["refund", "cancel", "delete", "remove", "payout", "drop", "write"])
                requires_auth = "refund" in fname_lower or "payout" in fname_lower or "pay" in fname_lower
                requires_conf = "cancel" in fname_lower or "delete" in fname_lower or "drop" in fname_lower

                risk = ToolRisk.LOW
                if is_destructive or requires_auth:
                    risk = ToolRisk.CRITICAL if requires_auth else ToolRisk.HIGH
                elif any(k in fname_lower for k in ["update", "modify", "send", "write"]):
                    risk = ToolRisk.MEDIUM

                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                param_schema = {p: "string" if p != "amount" else "number" for p in params}

                # Canonical capability classification
                canonical = "GENERIC_TOOL"
                if "customer" in fname_lower:
                    canonical = "CUSTOMER_LOOKUP"
                elif "order" in fname_lower and "refund" not in fname_lower and "cancel" not in fname_lower:
                    canonical = "ORDER_LOOKUP"
                elif "refund" in fname_lower or "payout" in fname_lower:
                    canonical = "REFUND_TRANSACTION"
                elif "cancel" in fname_lower:
                    canonical = "ORDER_CANCELLATION"
                elif "address" in fname_lower:
                    canonical = "ADDRESS_UPDATE"
                elif "email" in fname_lower or "send" in fname_lower:
                    canonical = "EMAIL_NOTIFICATION"
                elif "search" in fname_lower or "knowledge" in fname_lower:
                    canonical = "KNOWLEDGE_SEARCH"

                tools.append(
                    ToolDefinition(
                        name=node.name,
                        description=doc or f"Executes {node.name}({', '.join(params)})",
                        parameters_schema=param_schema,
                        risk=risk,
                        is_destructive=is_destructive,
                        requires_confirmation=requires_conf,
                        requires_authorization=requires_auth,
                        max_amount=10000.0 if requires_auth else None,
                        canonical_capability=canonical,
                        side_effect_type="WRITE" if is_destructive else "READ"
                    )
                )

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mod_name = getattr(node, "module", None)
                if not mod_name and hasattr(node, "names") and node.names:
                    mod_name = node.names[0].name
                if mod_name:
                    if any(k in mod_name for k in ["psycopg", "sqlalchemy", "sqlite", "postgres"]):
                        dependencies.append(DependencyDefinition(id="dep-db", name="PostgreSQL Database", type="database", detected_from="AST_IMPORT"))
                    elif any(k in mod_name for k in ["requests", "httpx", "urllib", "aiohttp"]):
                        dependencies.append(DependencyDefinition(id="dep-http", name="External HTTP REST API", type="http", detected_from="AST_IMPORT"))
                    elif any(k in mod_name for k in ["smtplib", "sendgrid"]):
                        dependencies.append(DependencyDefinition(id="dep-email", name="SendGrid / SMTP Email Service", type="email", detected_from="AST_IMPORT"))
                    elif any(k in mod_name for k in ["playwright", "selenium"]):
                        dependencies.append(DependencyDefinition(id="dep-browser", name="Headless Browser Controller", type="browser", detected_from="AST_IMPORT"))

    except Exception as e:
        logger.warning(f"Python AST analysis error: {e}")

    # Deduplicate dependencies
    seen = set()
    dedup_deps = []
    for d in dependencies:
        if d.name not in seen:
            seen.add(d.name)
            dedup_deps.append(d)

    return {
        "classes": classes,
        "functions": functions,
        "tools": tools,
        "dependencies": dedup_deps,
        "docstrings": docstrings
    }


def analyze_generic_source(text: str) -> Dict[str, Any]:
    """Regex fallback for TypeScript, JS, and plain text tool signatures."""
    tools: List[ToolDefinition] = []
    # Match JS/TS function or method definitions
    pattern = r"(?:async\s+)?(?:function\s+|def\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)"
    matches = re.findall(pattern, text)

    for fn_name, params_str in matches:
        if fn_name in ["if", "for", "while", "catch", "switch", "__init__"]:
            continue
        params = [p.strip().split(":")[0] for p in params_str.split(",") if p.strip()]
        is_destructive = any(k in fn_name.lower() for k in ["refund", "cancel", "delete", "payout"])
        requires_auth = "refund" in fn_name.lower() or "payout" in fn_name.lower()

        tools.append(
            ToolDefinition(
                name=fn_name,
                description=f"Auto-extracted tool signature {fn_name}({', '.join(params)})",
                parameters_schema={p: "string" for p in params},
                risk=ToolRisk.CRITICAL if requires_auth else ToolRisk.LOW,
                is_destructive=is_destructive,
                requires_authorization=requires_auth,
                max_amount=10000.0 if requires_auth else None,
                canonical_capability="CUSTOM_CAPABILITY"
            )
        )

    return {"tools": tools, "dependencies": []}
