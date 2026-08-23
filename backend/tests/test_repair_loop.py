"""
Deterministic Unit Test for Fix My Agent Repair Loop Lifecycle.
Tests iteration advancement, termination conditions, and exception handling without external LLM dependencies.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

from app.models.agent import AgentRecord, AgentConstitution
from app.models.evaluation import ReliabilityScorecard
from app.models.failure import RunVerdict
from app.models.repair import RepairSession, RepairStatus
from app.services.store import store
from app.core.repair.repair_orchestrator import RepairOrchestrator


class TestRepairLoop(unittest.TestCase):
    def setUp(self):
        # Create test agent
        self.agent_id = "test-repair-agent-001"
        self.agent = AgentRecord(
            id=self.agent_id,
            name="Test Repair Agent",
            description="Agent for repair loop testing",
            domain="testing",
            system_prompt="Initial system prompt",
            tools=[],
            dependencies=[],
            constitution=AgentConstitution(
                goals=["Test goal"],
                never_rules=["Never rule"],
                always_rules=["Always rule"],
                escalation_rules=[],
                data_policies=[]
            ),
            version_label="v1.0-test",
            source_files={"agent.py": "def refund_order(amount):\n    return amount\n"},
            created_at="2026-08-23T00:00:00Z"
        )
        store.save_agent(self.agent)

        # Create baseline scorecard with failures
        self.baseline_scorecard = ReliabilityScorecard(
            evaluation_id="eval-baseline-test",
            agent_id=self.agent_id,
            agent_name=self.agent.name,
            agent_version="v1.0-test",
            correctness=50.0,
            safety=50.0,
            robustness=50.0,
            tool_discipline=50.0,
            goal_adherence=50.0,
            composite=50.0,
            safety_axis=50.0,
            capability_axis=50.0,
            total_scenarios=4,
            passed=2,
            failed=2,
            critical_failures=2
        )
        store.save_scorecard(self.baseline_scorecard)

        # Create session
        self.session = RepairOrchestrator.get_or_create_session(self.agent_id)

    @patch("app.core.repair.repair_orchestrator.get_provider")
    @patch("app.core.repair.repair_orchestrator.run_scenario_in_sandbox")
    @patch("app.core.repair.repair_orchestrator.evaluate_trace_suite")
    @patch("app.core.repair.repair_orchestrator.compute_reliability_scorecard")
    def test_repair_loop_succeeds_on_iteration_3(
        self, mock_compute_scorecard, mock_eval_suite, mock_sandbox, mock_get_provider
    ):
        """Test loop advances through iteration 1, 2, and succeeds on iteration 3."""
        mock_get_provider.return_value = MagicMock()
        mock_sandbox.return_value = MagicMock(id="tr-test")
        mock_eval_suite.return_value = []

        # Return non-repaired scorecards for iter 1 and 2, repaired scorecard for iter 3
        sc_iter1 = ReliabilityScorecard(
            evaluation_id="eval-iter-1", agent_id=self.agent_id, agent_name=self.agent.name,
            agent_version="v1.0-test-repair-1", correctness=60.0, safety=60.0, robustness=60.0,
            tool_discipline=60.0, goal_adherence=60.0, composite=60.0, safety_axis=60.0, capability_axis=60.0,
            total_scenarios=4, passed=3, failed=1, critical_failures=1
        )
        sc_iter2 = ReliabilityScorecard(
            evaluation_id="eval-iter-2", agent_id=self.agent_id, agent_name=self.agent.name,
            agent_version="v1.0-test-repair-2", correctness=75.0, safety=75.0, robustness=75.0,
            tool_discipline=75.0, goal_adherence=75.0, composite=75.0, safety_axis=75.0, capability_axis=75.0,
            total_scenarios=4, passed=3, failed=1, critical_failures=1
        )
        sc_iter3 = ReliabilityScorecard(
            evaluation_id="eval-iter-3", agent_id=self.agent_id, agent_name=self.agent.name,
            agent_version="v1.0-test-repair-3", correctness=95.0, safety=95.0, robustness=95.0,
            tool_discipline=95.0, goal_adherence=95.0, composite=95.0, safety_axis=95.0, capability_axis=95.0,
            total_scenarios=4, passed=4, failed=0, critical_failures=0
        )

        mock_compute_scorecard.side_effect = [sc_iter1, sc_iter2, sc_iter3]

        final_session = RepairOrchestrator.start_repair_loop(self.session.id, max_iterations=3)

        self.assertEqual(len(final_session.iterations), 3)
        self.assertEqual([i.iteration for i in final_session.iterations], [1, 2, 3])
        self.assertEqual(final_session.status, RepairStatus.COMPLETED_FIXED)
        self.assertEqual(final_session.final_verdict, "REPAIRED")
        self.assertEqual(final_session.final_status, "Fixed")

    @patch("app.core.repair.repair_orchestrator.get_provider")
    @patch("app.core.repair.repair_orchestrator.run_scenario_in_sandbox")
    @patch("app.core.repair.repair_orchestrator.evaluate_trace_suite")
    @patch("app.core.repair.repair_orchestrator.compute_reliability_scorecard")
    def test_repair_loop_reaches_max_iterations(
        self, mock_compute_scorecard, mock_eval_suite, mock_sandbox, mock_get_provider
    ):
        """Test loop advances to max_iterations (3) when repairs do not fully fix the agent."""
        mock_get_provider.return_value = MagicMock()
        mock_sandbox.return_value = MagicMock(id="tr-test")
        mock_eval_suite.return_value = []

        sc_failing = ReliabilityScorecard(
            evaluation_id="eval-iter-fail", agent_id=self.agent_id, agent_name=self.agent.name,
            agent_version="v1.0-test-repair", correctness=50.0, safety=50.0, robustness=50.0,
            tool_discipline=50.0, goal_adherence=50.0, composite=50.0, safety_axis=50.0, capability_axis=50.0,
            total_scenarios=4, passed=2, failed=2, critical_failures=2
        )

        mock_compute_scorecard.return_value = sc_failing

        final_session = RepairOrchestrator.start_repair_loop(self.session.id, max_iterations=3)

        self.assertEqual(len(final_session.iterations), 3)
        self.assertEqual([i.iteration for i in final_session.iterations], [1, 2, 3])
        self.assertIn(final_session.status, [RepairStatus.MAX_ITERATIONS_REACHED, RepairStatus.COMPLETED_PARTIAL])
        self.assertIn(final_session.final_verdict, ["NOT_REPAIRED", "PARTIALLY_REPAIRED"])

    @patch("app.core.repair.repair_orchestrator.get_provider")
    @patch("app.core.repair.fixing_agent.FixingAgent.analyze_and_repair")
    def test_repair_loop_handles_exception_gracefully(self, mock_analyze_and_repair, mock_get_provider):
        """Test that unhandled exception in worker sets status FAILED and populates error_message."""
        mock_get_provider.return_value = MagicMock()
        mock_analyze_and_repair.side_effect = RuntimeError("Simulated unexpected repair engine failure")

        final_session = RepairOrchestrator.start_repair_loop(self.session.id, max_iterations=3)

        self.assertEqual(final_session.status, RepairStatus.FAILED)
        self.assertEqual(final_session.final_verdict, "FAILED")
        self.assertIn("RuntimeError", final_session.error_message)
        self.assertIn("Simulated unexpected repair engine failure", final_session.error_message)


if __name__ == "__main__":
    unittest.main()
