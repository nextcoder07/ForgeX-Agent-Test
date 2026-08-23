"""
Canonical mock-tool naming used by ToolAnalyzer and MockToolFactory.
"""
from __future__ import annotations

from typing import Iterable, Optional

MOCK_TOOL_NAMES = {
    "database": "mock_database",
    "email": "mock_email",
    "http": "mock_http_api",
    "file": "mock_file_system",
    "search": "mock_search",
    "payment": "mock_payment",
}


def canonical_tool_key(name: str) -> str:
    n = (name or "").lower().replace("-", "_").strip()
    if n.startswith("mock_"):
        n = n[5:]
    if "database" in n or n in {"db", "sql"}:
        return "database"
    if "email" in n or "mail" in n:
        return "email"
    if "payment" in n or "refund" in n or "payout" in n or "charge" in n:
        return "payment"
    if "search" in n:
        return "search"
    if "file" in n or "filesystem" in n or n in {"fs"}:
        return "file"
    if "http" in n or "api" in n:
        return "http"
    return n


def mock_tool_name_for(name: str) -> str:
    key = canonical_tool_key(name)
    return MOCK_TOOL_NAMES.get(key, f"mock_{key}" if key else "mock_generic")


def tool_is_provided(name: str, provided_names: Iterable[str]) -> bool:
    target = canonical_tool_key(name)
    for provided in provided_names:
        if canonical_tool_key(provided) == target:
            return True
    return False


def infer_risk_level(name: str, fallback: Optional[str] = None) -> str:
    if fallback:
        return fallback
    key = canonical_tool_key(name)
    if key == "payment":
        return "critical"
    if key in {"database", "file", "http"}:
        return "medium"
    return "low"
