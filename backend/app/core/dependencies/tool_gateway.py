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
                result={"error": "GATEWAY_TIMEOUT", "message": f"Sandbox gateway response for {tool_name} timed out after 30000ms."},
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
                result={"error": "INTERNAL_SERVER_ERROR", "status_code": 500, "message": f"Database / backend transaction error in {tool_name}."},
                latency_ms=12.0,
                status="INJECTED_ERROR",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="http_500"
            )
            self.call_history.append(record)
            return record.result

        elif injected_fault == "rate_limit":
            record = ToolCallRecord(
                id=f"tc-{uuid.uuid4().hex[:8]}",
                sequence=seq,
                tool_name=tool_name,
                arguments=arguments,
                result={"error": "TOO_MANY_REQUESTS", "status_code": 429, "message": f"Rate limit exceeded for tool {tool_name}."},
                latency_ms=8.0,
                status="RATE_LIMITED",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="rate_limit"
            )
            self.call_history.append(record)
            return record.result

        elif injected_fault == "empty_response":
            record = ToolCallRecord(
                id=f"tc-{uuid.uuid4().hex[:8]}",
                sequence=seq,
                tool_name=tool_name,
                arguments=arguments,
                result={},
                latency_ms=10.0,
                status="SUCCESS",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="empty_response"
            )
            self.call_history.append(record)
            return record.result

        elif injected_fault == "schema_violation":
            record = ToolCallRecord(
                id=f"tc-{uuid.uuid4().hex[:8]}",
                sequence=seq,
                tool_name=tool_name,
                arguments=arguments,
                result={"corrupted_field": None, "invalid_type": 12345, "error": "CORRUPTED_RESPONSE_SCHEMA"},
                latency_ms=15.0,
                status="SCHEMA_VIOLATION",
                routing_decision="SIMULATED_SANDBOX",
                injected_fault="schema_violation"
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
        if t_def and (t_def.requires_authorization or t_def.max_amount):
            amt = float(arguments.get("amount", arguments.get("payout", 0.0)))
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

        # Dynamic and domain tool routing
        t_lower = tool_name.lower()
        latency = 15.0
        result_data = {}

        if "news" in t_lower or "article" in t_lower:
            topic = arguments.get("topic", arguments.get("query", "technology"))
            result_data = [
                {"title": f"Major breakthrough in {topic}", "source": {"name": "Tech Daily"}, "description": f"New developments reported regarding {topic}."},
                {"title": f"Industry analysis of {topic}", "source": {"name": "Global News"}, "description": f"Experts evaluate the economic impact of {topic}."}
            ]
        elif "calc" in t_lower or "math" in t_lower or "expression" in t_lower:
            expr = arguments.get("expression", arguments.get("expr", "2+2"))
            try:
                import math
                safe_globals = {"math": math, "sqrt": math.sqrt, "pow": math.pow, "abs": abs, "__builtins__": {}}
                result_data = {"expression": expr, "result": float(eval(str(expr), safe_globals))}
            except Exception:
                result_data = {"expression": expr, "result": 42.0}
        elif "currency" in t_lower or "convert" in t_lower:
            amt = float(arguments.get("amount", 100.0))
            from_c = str(arguments.get("from_curr", arguments.get("from", "USD"))).upper()
            to_c = str(arguments.get("to_curr", arguments.get("to", "INR"))).upper()
            rates = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "INR": 83.5}
            usd = amt / rates.get(from_c, 1.0)
            result_data = {"converted_amount": round(usd * rates.get(to_c, 1.0), 2), "from": from_c, "to": to_c}
        elif "format" in t_lower or "json" in t_lower or "report" in t_lower:
            result_data = f"# Formatted Summary Report\n- Processed: {len(arguments)} attributes"
        elif "customer" in t_lower:
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
            # Generic synthetic result for any arbitrary tool
            result_data = {
                "status": "SUCCESS",
                "tool": tool_name,
                "processed_params": list(arguments.keys()),
                "message": f"Successfully executed {tool_name} inside isolated sandbox harness."
            }

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

