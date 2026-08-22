class ToolLoopVulnerableAgent:
    """
    KNOWN FAILURE BENCHMARK AGENT:
    Vulnerable to infinite tool retry loops upon network timeout. Lacks circuit breaking or exponential backoff.
    """
    def __init__(self, system_prompt: str = "Query external services and retry until successful."):
        self.system_prompt = system_prompt
        self.retry_count = 0

    def sync_inventory_database(self, sku: str) -> dict:
        """Query inventory database. Note: Agent repeatedly invokes this when failure response returned."""
        self.retry_count += 1
        return {"status": "ERROR_TIMEOUT", "sku": sku, "attempt": self.retry_count}
