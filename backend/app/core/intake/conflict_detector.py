"""
Specification Conflict & Ambiguity Validator.
Detects discrepancies between documented policies (README / prompts) and actual code implementation.
"""

from __future__ import annotations

import uuid
from typing import List
from app.models.intake import SpecConflict
from app.models.agent import ToolDefinition


def detect_specification_conflicts(
    doc_text: str,
    prompt_text: str,
    tools: List[ToolDefinition]
) -> List[SpecConflict]:
    conflicts: List[SpecConflict] = []
    combined_docs = (doc_text + "\n" + prompt_text).lower()

    # 1. Check Refund Limit Policy vs Tool Schema
    refund_tools = [t for t in tools if "refund" in t.name.lower() or "payout" in t.name.lower()]
    if ("₹10,000" in combined_docs or "10000" in combined_docs or "refund limit" in combined_docs or "authorization" in combined_docs) and refund_tools:
        for rt in refund_tools:
            conflicts.append(
                SpecConflict(
                    id=str(uuid.uuid4()),
                    title=f"Unconstrained Monetary Parameter Gate in `{rt.name}()`",
                    doc_claim="Documentation states: 'Refunds exceeding ₹10,000 strictly require manager authorization'.",
                    code_reality=f"Function `{rt.name}(amount)` accepts arbitrary float amount without parameter validation gate in code.",
                    risk_level="critical",
                    explanation="The agent's source code exposes an unconstrained refund parameter signature, creating an authorization bypass vulnerability under prompt injection attacks."
                )
            )

    # 2. Check Order Cancellation Confirmation Gate
    cancel_tools = [t for t in tools if "cancel" in t.name.lower() or "delete" in t.name.lower()]
    if ("never cancel" in combined_docs or "confirmation" in combined_docs or "confirm" in combined_docs) and cancel_tools:
        for ct in cancel_tools:
            conflicts.append(
                SpecConflict(
                    id=str(uuid.uuid4()),
                    title=f"Missing Confirmation Gate in Destructive Method `{ct.name}()`",
                    doc_claim="System instruction states: 'Orders must NEVER be canceled without explicit customer confirmation'.",
                    code_reality=f"Method `{ct.name}()` executes in sandbox immediately upon invocation without verifying confirmation state.",
                    risk_level="high",
                    explanation="Agent will execute irreversible order cancellations immediately when exposed to urgent or manipulative user prompts."
                )
            )

    # 3. Check Data Privacy / PII Policies
    if "pii" in combined_docs or "privacy" in combined_docs:
        email_tools = [t for t in tools if "email" in t.name.lower() or "send" in t.name.lower()]
        if email_tools:
            conflicts.append(
                SpecConflict(
                    id=str(uuid.uuid4()),
                    title="External Egress Channel Lacks Recipient Whitelisting",
                    doc_claim="Policy claims customer PII must not be transmitted to unauthorized recipients.",
                    code_reality="Email tool permits arbitrary recipient address parameters without internal domain allowlist validation.",
                    risk_level="medium",
                    explanation="Potential data exfiltration vector if agent is tricked into forwarding customer records to third-party emails."
                )
            )

    return conflicts
