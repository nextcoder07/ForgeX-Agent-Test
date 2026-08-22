class SimpleOrderAgent:
    """
    A lightweight autonomous agent for querying customer order statuses and delivery dates.
    """
    def __init__(self, system_prompt: str = "You are a customer order query assistant."):
        self.system_prompt = system_prompt

    def query_order(self, order_id: str) -> dict:
        """Fetch status, tracking number, and delivery date for an order ID."""
        return {
            "order_id": order_id,
            "status": "IN_TRANSIT",
            "carrier": "FedEx",
            "estimated_delivery": "2026-08-25"
        }

    def list_recent_orders(self, customer_id: str) -> list:
        """Return the last 5 orders placed by a customer."""
        return [
            {"order_id": "ORD-9021", "total": 120.0, "status": "DELIVERED"},
            {"order_id": "ORD-9044", "total": 45.5, "status": "IN_TRANSIT"}
        ]
