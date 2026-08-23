"""
Hard unit test for Evidence Packet JSON Serialization.
Validates that all Pydantic models, nested entities, DetectedSecret, ToolDefinition,
DependencyDefinition, Enums, datetime, and Path objects serialize into valid JSON
without throwing TypeError or losing data.
"""

import datetime
import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

from app.core.intake.spec_reconstructor import to_json_safe
from app.models.agent import DependencyDefinition, ToolDefinition, ToolRisk
from app.models.agent_behavior import CodeInvariant, DataTransformation, FailureSurface
from app.models.dependency_model import DetectedSecret
from app.models.intake import AgentConstitution, NormalizedAgentSpec


class TestEvidencePacketSerialization(unittest.TestCase):
    def test_direct_detected_secret_serialization(self):
        """Verify DetectedSecret and list of secrets serialize cleanly."""
        secret = DetectedSecret(
            name="STRIPE_API_KEY",
            type="configured_in_env",
            required=True,
            masked_sample="sk_live_...1234",
            condition="payment_processing",
            fallback="mock_payment"
        )
        safe = to_json_safe(secret)
        raw_json = json.dumps(safe)
        self.assertIn("STRIPE_API_KEY", raw_json)
        self.assertIn("configured_in_env", raw_json)

    def test_full_complex_evidence_packet_serialization(self):
        """Verify comprehensive evidence packet with mixed models, enums, dates, and paths."""
        packet = {
            "analysis_context": {
                "run_id": str(uuid4()),
                "path": Path("/workspace/test-agents/03-customer-support"),
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
            },
            "credentials": [
                DetectedSecret(name="OPENAI_API_KEY", type="required_llm", required=True),
                DetectedSecret(name="NEWS_API_KEY", type="optional_service", required=False, fallback="mock_data")
            ],
            "tools": [
                ToolDefinition(
                    name="refund_order",
                    description="Monetary refund execution",
                    parameters_schema={"order_id": "string", "amount": "float"},
                    risk=ToolRisk.HIGH,
                    is_destructive=True,
                    side_effect_type="WRITE"
                )
            ],
            "dependencies": [
                DependencyDefinition(id="dep-1", name="requests", type="package", status="ready", detected_from="requirements.txt")
            ],
            "behavioral_facts": {
                "invariants": [
                    CodeInvariant(
                        statement="model == 'gpt-4o-mini'",
                        type="observed",
                        enforcement_level="hard",
                        testability="deterministic",
                        evidence="ChatOpenAI(model='gpt-4o-mini')",
                        confidence=1.0
                    )
                ],
                "transformations": [
                    DataTransformation(field="articles", operation="limit_items", parameters={"max_items": 5})
                ],
                "failure_surfaces": [
                    FailureSurface(
                        id="fs-1",
                        component="agent",
                        surface_type="security",
                        description="SSRF via URL parameter",
                        evidence="requests.get(url)"
                    )
                ]
            }
        }

        # Must convert to JSON safe and serialize without throwing
        safe_packet = to_json_safe(packet)
        serialized_str = json.dumps(safe_packet, indent=2)

        self.assertIsInstance(serialized_str, str)
        self.assertTrue(len(serialized_str) > 100)

        # Deserialize to verify structure
        deserialized = json.loads(serialized_str)
        self.assertEqual(deserialized["credentials"][0]["name"], "OPENAI_API_KEY")
        self.assertEqual(deserialized["tools"][0]["name"], "refund_order")
        self.assertEqual(deserialized["tools"][0]["risk"], "high")
        self.assertEqual(deserialized["behavioral_facts"]["invariants"][0]["statement"], "model == 'gpt-4o-mini'")


if __name__ == "__main__":
    unittest.main()
