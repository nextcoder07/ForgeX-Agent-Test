"""
Capability Catalog and Tool Resolution API Router.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter
from app.models.capability import CapabilityDefinition, DependencyBinding

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])

PLATFORM_CAPABILITY_CATALOG = [
    CapabilityDefinition(id="cap-01", code="CUSTOMER_LOOKUP", name="Customer Profile Lookup", description="Lookup customer name, tier, and account info", sandbox_adapter="generic_db_sandbox", risk_level="low"),
    CapabilityDefinition(id="cap-02", code="ORDER_LOOKUP", name="Order Details & Status Query", description="Query order details, shipping status, and items", sandbox_adapter="generic_db_sandbox", risk_level="low"),
    CapabilityDefinition(id="cap-03", code="REFUND_TRANSACTION", name="Monetary Refund Processing", description="Process financial refunds and payouts", sandbox_adapter="stripe_payment_sandbox", risk_level="critical", side_effect=True),
    CapabilityDefinition(id="cap-04", code="ORDER_CANCELLATION", name="Order Cancellation & Inventory Release", description="Cancel unfulfilled orders and release stock", sandbox_adapter="generic_db_sandbox", risk_level="high", side_effect=True),
    CapabilityDefinition(id="cap-05", code="ADDRESS_UPDATE", name="Shipping Address Modification", description="Update destination address for shipments", sandbox_adapter="generic_db_sandbox", risk_level="medium", side_effect=True),
    CapabilityDefinition(id="cap-06", code="EMAIL_NOTIFICATION", name="Customer Email Dispatch", description="Send transactional emails to customers", sandbox_adapter="sendgrid_email_sandbox", risk_level="low", side_effect=True),
    CapabilityDefinition(id="cap-07", code="KNOWLEDGE_SEARCH", name="Vectorized Knowledge Search", description="Retrieve document embeddings from knowledge base", sandbox_adapter="vector_rag_sandbox", risk_level="low"),
    CapabilityDefinition(id="cap-08", code="BROWSER_NAVIGATION", name="Headless Browser Navigation", description="Interact with web pages in headless browser", sandbox_adapter="playwright_browser_sandbox", risk_level="medium"),
]


@router.get("", response_model=List[CapabilityDefinition])
def get_capability_catalog():
    return PLATFORM_CAPABILITY_CATALOG


@router.get("/bindings", response_model=List[DependencyBinding])
def get_default_dependency_bindings():
    return [
        DependencyBinding(dependency_id="dep-db", name="PostgreSQL Database", binding_type="PLATFORM_SANDBOX", adapter_id="generic_db_sandbox", status="READY", details="In-memory disposable relational state store"),
        DependencyBinding(dependency_id="dep-payment", name="Stripe Payment Gateway", binding_type="PLATFORM_SANDBOX", adapter_id="stripe_payment_sandbox", status="READY", details="Simulated payment intents with ledger tracking"),
        DependencyBinding(dependency_id="dep-email", name="SendGrid Email API", binding_type="PLATFORM_SANDBOX", adapter_id="sendgrid_email_sandbox", status="READY", details="Redirects emails safely to sandbox mailbox inspect drawer"),
        DependencyBinding(dependency_id="dep-browser", name="Headless Browser Engine", binding_type="PLATFORM_SANDBOX", adapter_id="playwright_browser_sandbox", status="READY", details="Isolated browser DOM renderer"),
    ]
