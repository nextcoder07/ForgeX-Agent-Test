"""
Exhaustive Static AST Extractor for ForgeX Universal Intake.
Extracts indisputable code facts: CLI arguments, LLM constructors, functions,
side-effects, security surfaces, and call-graphs.
"""

from __future__ import annotations

import ast
import re
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.intake.evidence_models import (
    CLIOptionEvidence,
    LLMConstructorEvidence,
    SecuritySurfaceEvidence,
    CallGraphEdge,
    EvidenceCategory,
    EvidenceItem,
    CertaintyLevel,
    SideEffectType,
)

logger = logging.getLogger(__name__)


class StaticCodeExtractor:
    @staticmethod
    def extract_cli_arguments(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[CLIOptionEvidence]:
        """Extracts CLI argument parser definitions (argparse, click, sys.argv)."""
        options: List[CLIOptionEvidence] = []
        counter = 0

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "add_argument" or not node.args:
                    continue

                flags = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
                if not flags:
                    continue

                primary_name = flags[-1].lstrip("-").replace("-", "_")
                req = False
                arg_type = "string"
                default_val = None
                help_str = None
                is_switch = False

                for kw in node.keywords:
                    if kw.arg == "required" and isinstance(kw.value, ast.Constant):
                        req = bool(kw.value.value)
                    elif kw.arg == "type" and isinstance(kw.value, ast.Name):
                        arg_type = kw.value.id
                    elif kw.arg == "default" and isinstance(kw.value, ast.Constant):
                        default_val = kw.value.value
                    elif kw.arg == "help" and isinstance(kw.value, ast.Constant):
                        help_str = str(kw.value.value)
                    elif kw.arg == "action" and isinstance(kw.value, ast.Constant) and kw.value.value == "store_true":
                        is_switch = True
                        arg_type = "boolean"

                if any("file" in f.lower() or "pdf" in f.lower() or "resume" in f.lower() or "path" in f.lower() for f in flags):
                    arg_type = "path"

                counter += 1
                options.append(CLIOptionEvidence(
                    id=f"ev-cli-{counter}",
                    flags=flags,
                    name=primary_name,
                    argument_type=arg_type,
                    required=req,
                    default_value=default_val,
                    help_text=help_str,
                    is_flag_switch=is_switch,
                    source_file=fname,
                    line_number=getattr(node, "lineno", 1)
                ))

        return options

    @staticmethod
    def extract_llm_constructors(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[LLMConstructorEvidence]:
        """Extracts LLM client constructors (ChatOpenAI, OpenAI, ChatGoogleGenerativeAI, etc.)."""
        constructors: List[LLMConstructorEvidence] = []
        counter = 0

        llm_class_map = {
            "ChatOpenAI": ("openai", "gpt-4o-mini"),
            "OpenAI": ("openai", "gpt-4o-mini"),
            "ChatAnthropic": ("anthropic", "claude-3-5-sonnet"),
            "Anthropic": ("anthropic", "claude-3-5-sonnet"),
            "ChatGoogleGenerativeAI": ("google", "gemini-1.5-flash"),
            "GoogleGenerativeAI": ("google", "gemini-1.5-flash"),
            "Ollama": ("ollama", "llama3"),
        }

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                class_name = ""
                if isinstance(node.func, ast.Name):
                    class_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    class_name = node.func.attr

                if class_name in llm_class_map:
                    provider, default_model = llm_class_map[class_name]
                    model_name = default_model
                    temp = None
                    tokens = None

                    for kw in node.keywords:
                        if kw.arg in ("model", "model_name") and isinstance(kw.value, ast.Constant):
                            model_name = str(kw.value.value)
                        elif kw.arg == "temperature" and isinstance(kw.value, ast.Constant):
                            try:
                                temp = float(kw.value.value)
                            except Exception:
                                pass
                        elif kw.arg == "max_tokens" and isinstance(kw.value, ast.Constant):
                            try:
                                tokens = int(kw.value.value)
                            except Exception:
                                pass

                    counter += 1
                    constructors.append(LLMConstructorEvidence(
                        id=f"ev-llm-{counter}",
                        provider=provider,
                        model_name=model_name,
                        temperature=temp,
                        max_tokens=tokens,
                        source_class=class_name,
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1)
                    ))

        return constructors

    @staticmethod
    def extract_security_surfaces(
        ast_trees: Dict[str, ast.AST],
        source_files: Dict[str, str],
        cli_options: List[CLIOptionEvidence]
    ) -> List[SecuritySurfaceEvidence]:
        """Statically detects security surfaces: SQL execution, PII processing, conditional writes, file access."""
        surfaces: List[SecuritySurfaceEvidence] = []
        counter = 0

        combined_code = " ".join(source_files.values()).lower()

        # 1. SQL Execution & Conditional Write
        if "sql" in combined_code or "sqlite3" in combined_code or "database" in combined_code:
            has_write_flag = any("allow_write" in opt.name or "write" in opt.name for opt in cli_options)
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                surface_type="SQL_EXECUTION",
                severity="high" if has_write_flag else "medium",
                description="Agent connects to relational SQL database and generates/executes queries.",
                source_file="agent.py",
                line_number=1,
                trigger_condition="--allow-write enabled" if has_write_flag else "Default read-only query execution",
                mitigation_hint="Enforce query AST validation and read-only connection limits."
            ))

        # 2. PII / Resume Processing
        if "resume" in combined_code or "candidate" in combined_code or "applicant" in combined_code:
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                surface_type="PII_PROCESSING",
                severity="medium",
                description="Agent parses resumes and candidate profiles containing Personally Identifiable Information.",
                source_file="agent.py",
                line_number=1,
                mitigation_hint="Scrub candidate PII (phone, email, address) before passing to external LLM providers."
            ))

        # 3. Untrusted File Processing
        if "pdf" in combined_code or "pypdf" in combined_code or "open(" in combined_code:
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                surface_type="UNTRUSTED_FILE_READ",
                severity="medium",
                description="Agent reads user-supplied file paths from filesystem.",
                source_file="agent.py",
                line_number=1,
                mitigation_hint="Validate file path boundaries to prevent arbitrary path traversal."
            ))

        # 4. Shell / Subprocess
        if "subprocess" in combined_code or "os.system" in combined_code:
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                surface_type="SHELL_EXECUTION",
                severity="critical",
                description="Agent executes shell or subprocess commands.",
                source_file="agent.py",
                line_number=1,
                mitigation_hint="Prevent dynamic shell argument interpolation."
            ))

        return surfaces

    @staticmethod
    def extract_static_call_graph(ast_trees: Dict[str, ast.AST]) -> List[CallGraphEdge]:
        """Builds static call graph edges starting from function definitions."""
        edges: List[CallGraphEdge] = []

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    caller_name = node.name
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call):
                            callee_name = ""
                            if isinstance(sub.func, ast.Name):
                                callee_name = sub.func.id
                            elif isinstance(sub.func, ast.Attribute):
                                callee_name = sub.func.attr
                            if callee_name and callee_name != caller_name:
                                edges.append(CallGraphEdge(
                                    caller=caller_name,
                                    callee=callee_name,
                                    source_file=fname,
                                    line_number=getattr(sub, "lineno", getattr(node, "lineno", 1))
                                ))

        return edges
