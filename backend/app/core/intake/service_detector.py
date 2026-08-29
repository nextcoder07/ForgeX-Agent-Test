"""
Service & Capability Detector Module.
Generic SDK/client and credential detector that maps external integrations to capabilities
strictly based on AST evidence and environment variable declarations.
Never fabricates default capabilities (e.g. LLM_INFERENCE) when not present in source code.
"""

from __future__ import annotations

import ast
import re
from typing import Dict, List, Any
from app.models.dependency_model import DetectedSecret


class ServiceDetector:
    # Generic mapping patterns: SDK / Class Name / Modules -> Capability
    CAPABILITY_PATTERNS = {
        r"Tavily|Serper|DuckDuckGo|BraveSearch|GoogleSearch": "WEB_SEARCH",
        r"ChatOpenAI|ChatGoogleGenerativeAI|Anthropic|ChatAnthropic|LLM|OpenAI": "LLM_INFERENCE",
        r"pypdf|PdfReader|pdfplumber|PyPDF2|fitz|SimpleDirectoryReader": "PDF_TEXT_EXTRACTION",
        r"parse_resume|resume_parser|candidate_profile": "RESUME_PARSING",
        r"parse_resume|parse_json_response|extract_profile|structured_profile": "STRUCTURED_PROFILE_EXTRACTION",
        r"score_fit|fit_score|job_fit|fit_analysis": "JOB_FIT_SCORING",
        r"recommendation|candidate_recommendation|fit_label": "CANDIDATE_RECOMMENDATION",
        r"Stripe|PayPal|Razorpay": "PAYMENT",
        r"SMTP|SendGrid|Mailgun|Email": "EMAIL",
        r"Postgres|MySQL|MongoDB|Supabase|SQLite|Redis|SQLAlchemy|SQLDatabase": "SQL_DATABASE_QUERY",
        r"S3|GoogleDrive|Dropbox|FileSystem": "FILESYSTEM",
        r"requests|httpx|urllib|http_endpoint": "HTTP_API_ACCESS",
        r"fetch_news|get_news|newsapi": "NEWS_RETRIEVAL",
        r"summarize_news|news_summary|summarize_articles": "NEWS_SUMMARIZATION",
        r"news_briefing|structured_briefing|briefing": "STRUCTURED_NEWS_BRIEFING",
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
    def detect_services_and_capabilities(ast_trees: Dict[str, ast.AST] = None, raw_files: Dict[str, str] = None) -> Dict[str, Any]:
        """Detects external service calls, capabilities, and credential references strictly from code evidence."""
        ast_trees = ast_trees or {}
        raw_files = raw_files or {}
        external_calls: List[Dict[str, Any]] = []
        capabilities: List[str] = []
        credential_refs: List[DetectedSecret] = []
        discovered_secrets_set = set()

        # 1. Parse declared credentials from env template files (.env.example, .env.sample)
        for fname, content in raw_files.items():
            if ".env" in fname.lower():
                is_example = "example" in fname.lower() or "sample" in fname.lower()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key_name = line.split("=")[0].strip()
                        if key_name and key_name not in discovered_secrets_set:
                            discovered_secrets_set.add(key_name)
                            credential_refs.append(
                                DetectedSecret(
                                    name=key_name,
                                    type="declared_in_template" if is_example else "configured_in_env",
                                    required=True,
                                    masked_sample=f"[{'TEMPLATE' if is_example else 'CONFIGURED'}]"
                                )
                            )

        # 2. Parse AST trees for SDK class instantiations, imports, and os.getenv references
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # Detect Class Instantiations (e.g. TavilySearch(), ChatOpenAI())
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
                                    "line": getattr(node, "lineno", 1),
                                    "evidence": f"Instantiated {class_name}() in {fname}"
                                })

                # Detect Imports (e.g. from langchain_openai import ChatOpenAI)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        full_name = f"{mod}.{alias.name}"
                        for pattern, cap in ServiceDetector.CAPABILITY_PATTERNS.items():
                            if re.search(pattern, full_name, re.IGNORECASE) or re.search(pattern, alias.name, re.IGNORECASE):
                                if cap not in capabilities:
                                    capabilities.append(cap)

                # Detect Function Definitions (e.g. parse_resume, score_fit, read_pdf_text)
                elif isinstance(node, ast.FunctionDef):
                    fn_name = node.name.lower()
                    for pattern, cap in ServiceDetector.CAPABILITY_PATTERNS.items():
                        if re.search(pattern, fn_name, re.IGNORECASE):
                            if cap not in capabilities:
                                capabilities.append(cap)

                # Detect os.getenv / os.environ references in code
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
                                            type="referenced_in_code",
                                            required=True,
                                            masked_sample="[REFERENCED_IN_CODE]"
                                        )
                                    )

        # Pure evidence: do NOT fabricate default LLM_INFERENCE if none discovered
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
