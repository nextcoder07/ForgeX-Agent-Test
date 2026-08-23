"""Unit tests for Execution Stage Evidence-Collection System covering 18 mandatory requirements."""
import unittest
import datetime as dt
from typing import Any, Dict, List

from app.models.agent import AgentRecord, ToolDefinition, ToolRisk, DependencyDefinition, AgentConstitution
from app.models.scenario import Scenario, ScenarioCategory, ScenarioAssertion
from app.models.execution import (
    ExecutionLifecycleState, ExecutionFailureState, VariableSource,
    ExecutionPreflight, ExecutionAction, ObservationSummary, ExecutionSession,
    PreExecutionSnapshot, PostExecutionSnapshot, EvidencePackage
)
from app.core.execution.preflight import run_scenario_preflight
from app.core.sandbox.sandbox_manager import SandboxManager
from app.core.sandbox.runner import run_scenario_in_sandbox
from app.core.execution.side_effect_detector import SideEffectDetector
from app.core.execution.interceptors.tool_interceptor import ToolInterceptor
from app.core.execution.interceptors.network_interceptor import NetworkInterceptor
from app.core.execution.interceptors.filesystem_interceptor import FilesystemInterceptor
from app.core.execution.interceptors.database_interceptor import DatabaseInterceptor
from app.core.execution.interceptors.runtime_interceptor import RuntimeInterceptor
from app.services.store import store


class TestExecutionEvidenceCollection(unittest.TestCase):
    def setUp(self):
        self.agent = AgentRecord(
            id="test-evidence-agent",
            name="Evidence Agent",
            display_name="Evidence Agent",
            description="Agent for testing evidence collection",
            created_at=dt.datetime.utcnow().isoformat(),
            domain="customer_support",
            system_prompt="Process customer requests safely.",
            tools=[
                ToolDefinition(name="get_order", description="Query order", canonical_capability="ORDER_LOOKUP", risk=ToolRisk.LOW),
                ToolDefinition(name="refund_order", description="Refund order", canonical_capability="REFUND_TRANSACTION", risk=ToolRisk.CRITICAL, is_destructive=True, max_amount=10000.0)
            ],
            dependencies=[
                DependencyDefinition(id="dep-1", name="OPENAI_API_KEY", type="api_key", detected_from="MANUAL")
            ],
            constitution=AgentConstitution(
                never_rules=["Never issue refunds above ₹10,000"],
                always_rules=["Verify order exists first"]
            )
        )
        store.save_agent(self.agent)

    # 1. Successful preflight
    def test_1_successful_preflight(self):
        scenario = Scenario(
            id="SC-01", agent_id=self.agent.id, category=ScenarioCategory.NORMAL,
            title="Normal Query", purpose="Happy path test",
            user_messages=["Track order ORD-101"]
        )
        res = run_scenario_preflight(scenario, self.agent, provided_variables={"OPENAI_API_KEY": "sk-123"})
        self.assertTrue(res.is_ready)
        self.assertEqual(res.status, "READY")

    # 2. Missing credential
    def test_2_missing_credential_blocks_preflight(self):
        scenario = Scenario(
            id="SC-02", agent_id=self.agent.id, category=ScenarioCategory.NORMAL,
            title="Missing Credential", purpose="Test missing key",
            user_messages=["Track order ORD-101"]
        )
        res = run_scenario_preflight(scenario, self.agent)
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.preflight_record.credential_status, "BLOCKED")

    # 3. Safe default variable
    def test_3_safe_default_variable_resolution(self):
        scenario = Scenario(
            id="SC-03", agent_id=self.agent.id, category=ScenarioCategory.NORMAL,
            title="Safe Default Test", purpose="Test log level default",
            user_messages=["Track order ORD-101"]
        )
        res = run_scenario_preflight(scenario, self.agent, provided_variables={"OPENAI_API_KEY": "sk-123"})
        vars_list = res.preflight_record.resolved_variables
        self.assertTrue(any(v.name == "LOG_LEVEL" and v.source == VariableSource.SAFE_DEFAULT for v in vars_list))

    # 4. Sandbox construction
    def test_4_sandbox_construction_logs_build_events(self):
        mgr = SandboxManager()
        sb = mgr.create_sandbox(self.agent.id, "SC-04")
        mgr.install_dependencies(sb, self.agent)
        mgr.inject_allowed_environment(sb, allowed_env={}, secrets={"KEY": "val"})
        logs = "\n".join(sb.logs)
        self.assertIn("[SANDBOX_BUILD_STARTED]", logs)
        self.assertIn("[SANDBOX_READY]", logs)
        mgr.destroy_sandbox(sb.sandbox_id)

    # 5. Tool call allowed
    def test_5_tool_call_allowed_interceptor(self):
        act = ToolInterceptor.intercept_call(
            session_id="s1", sequence=1, tool_name="get_order",
            arguments={"order_id": "ORD-1"}, routing_decision="ALLOW",
            result={"status": "active"}, side_effect_occurred=False
        )
        self.assertEqual(act.action_type, "TOOL_CALL")
        self.assertEqual(act.policy_decision["decision"], "ALLOW")
        self.assertTrue(act.execution_result["executed"])

    # 6. Tool call blocked
    def test_6_tool_call_blocked_interceptor(self):
        act = ToolInterceptor.intercept_call(
            session_id="s1", sequence=2, tool_name="refund_order",
            arguments={"amount": 50000.0}, routing_decision="BLOCK",
            policy_reason="Refund limit exceeded", result_status="BLOCKED_POLICY",
            side_effect_occurred=False
        )
        self.assertEqual(act.policy_decision["decision"], "BLOCK")
        self.assertFalse(act.execution_result["executed"])

    # 7. Filesystem side effect
    def test_7_filesystem_side_effect_interceptor(self):
        act = FilesystemInterceptor.intercept_operation(
            session_id="s1", sequence=3, operation="WRITE",
            path="/workspace/output.json", content_length=120,
            allowed=True, side_effect_occurred=True
        )
        self.assertTrue(act.side_effect["detected"])
        self.assertEqual(act.side_effect["details"]["path"], "/workspace/output.json")

    # 8. Database side effect
    def test_8_database_side_effect_interceptor(self):
        act = DatabaseInterceptor.intercept_operation(
            session_id="s1", sequence=4, resource_type="ORDER",
            resource_id="ORD-1", operation="UPDATE",
            before_val="PENDING", after_val="SHIPPED", allowed=True
        )
        self.assertTrue(act.side_effect["detected"])
        self.assertEqual(act.side_effect["details"]["before"], "PENDING")

    # 9. Network request blocked
    def test_9_network_request_blocked(self):
        act = NetworkInterceptor.intercept_request(
            session_id="s1", sequence=5, host="unauthorized-site.com",
            method="POST", path="/exfiltrate", allowed=False, policy_reason="Domain not in allowlist"
        )
        self.assertEqual(act.policy_decision["decision"], "BLOCK")
        self.assertFalse(act.execution_result["executed"])

    # 10. Network request allowed
    def test_10_network_request_allowed(self):
        act = NetworkInterceptor.intercept_request(
            session_id="s1", sequence=6, host="api.openai.com",
            method="POST", path="/v1/chat/completions", allowed=True, response_status=200
        )
        self.assertEqual(act.policy_decision["decision"], "ALLOW")
        self.assertEqual(act.execution_result["response_status"], 200)

    # 11. Runtime error
    def test_11_runtime_error_interceptor(self):
        act = RuntimeInterceptor.intercept_event(
            session_id="s1", sequence=7, event_kind="UNCATCH_EXCEPTION",
            details={"error": "ZeroDivisionError"}, allowed=True
        )
        self.assertEqual(act.execution_result["status"], "ERROR")

    # 12. Timeout
    def test_12_timeout_interceptor(self):
        act = RuntimeInterceptor.intercept_event(
            session_id="s1", sequence=8, event_kind="TIMEOUT",
            details={"timeout_seconds": 15}, allowed=True
        )
        self.assertEqual(act.execution_result["status"], "TIMEOUT")

    # 13. Multiple actions sequence
    def test_13_multiple_actions_sequence(self):
        scenario = Scenario(
            id="SC-13", agent_id=self.agent.id, category=ScenarioCategory.NORMAL,
            title="Multi Action", purpose="Multi action test",
            user_messages=["Please track order ORD-4821"]
        )
        trace = run_scenario_in_sandbox(self.agent, scenario, provided_secrets={"TEST_AGENT_GEMINI_API_KEY": "dummy"})
        self.assertGreaterEqual(len(trace.events), 2)

    # 14. Pre/post snapshot difference
    def test_14_pre_post_snapshot_diff(self):
        pre = PreExecutionSnapshot(filesystem_state={"a.py": "v1"}, database_fixture_state={"ord": 1})
        post = PostExecutionSnapshot(filesystem_state={"a.py": "v1", "out.txt": "res"}, database_state={"ord": 2})
        diff = SideEffectDetector.detect_side_effects(pre, post, [])
        self.assertTrue(diff["side_effect_occurred"])
        self.assertIn("out.txt", diff["filesystem_changes"])
        self.assertEqual(len(diff["database_diffs"]), 1)

    # 15. Observation summary generation
    def test_15_observation_summary_generation(self):
        obs = ObservationSummary(
            action_count=5, tool_calls=2, llm_calls=1,
            blocked_actions=1, execution_duration_ms=150.0, exit_code=0
        )
        self.assertEqual(obs.action_count, 5)
        self.assertEqual(obs.blocked_actions, 1)

    # 16. Evidence sealing
    def test_16_evidence_sealing_package(self):
        obs = ObservationSummary(action_count=2, tool_calls=1)
        pkg = EvidencePackage(
            session_id="sess-99", scenario_id="sc-99", agent_version_id="v1.0",
            observation_summary=obs, trajectory_hash="sha256:abc123hash",
            sealing_timestamp=dt.datetime.utcnow().isoformat()
        )
        self.assertTrue(pkg.trajectory_hash.startswith("sha256:"))

    # 17. Retrieval through API/Store
    def test_17_retrieval_through_store(self):
        sess = ExecutionSession(
            id="sess-api-01", execution_run_id="run-01",
            agent_version_id="v1.0", scenario_id="sc-01", started_at=dt.datetime.utcnow().isoformat()
        )
        store.save_execution_session(sess)
        fetched = store.get_execution_session("sess-api-01")
        self.assertEqual(fetched.id, "sess-api-01")

    # 18. Ensure Execution NEVER produces PASS/FAIL
    def test_18_execution_never_produces_pass_fail(self):
        act = ToolInterceptor.intercept_call(
            session_id="s1", sequence=1, tool_name="refund_order",
            arguments={"amount": 50000.0}, routing_decision="BLOCK",
            policy_reason="Refund cap exceeded", result_status="BLOCKED_POLICY"
        )
        dict_repr = act.model_dump()
        # Verify no pass, fail, verdict, or reliability score inside action
        self.assertNotIn("passed", dict_repr)
        self.assertNotIn("failed", dict_repr)
        self.assertNotIn("verdict", dict_repr)
        self.assertNotIn("reliability_score", dict_repr)


if __name__ == "__main__":
    unittest.main()
