"""
Capability Extractor for Member 1.
Identifies agent capabilities from tools and system prompts, reconciling them with the platform catalog.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.models.agent import ToolDefinition
from app.models.agent_test_spec import Capability

# Re-use catalog details for standard mapping
STANDARD_CAPABILITIES = {
    "CUSTOMER_LOOKUP": {
        "name": "Customer Profile Lookup",
        "description": "Lookup customer details (name, tier, and account verification status)",
        "outputs": ["Customer record dict", "Verification flag"],
        "risks": ["PII leakage", "Social engineering vulnerability"]
    },
    "ORDER_LOOKUP": {
        "name": "Order Details & Status Query",
        "description": "Query order details, shipping status, and items",
        "outputs": ["Order status dict", "Tracking info"],
        "risks": ["Disclosing order details to unauthorized parties"]
    },
    "REFUND_TRANSACTION": {
        "name": "Monetary Refund Processing",
        "description": "Process financial refunds and payouts",
        "outputs": ["Refund transaction record", "Stripe payment intent status"],
        "risks": ["Financial loss via unauthorized high-value refund bypass", "Uncapped refund amount execution"]
    },
    "ORDER_CANCELLATION": {
        "name": "Order Cancellation & Inventory Release",
        "description": "Cancel unfulfilled orders and release stock",
        "outputs": ["Cancellation success record", "Inventory release status"],
        "risks": ["Irreversible inventory cancellation without customer confirmation"]
    },
    "ADDRESS_UPDATE": {
        "name": "Shipping Address Modification",
        "description": "Update destination address for shipments",
        "outputs": ["Updated order address dict"],
        "risks": ["Bypassing address validation", "Fraudulent redirection of shipments"]
    },
    "EMAIL_NOTIFICATION": {
        "name": "Customer Email Dispatch",
        "description": "Send transactional emails to customers",
        "outputs": ["SMTP email dispatch status"],
        "risks": ["Spamming customers", "Phishing email dispatch bypass"]
    },
    "KNOWLEDGE_SEARCH": {
        "name": "Vectorized Knowledge Search",
        "description": "Retrieve document embeddings from knowledge base",
        "outputs": ["List of relevant document chunks"],
        "risks": ["Hallucinated search results", "Retrieving outdated policies"]
    },
    "BROWSER_NAVIGATION": {
        "name": "Headless Browser Navigation",
        "description": "Interact with web pages in headless browser",
        "outputs": ["Scraped page content", "Screenshot paths"],
        "risks": ["SSRF vulnerability", "Unbounded scraping of untrusted sites"]
    }
}

class CapabilityExtractor:
    @staticmethod
    def extract_capabilities(
        tools: List[ToolDefinition],
        llm_capabilities: Optional[List[Dict[str, Any]]] = None
    ) -> List[Capability]:
        """
        Extract and construct Capability definitions.
        If llm_capabilities is provided (from LLM semantic analysis), parses it into schemas.
        Otherwise, maps AST-extracted tools to canonical or dynamic capabilities.
        """
        capabilities_map: Dict[str, Capability] = {}

        # 1. Process LLM-extracted capabilities if available
        if llm_capabilities:
            for item in llm_capabilities:
                cap_id = item.get("capability_id", "").upper().strip()
                if not cap_id:
                    continue
                
                # Check if it matches standard catalog to populate gaps
                name = item.get("name")
                desc = item.get("description")
                outputs = item.get("outputs", [])
                risks = item.get("risks", [])
                
                if cap_id in STANDARD_CAPABILITIES:
                    std = STANDARD_CAPABILITIES[cap_id]
                    name = name or std["name"]
                    desc = desc or std["description"]
                    outputs = outputs or std["outputs"]
                    risks = risks or std["risks"]
                
                # Identify related tools from the list matching the capability
                related_tools = item.get("related_tools", [])
                if not related_tools:
                    # Infer from tool canonical capabilities or names
                    related_tools = [
                        t.name for t in tools 
                        if (t.canonical_capability and t.canonical_capability.upper() == cap_id)
                        or cap_id.lower() in t.name.lower()
                    ]

                # Extract inputs (consolidated schema of all related tools parameters)
                inputs: Dict[str, Any] = {}
                for tname in related_tools:
                    tool_def = next((t for t in tools if t.name == tname), None)
                    if tool_def and tool_def.parameters_schema:
                        inputs.update(tool_def.parameters_schema)

                capabilities_map[cap_id] = Capability(
                    capability_id=cap_id,
                    name=name or f"Capability {cap_id.replace('_', ' ').title()}",
                    description=desc or f"Executes capability actions for {cap_id}",
                    related_tools=related_tools,
                    inputs=inputs,
                    outputs=outputs or ["Success execution dictionary"],
                    risks=risks or ["Unbounded capability execution risk"]
                )

        # 2. Complete mapping from tools to ensure coverage of all tools
        for tool in tools:
            # Determine canonical code
            cap_id = (tool.canonical_capability or "GENERIC_TOOL").upper()
            if cap_id == "GENERIC_TOOL":
                # Try to map based on common naming convention
                fname_lower = tool.name.lower()
                if "customer" in fname_lower:
                    cap_id = "CUSTOMER_LOOKUP"
                elif "order" in fname_lower and "refund" not in fname_lower and "cancel" not in fname_lower:
                    cap_id = "ORDER_LOOKUP"
                elif "refund" in fname_lower or "payout" in fname_lower:
                    cap_id = "REFUND_TRANSACTION"
                elif "cancel" in fname_lower:
                    cap_id = "ORDER_CANCELLATION"
                elif "address" in fname_lower:
                    cap_id = "ADDRESS_UPDATE"
                elif "email" in fname_lower or "send" in fname_lower:
                    cap_id = "EMAIL_NOTIFICATION"
                elif "search" in fname_lower or "knowledge" in fname_lower:
                    cap_id = "KNOWLEDGE_SEARCH"
                else:
                    # Fallback to function name capitalized
                    cap_id = tool.name.upper()

            # If we don't have this capability in map, create it
            if cap_id not in capabilities_map:
                if cap_id in STANDARD_CAPABILITIES:
                    std = STANDARD_CAPABILITIES[cap_id]
                    name = std["name"]
                    desc = std["description"]
                    outputs = std["outputs"]
                    risks = std["risks"]
                else:
                    name = f"Custom Tool {tool.name.replace('_', ' ').title()}"
                    desc = tool.description or f"Executes agent function {tool.name}"
                    outputs = ["Function execution result object"]
                    risks = ["Tool execution integrity vulnerability"]

                capabilities_map[cap_id] = Capability(
                    capability_id=cap_id,
                    name=name,
                    description=desc,
                    related_tools=[tool.name],
                    inputs=dict(tool.parameters_schema or {}),
                    outputs=outputs,
                    risks=risks
                )
            else:
                # Add tool to related tools of existing capability if not present
                cap = capabilities_map[cap_id]
                if tool.name not in cap.related_tools:
                    cap.related_tools.append(tool.name)
                # Merge parameter schemas
                if tool.parameters_schema:
                    cap.inputs.update(tool.parameters_schema)

        return list(capabilities_map.values())
