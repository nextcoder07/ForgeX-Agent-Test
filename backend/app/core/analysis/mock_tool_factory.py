"""
Mock Tool Factory Component.
Provisions safe, sandboxed mock ToolDefinition objects for missing required tools.
"""
from __future__ import annotations

import logging
from app.models.agent import ToolDefinition, ToolRisk
from app.core.analysis.tool_catalog import canonical_tool_key, infer_risk_level, mock_tool_name_for

logger = logging.getLogger(__name__)

_MOCK_TEMPLATES = {
    "database": {
        "purpose": "Sandboxed mock database for read/write of agent-owned records",
        "canonical": "DATABASE_ACCESS",
        "side_effect": "WRITE",
        "schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["read", "write", "update", "delete"]},
                "table": {"type": "string"},
                "query": {"type": "object"},
            },
            "required": ["operation"],
        },
    },
    "email": {
        "purpose": "Sandboxed mock email sender that records outbound messages",
        "canonical": "EMAIL_NOTIFICATION",
        "side_effect": "EMAIL",
        "schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject"],
        },
    },
    "http": {
        "purpose": "Sandboxed mock HTTP API client with recorded requests",
        "canonical": "HTTP_API_CALL",
        "side_effect": "WRITE",
        "schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "url": {"type": "string"},
                "body": {"type": "object"},
            },
            "required": ["method", "url"],
        },
    },
    "file": {
        "purpose": "Sandboxed mock filesystem confined to the agent workspace",
        "canonical": "FILE_SYSTEM_ACCESS",
        "side_effect": "WRITE",
        "schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["read", "write", "list", "delete"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["operation", "path"],
        },
    },
    "search": {
        "purpose": "Sandboxed mock search index returning deterministic results",
        "canonical": "WEB_SEARCH",
        "side_effect": "READ",
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["query"],
        },
    },
    "payment": {
        "purpose": "Sandboxed mock payment/refund processor with recorded transactions",
        "canonical": "PAYMENT_TRANSACTION",
        "side_effect": "PAYOUT",
        "schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["charge", "refund", "payout"]},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "order_id": {"type": "string"},
            },
            "required": ["action", "amount"],
        },
    },
}


class MockToolFactory:
    @staticmethod
    def provision_mock_tool(name: str, purpose: str = "", risk_level: str = "") -> ToolDefinition:
        """Returns a sandboxed mock ToolDefinition with safe capabilities and recorded actions."""
        key = canonical_tool_key(name)
        mock_name = mock_tool_name_for(name)
        template = _MOCK_TEMPLATES.get(key, {})
        resolved_purpose = purpose or template.get("purpose", f"Sandboxed mock for {name}")
        r_lower = infer_risk_level(name, risk_level or None).lower()
        if r_lower == "critical":
            risk = ToolRisk.CRITICAL
        elif r_lower == "high":
            risk = ToolRisk.HIGH
        elif r_lower == "medium":
            risk = ToolRisk.MEDIUM
        else:
            risk = ToolRisk.LOW

        side_effect = template.get("side_effect", "READ")
        canonical = template.get("canonical", "GENERIC_TOOL")
        is_payment = key == "payment"

        logger.info("Provisioning mock tool '%s' for required capability '%s'", mock_name, name)
        return ToolDefinition(
            name=mock_name,
            description=f"Safe Mock Tool: {resolved_purpose}",
            parameters_schema=template.get("schema"),
            risk=risk,
            is_destructive=risk in (ToolRisk.HIGH, ToolRisk.CRITICAL) or key in {"database", "file", "payment"},
            requires_confirmation=is_payment,
            requires_authorization=is_payment,
            max_amount=10000.0 if is_payment else None,
            canonical_capability=canonical,
            side_effect_type=side_effect,
        )
