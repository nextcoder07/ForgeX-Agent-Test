"""
Capability Catalog and Canonical Tool Mapping Models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CapabilityDefinition(BaseModel):
    id: str
    code: str  # e.g., "CUSTOMER_LOOKUP", "EMAIL_SEND", "DATABASE_QUERY"
    name: str
    description: str
    sandbox_adapter: str  # e.g., "generic_db_sandbox", "generic_email_sandbox"
    risk_level: str  # "low", "medium", "high", "critical"
    side_effect: bool = False


class CanonicalToolMapping(BaseModel):
    original_tool_name: str
    canonical_capability: str
    mapped_sandbox_adapter: str
    routing_strategy: str  # "SIMULATE", "REDIRECT", "PASS_THROUGH", "BLOCK"
    policy_constraints: Dict[str, Any] = Field(default_factory=dict)


class DependencyBinding(BaseModel):
    dependency_id: str
    name: str
    binding_type: str  # "PLATFORM_SANDBOX", "USER_SUPPLIED", "MOCK_GATEWAY"
    adapter_id: str
    status: str  # "READY", "PARTIAL", "BLOCKED"
    details: Optional[str] = None
