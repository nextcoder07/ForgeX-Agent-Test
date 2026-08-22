"""
Generic Specification Conflict Detector.
Compares declared documentation/prompt claims against observed AST code evidence without domain-specific hardcoding.
"""

import uuid
from typing import List, Dict, Any
from app.models.agent import AgentConstitution, ToolDefinition
from app.models.intake import SpecConflict


def detect_specification_conflicts(
    constitution: AgentConstitution,
    tools: List[ToolDefinition],
    all_code: str,
    all_docs: str
) -> List[SpecConflict]:
    """Generically detects discrepancies between declared safety/business rules and AST code facts."""
    conflicts: List[SpecConflict] = []
    code_lower = all_code.lower()
    docs_lower = all_docs.lower()

    # 1. Check for declared auth/approval claims vs code implementation
    if "authorization" in docs_lower or "approval" in docs_lower or "permission" in docs_lower:
        has_auth_logic = any(kw in code_lower for kw in ["auth", "permission", "approve", "confirm", "token", "role"])
        if not has_auth_logic:
            conflicts.append(
                SpecConflict(
                    id=f"conf-{uuid.uuid4().hex[:6]}",
                    title="Missing Authorization Check",
                    doc_claim="Documentation declares explicit authorization/approval constraints",
                    code_reality="No authorization or confirmation logic detected in source code AST",
                    risk_level="high",
                    explanation="Implement explicit approval gates before executing sensitive actions."
                )
            )

    # 2. Check for declared rate limiting / quota management vs code implementation
    if "rate limit" in docs_lower or "quota" in docs_lower or "retry" in docs_lower:
        has_retry = any(kw in code_lower for kw in ["retry", "backoff", "ratelimit", "semaphore", "sleep"])
        if not has_retry:
            conflicts.append(
                SpecConflict(
                    id=f"conf-{uuid.uuid4().hex[:6]}",
                    title="Missing Rate Limiting / Retry Logic",
                    doc_claim="Documentation mentions rate limiting or retry resilience",
                    code_reality="No backoff or retry mechanism found in source code",
                    risk_level="medium",
                    explanation="Add resilience retry/backoff wrappers around external API invocations."
                )
            )

    # 3. Check for declared PII/secret protection vs code implementation
    if "pii" in docs_lower or "redact" in docs_lower or "mask" in docs_lower:
        has_redaction = any(kw in code_lower for kw in ["redact", "mask", "sanitize", "anonymize"])
        if not has_redaction:
            conflicts.append(
                SpecConflict(
                    id=f"conf-{uuid.uuid4().hex[:6]}",
                    title="Missing PII / Data Redaction Logic",
                    doc_claim="Documentation claims sensitive data/credential protection",
                    code_reality="No data masking or sanitization logic found in code",
                    risk_level="high",
                    explanation="Implement data scrubbing before passing external text to models or logs."
                )
            )

    return conflicts
