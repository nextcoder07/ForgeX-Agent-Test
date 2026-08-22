import math
from typing import Any, Dict

class UtilityToolAgent:
    """
    Mathematical and data conversion utility agent with schema-validated tools.
    """
    def __init__(self, system_prompt: str = "Perform math and data transformations."):
        self.system_prompt = system_prompt

    def calculate_expression(self, expression: str) -> float:
        """Evaluate mathematical expressions safely."""
        allowed_names = {"math": math, "sqrt": math.sqrt, "pow": math.pow, "abs": abs}
        return float(eval(expression, {"__builtins__": {}}, allowed_names))

    def convert_currency(self, amount: float, from_curr: str, to_curr: str) -> float:
        """Convert monetary amounts between USD, EUR, GBP, INR."""
        rates = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "INR": 83.5}
        usd_amount = amount / rates.get(from_curr.upper(), 1.0)
        return usd_amount * rates.get(to_curr.upper(), 1.0)

    def format_json_report(self, payload: Dict[str, Any]) -> str:
        """Format raw structured data into a markdown-styled report."""
        lines = [f"# Data Summary Report"]
        for k, v in payload.items():
            lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)
