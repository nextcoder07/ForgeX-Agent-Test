"""
Pure Structural AST Code Analyzer for Agent Source Files.
Extracts structural code facts (functions, classes, parameters, decorators, docstrings, imports, calls, constants)
without making semantic capability or domain-specific risk decisions.
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Dict, List, Optional
from app.models.agent import ToolDefinition, ToolRisk, DependencyDefinition

logger = logging.getLogger(__name__)


def analyze_python_source(code: str, filename: str = "agent.py") -> Dict[str, Any]:
    """Parse Python code using AST module to extract pure structural code facts."""
    classes: List[Dict[str, Any]] = []
    functions: List[Dict[str, Any]] = []
    tools: List[ToolDefinition] = []
    dependencies: List[DependencyDefinition] = []
    docstrings: List[str] = []
    imports: List[Dict[str, Any]] = []
    constants: List[Dict[str, Any]] = []

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # 1. Class Definitions & State Models (TypedDict / BaseModel)
            if isinstance(node, ast.ClassDef):
                base_names = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_names.append(base.attr)

                fields = []
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        fields.append(item.target.id)

                classes.append({
                    "name": node.name,
                    "base_classes": base_names,
                    "fields": fields,
                    "line": getattr(node, "lineno", 1)
                })

                # Extract public methods on Agent / Tool classes as ToolDefinitions
                is_agent_or_tool_class = any(kw in node.name.lower() for kw in ["agent", "tool", "service", "executor"])
                if is_agent_or_tool_class:
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_") and item.name not in ["run", "execute", "main"]:
                            doc = ast.get_docstring(item) or ""
                            params = [arg.arg for arg in item.args.args if arg.arg != "self"]
                            param_schema = {p: "string" for p in params}
                            tools.append(
                                ToolDefinition(
                                    name=item.name,
                                    description=doc or f"Executes {item.name}({', '.join(params)})",
                                    parameters_schema=param_schema,
                                    risk=ToolRisk.HIGH if any(kw in item.name.lower() for kw in ["refund", "cancel", "delete", "execute", "drop"]) else ToolRisk.LOW,
                                    is_destructive=any(kw in item.name.lower() for kw in ["delete", "cancel", "drop", "destroy"]),
                                    requires_confirmation=any(kw in item.name.lower() for kw in ["cancel", "delete", "refund"]),
                                    requires_authorization=any(kw in item.name.lower() for kw in ["refund", "payment", "transfer"]),
                                    canonical_capability=None,
                                    side_effect_type="WRITE" if any(kw in item.name.lower() for kw in ["refund", "cancel", "update", "send", "write", "post"]) else "READ"
                                )
                            )

            # 2. Function Definitions
            elif isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node) or ""
                if doc:
                    docstrings.append(f"{node.name}: {doc}")

                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                param_schema = {p: "string" for p in params}

                decorators = []
                is_explicit_tool = False
                for dec in node.decorator_list:
                    dec_name = dec.id if isinstance(dec, ast.Name) else (dec.func.id if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) else "")
                    if dec_name:
                        decorators.append(dec_name)
                    if dec_name in ["tool", "agent_tool", "command"]:
                        is_explicit_tool = True

                # Extract calls made inside this function
                calls_made = []
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        if isinstance(sub.func, ast.Name):
                            calls_made.append(sub.func.id)
                        elif isinstance(sub.func, ast.Attribute):
                            calls_made.append(sub.func.attr)

                fn_info = {
                    "name": node.name,
                    "parameters": params,
                    "decorators": decorators,
                    "docstring": doc,
                    "line": getattr(node, "lineno", 1),
                    "is_explicit_tool": is_explicit_tool,
                    "calls_made": calls_made
                }
                functions.append(fn_info)

                # Explicitly decorated functions or top-level tool functions (non-main/non-helper) are tools
                if is_explicit_tool or (not node.name.startswith("_") and node.name not in ["main", "run", "cli", "parse_args", "get_agent"] and any(kw in node.name.lower() for kw in ["calculate", "convert", "format", "search", "lookup", "fetch", "get_", "create_", "update_", "delete_"])):
                    tools.append(
                        ToolDefinition(
                            name=node.name,
                            description=doc or f"Executes {node.name}({', '.join(params)})",
                            parameters_schema=param_schema,
                            risk=ToolRisk.LOW,
                            is_destructive=False,
                            requires_confirmation=False,
                            requires_authorization=False,
                            canonical_capability=None,
                            side_effect_type="READ"
                        )
                    )

            # 3. Imports
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mod_name = getattr(node, "module", None)
                names = [n.name for n in getattr(node, "names", [])]
                imports.append({
                    "module": mod_name or (names[0] if names else ""),
                    "names": names,
                    "line": getattr(node, "lineno", 1)
                })

            # 4. Constants
            elif isinstance(node, ast.Constant):
                constants.append({
                    "value": node.value,
                    "type": type(node.value).__name__,
                    "line": getattr(node, "lineno", 1)
                })

    except Exception as e:
        logger.warning(f"Python AST analysis error in {filename}: {e}")

    return {
        "classes": classes,
        "functions": functions,
        "tools": tools,
        "dependencies": dependencies,
        "docstrings": docstrings,
        "imports": imports,
        "constants": constants
    }


def analyze_generic_source(text: str, filename: str = "agent.ts") -> Dict[str, Any]:
    """Structural regex fallback for non-Python files with low confidence flag."""
    tools: List[ToolDefinition] = []
    functions: List[Dict[str, Any]] = []

    # Match functions with low confidence flag
    pattern = r"(?:async\s+)?(?:function\s+|def\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)"
    matches = re.findall(pattern, text)

    for fn_name, params_str in matches:
        if fn_name in ["if", "for", "while", "catch", "switch", "__init__"]:
            continue
        params = [p.strip().split(":")[0] for p in params_str.split(",") if p.strip()]
        functions.append({
            "name": fn_name,
            "parameters": params,
            "decorators": [],
            "docstring": "",
            "is_explicit_tool": False,
            "calls_made": []
        })

    return {
        "classes": [],
        "functions": functions,
        "tools": tools, # Do not invent external tools without explicit tool decorator
        "dependencies": [],
        "docstrings": [],
        "imports": [],
        "constants": []
    }
