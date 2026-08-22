"""
Unit tests for Member 1 Pipeline.
Tests semantic analyzer, capability extractor, scenario generator, critic, validator, library, and coverage.
"""
from __future__ import annotations

import os
import unittest
import tempfile
from typing import List

from app.core.member1_pipeline import (
    analyze_agent,
    generate_scenarios,
    validate_scenarios,
    calculate_coverage
)
from app.core.scenarios.library import ScenarioLibrary
from app.models.agent_test_spec import AgentTestSpecification, ScenarioDefinition

class TestMember1Pipeline(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Resolve test agent paths dynamically relative to this test file
        cls.tests_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # backend/tests
        cls.backend_dir = os.path.dirname(cls.tests_dir) # backend
        cls.agents_dir = os.path.join(cls.backend_dir, "test-agents")
        
        cls.customer_support_path = os.path.join(cls.agents_dir, "03-customer-support")
        cls.tool_agent_path = os.path.join(cls.agents_dir, "02-tool-agent")
        cls.news_agent_path = os.path.join(cls.agents_dir, "09-news-summarizer-agent")

    async def test_semantic_intake_customer_support(self):
        """Test intake and capability mapping for 03-customer-support agent."""
        spec = await analyze_agent(self.customer_support_path)
        
        self.assertIsInstance(spec, AgentTestSpecification)
        self.assertEqual(spec.name, "Customer Support Agent")
        self.assertTrue(len(spec.tools) >= 5, f"Expected customer support to have tools, found {len(spec.tools)}")
        
        # Verify tool definitions parsed correctly
        tool_names = {t.name for t in spec.tools}
        self.assertIn("refund_order", tool_names)
        self.assertIn("cancel_order", tool_names)
        self.assertIn("get_customer", tool_names)
        
        # Verify capability extraction mapping
        cap_ids = {c.capability_id.upper() for c in spec.capabilities}
        self.assertIn("REFUND_TRANSACTION", cap_ids)
        self.assertIn("ORDER_CANCELLATION", cap_ids)
        self.assertIn("CUSTOMER_LOOKUP", cap_ids)

        refund_cap = next(c for c in spec.capabilities if c.capability_id == "REFUND_TRANSACTION")
        self.assertIn("refund_order", refund_cap.related_tools)
        self.assertIn("amount", refund_cap.inputs)

    async def test_semantic_intake_tool_agent(self):
        """Test intake and capability mapping for 02-tool-agent."""
        spec = await analyze_agent(self.tool_agent_path)
        
        self.assertIsInstance(spec, AgentTestSpecification)
        self.assertTrue("Utility" in spec.name or "Tool" in spec.name)
        
        tool_names = {t.name for t in spec.tools}
        self.assertIn("calculate_expression", tool_names)
        self.assertIn("convert_currency", tool_names)
        self.assertIn("format_json_report", tool_names)

        # Verify capability extractor created capability
        cap_ids = {c.capability_id.upper() for c in spec.capabilities}
        self.assertTrue(any("CALCULATE" in cid or "CURRENCY" in cid or "FORMAT" in cid or "GENERIC" in cid for cid in cap_ids))

    async def test_scenario_generation_and_critic(self):
        """Test scenario generation pipelines and critic filtering."""
        spec = await analyze_agent(self.customer_support_path)
        
        # Generate 12 scenarios
        scenarios = await generate_scenarios(spec, count=12, run_critic=True)
        
        self.assertTrue(len(scenarios) > 0, "Scenario list should not be empty")
        self.assertTrue(len(scenarios) <= 12, "Scenario count should respect maximum constraint")
        
        for sc in scenarios:
            self.assertIsInstance(sc, ScenarioDefinition)
            self.assertTrue(sc.scenario_id.startswith("SC-"))
            self.assertIsNotNone(sc.critic_status)
            self.assertIn(sc.critic_status, ["PASS", "MODIFY", "REJECT"])

    def test_scenario_deduplication(self):
        """Verify duplicate generation prompts are filtered out."""
        from app.core.scenarios.generator import _deduplicate_scenarios
        
        raw_list = [
            ScenarioDefinition(
                scenario_id="SC-NOR-1",
                capability_id="SEARCH_NEWS",
                category="NORMAL",
                description="Search AI topic",
                input={"topic": "artificial intelligence", "message": "Search AI"},
                expected_behavior="Executes",
                required_tools=["fetch_news"]
            ),
            ScenarioDefinition(
                scenario_id="SC-NOR-2",
                capability_id="SEARCH_NEWS",
                category="NORMAL",
                description="Search AI topic identical",
                input={"topic": "artificial intelligence", "message": "Search AI"},
                expected_behavior="Executes duplicate",
                required_tools=["fetch_news"]
            )
        ]
        
        deduped = _deduplicate_scenarios(raw_list)
        self.assertEqual(len(deduped), 1, "Deduplication should keep only one identical input signature scenario")

    async def test_scenario_validator_happy_path(self):
        """Test scenario validator successfully validates correct scenarios."""
        spec = await analyze_agent(self.customer_support_path)
        scenarios = await generate_scenarios(spec, count=4, run_critic=False)
        
        val_res = validate_scenarios(scenarios, spec)
        self.assertIsInstance(val_res, dict)
        self.assertTrue(val_res["is_valid"], f"Expected valid scenarios, errors found: {val_res['errors']}")

    async def test_scenario_validator_failures(self):
        """Verify validator flags malformed entries, bad categories, and missing tools."""
        spec = await analyze_agent(self.customer_support_path)
        
        bad_scenarios = [
            # 1. Invalid category
            ScenarioDefinition(
                scenario_id="SC-BAD-1",
                capability_id="REFUND_TRANSACTION",
                category="NOT_A_REAL_CATEGORY",
                description="Test bad category",
                expected_behavior="Fails validation",
                required_tools=["refund_order"]
            ),
            # 2. Missing tool reference
            ScenarioDefinition(
                scenario_id="SC-BAD-2",
                capability_id="REFUND_TRANSACTION",
                category="NORMAL",
                description="Test missing tool",
                expected_behavior="Fails validation",
                required_tools=["not_a_real_tool_name"]
            ),
            # 3. Non-existent capability
            ScenarioDefinition(
                scenario_id="SC-BAD-3",
                capability_id="NON_EXISTENT_CAP",
                category="NORMAL",
                description="Test missing cap",
                expected_behavior="Fails validation",
                required_tools=[]
            )
        ]
        
        val_res = validate_scenarios(bad_scenarios, spec)
        self.assertFalse(val_res["is_valid"], "Validator should flag invalid categories/capabilities")
        self.assertTrue(val_res["errors_count"] >= 3, f"Expected at least 3 errors, got {val_res['errors_count']}")
        
        errs = {e["field"] for e in val_res["errors"]}
        self.assertIn("category", errs)
        self.assertIn("required_tools", errs)
        self.assertIn("capability_id", errs)

    async def test_coverage_gap_reporting(self):
        """Verify coverage reports calculate correct statistics and expose gaps."""
        spec = await analyze_agent(self.customer_support_path)
        
        # Intentionally create scenarios that only test one capability: CUSTOMER_LOOKUP
        scenarios = [
            ScenarioDefinition(
                scenario_id="SC-NOR-1",
                capability_id="CUSTOMER_LOOKUP",
                category="NORMAL",
                description="Verify profile tracking works",
                input={"customer_id": "SARAH_C"},
                expected_behavior="Resolves details",
                required_tools=["get_customer"]
            ),
            ScenarioDefinition(
                scenario_id="SC-EDG-1",
                capability_id="CUSTOMER_LOOKUP",
                category="EDGE_CASE",
                description="Check empty client id",
                input={"customer_id": ""},
                expected_behavior="Graceful error",
                required_tools=["get_customer"]
            )
        ]
        
        report = calculate_coverage(spec, scenarios)
        
        # Assertions
        self.assertTrue(report.capability_coverage < 100.0, "Should have low capability coverage since only one is tested")
        self.assertIn("REFUND_TRANSACTION", report.untested_capabilities)
        self.assertIn("ORDER_CANCELLATION", report.untested_capabilities)
        
        # Tools: get_customer is exercised, refund_order/cancel_order should be untested
        self.assertIn("refund_order", report.untested_tools)
        self.assertIn("cancel_order", report.untested_tools)
        self.assertNotIn("get_customer", report.untested_tools)

        # Category coverage: 2 out of 12 categories are covered
        expected_cat_cov = round((2 / 12) * 100.0, 1)
        self.assertEqual(report.category_coverage, expected_cat_cov)
        self.assertIn("TIMEOUT", report.missing_categories)
        self.assertIn("PROMPT_INJECTION", report.missing_categories)

    async def test_library_serialization(self):
        """Test writing scenarios to and reading from JSON library on disk."""
        spec = await analyze_agent(self.customer_support_path)
        scenarios = await generate_scenarios(spec, count=3, run_critic=False)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_scenarios.json")
            
            # Save
            ScenarioLibrary.save_scenarios(scenarios, filepath)
            self.assertTrue(os.path.exists(filepath))
            
            # Load
            loaded = ScenarioLibrary.load_scenarios(filepath)
            self.assertEqual(len(loaded), len(scenarios))
            
            for original, loaded_sc in zip(scenarios, loaded):
                self.assertEqual(original.scenario_id, loaded_sc.scenario_id)
                self.assertEqual(original.capability_id, loaded_sc.capability_id)
                self.assertEqual(original.category, loaded_sc.category)
                self.assertEqual(original.expected_behavior, loaded_sc.expected_behavior)

if __name__ == "__main__":
    unittest.main()
