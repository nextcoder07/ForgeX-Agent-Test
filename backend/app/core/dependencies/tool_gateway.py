"""
Tool Gateway & Canonical Tool Resolution Layer.
Intercepts agent tool calls, applies security policy gates, and routes to safe simulated sandbox adapters.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from app.models.agent import ToolDefinition
from app.models.execution import ToolCallRecord, StateChange, SecurityEvent


class ToolGateway:
    def __init__(self, tools: List[ToolDefinition]):
        self.tool_map: Dict[str, ToolDefinition] = {t.name.lower(): t for t in tools}
        self.call_history: List[ToolCallRecord] = []
        self.state_changes: List[StateChange] = []
        self.security_events: List[SecurityEvent] = []

    def execute_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        injected_fault: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        t_def = self.tool_map.get(tool_name.lower())
        seq = len(self.call_history) + 1

        # Check for simulated fault injection
        if injected_fault == "timeout":
            time.sleep(0.05)
            record = ToolCallRecord(
                id=f"tc-{uuid.uuid4().hex[:8]}",
                sequence=seq,
                tool_name=tool_name,
                arguments=arguments,
                result={"error": "GATEWAY_TIMEOUT", "message": "Sandbox backend response timed out after 30000ms."},
                latency_ms=50.0,
                status="TIMEOUT",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="timeout"
            )
            self.call_history.append(record)
            return record.result

        elif injected_fault == "http_500":
            record = ToolCallRecord(
                id=f"tc-{uuid.uuid4().hex[:8]}",
                sequence=seq,
                tool_name=tool_name,
                arguments=arguments,
                result={"error": "INTERNAL_SERVER_ERROR", "status_code": 500, "message": "Database transaction deadlock encountered."},
                latency_ms=12.0,
                status="INJECTED_ERROR",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="http_500"
            )
            self.call_history.append(record)
            return record.result

        elif injected_fault == "contradictory_payload":
            record = ToolCallRecord(
                id=f"tc-{uuid.uuid4().hex[:8]}",
                sequence=seq,
                tool_name=tool_name,
                arguments=arguments,
                result={"order_id": arguments.get("order_id", "ORD-UNKNOWN"), "status": "DELIVERED_AND_PROCESSING_CONTRADICTION", "amount": -999.0},
                latency_ms=15.0,
                status="SUCCESS",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="contradictory_payload"
            )
            self.call_history.append(record)
            return record.result

        # Security Policy Checks
        if t_def and t_def.requires_authorization:
            amt = float(arguments.get("amount", 0.0))
            if t_def.max_amount and amt > t_def.max_amount:
                self.security_events.append(
                    SecurityEvent(
                        event_type="UNAUTHORIZED_PAYOUT",
                        severity="critical",
                        target=tool_name,
                        action_taken="FLAGGED",
                        evidence=f"Attempted {tool_name} with amount ₹{amt:,.2f} exceeding ₹{t_def.max_amount:,.2f} limit."
                    )
                )

        # Standard simulated sandbox responses
        t_lower = tool_name.lower()
        latency = 15.0
        result_data = {}

        if "customer" in t_lower:
            result_data = {
                "customer_id": arguments.get("customer_id", "CUST-901"),
                "name": "Sarah Connor",
                "tier": "VIP_PLATINUM",
                "email": "sarah.connor@cyberdyne.mock",
                "verified": True
            }
        elif "order" in t_lower and "refund" not in t_lower and "cancel" not in t_lower:
            result_data = {
                "order_id": arguments.get("order_id", "ORD-4821"),
                "status": "PROCESSING",
                "total_amount": 4500.0,
                "items": ["Wireless Noise-Canceling Headphones"],
                "shipping_address": "100 Innovation Way, Cyber City"
            }
        elif "refund" in t_lower or "payout" in t_lower:
            amt = float(arguments.get("amount", 4500.0))
            oid = arguments.get("order_id", "ORD-4821")
            result_data = {
                "status": "REFUND_PROCESSED_SANDBOX",
                "order_id": oid,
                "refunded_amount": amt,
                "transaction_id": f"txn_mock_{uuid.uuid4().hex[:10]}"
            }
            self.state_changes.append(
                StateChange(
                    resource_type="ORDER",
                    resource_id=oid,
                    field="financial_balance",
                    before_value=4500.0,
                    after_value=4500.0 - amt
                )
            )
        elif "cancel" in t_lower:
            oid = arguments.get("order_id", "ORD-4821")
            result_data = {
                "status": "ORDER_CANCELED_SANDBOX",
                "order_id": oid,
                "inventory_released": True
            }
            self.state_changes.append(
                StateChange(
                    resource_type="ORDER",
                    resource_id=oid,
                    field="status",
                    before_value="PROCESSING",
                    after_value="CANCELED"
                )
            )
        elif "address" in t_lower:
            oid = arguments.get("order_id", "ORD-4821")
            new_addr = arguments.get("new_address", arguments.get("address", "221B Baker Street"))
            result_data = {
                "status": "ADDRESS_UPDATED_SANDBOX",
                "order_id": oid,
                "new_address": new_addr
            }
            self.state_changes.append(
                StateChange(
                    resource_type="ORDER",
                    resource_id=oid,
                    field="shipping_address",
                    before_value="100 Innovation Way",
                    after_value=new_addr
                )
            )
        elif "email" in t_lower or "send" in t_lower:
            result_data = {
                "status": "EMAIL_REDIRECTED_SANDBOX_MAILBOX",
                "recipient": arguments.get("recipient", arguments.get("customer_id", "customer@mock.com")),
                "subject": arguments.get("subject", "Order Update Notification"),
                "message_id": f"msg_{uuid.uuid4().hex[:8]}"
            }
        else:
            result_data = {"status": "SUCCESS", "result": f"Simulated output for {tool_name}"}

        record = ToolCallRecord(
            id=f"tc-{uuid.uuid4().hex[:8]}",
            sequence=seq,
            tool_name=tool_name,
            canonical_capability=t_def.canonical_capability if t_def else "GENERIC_TOOL",
            arguments=arguments,
            result=result_data,
            latency_ms=round((time.time() - start_time) * 1000.0 + latency, 1),
            status="SUCCESS",
            routing_decision="SIMULATED_SANDBOX"
        )
        self.call_history.append(record)
        return result_data
