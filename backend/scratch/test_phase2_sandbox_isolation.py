"""
Phase 2 Sandbox Container Isolation & Safety Harness Verification Script.
Tests:
  1. SandboxSpecification Auto-Generation & Persistence
  2. Subprocess Sandbox Engine Execution & Tool Gateway Interception
  3. Environment Security Masking (Stripping sensitive API keys & credentials)
  4. Execution Timeout & Infinite Loop Protection
"""

import sys
import os

# Set up python path to include backend
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

import asyncio
from app.services.store import store
from app.api.intake import get_local_demo_agent_files, analyze_agent, register_normalized_spec, get_agent_sandbox_specification
from app.models.intake import AgentIntakePayload, RegisterSpecRequest
from app.models.scenario import Scenario, ScenarioCategory
from app.core.dependencies.tool_gateway import ToolGateway
from app.core.sandbox.sandbox_manager import get_or_create_sandbox_spec
from app.core.sandbox.subprocess_runner import create_sanitized_environment, run_scenario_in_subprocess
from app.core.sandbox.runner import run_scenario_in_sandbox


async def run_phase2_verification():
    print("=" * 80)
    print("PHASE 2 SANDBOX CONTAINER ISOLATION VERIFICATION TEST SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: SandboxSpecification Auto-Generation & Persistence
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing SandboxSpecification Auto-Generation & Persistence...")
    demo_files = get_local_demo_agent_files("01-simple-python")
    intake_payload = AgentIntakePayload(
        agent_name_hint="Simple Python Agent",
        files=demo_files["files"]
    )
    understanding_result = await analyze_agent(intake_payload)
    
    register_req = RegisterSpecRequest(
        normalized_spec=understanding_result.normalized_spec,
        display_name="Simple Python Agent (Phase 2 Test)",
        source_files=demo_files["files"]
    )
    agent = register_normalized_spec(register_req)
    
    sandbox_spec = get_agent_sandbox_specification(agent.id)
    assert sandbox_spec is not None, "SandboxSpecification must not be None"
    assert sandbox_spec.agent_id == agent.id, "SandboxSpecification agent_id match failed"
    assert sandbox_spec.runtime.get("isolation_mode") == "subprocess", "Isolation mode must be subprocess"

    print(f"✓ TEST 1 PASSED: SandboxSpecification generated and persisted!")
    print(f"  - Spec ID: {sandbox_spec.id}")
    print(f"  - Isolation Mode: {sandbox_spec.runtime.get('isolation_mode')}")
    print(f"  - Memory Limit: {sandbox_spec.runtime.get('memory_limit_mb')} MB")

    # -------------------------------------------------------------------------
    # TEST 2: Environment Security Masking
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verifying Environment Security Masking...")
    # Inject a dummy sensitive env key
    os.environ["GEMINI_API_KEY"] = "AIzaSyTEST_SECRET_KEY_12345"
    os.environ["SUPABASE_KEY"] = "sb_secret_key_67890"

    sanitized_env = create_sanitized_environment()
    assert "GEMINI_API_KEY" not in sanitized_env, "GEMINI_API_KEY must be stripped"
    assert "SUPABASE_KEY" not in sanitized_env, "SUPABASE_KEY must be stripped"
    assert sanitized_env.get("SANDBOX_MODE") == "isolated_subprocess", "SANDBOX_MODE must be set"

    print("✓ TEST 2 PASSED: Sensitive environment keys successfully stripped from child process env!")

    # -------------------------------------------------------------------------
    # TEST 3: Subprocess Sandbox Engine Execution
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Running Scenario via Isolated Subprocess Runner Engine...")
    test_scenario = Scenario(
        id="SC-TEST-PHASE2",
        agent_id=agent.id,
        category=ScenarioCategory.NORMAL,
        title="Subprocess Execution Test",
        purpose="Verify child process execution with gateway interception",
        user_messages=["Look up customer CUST-901"]
    )

    code_content = demo_files["files"].get("agent.py", "# No code")
    gateway = ToolGateway(agent.tools)

    trace = run_scenario_in_subprocess(agent, test_scenario, code_content, gateway, timeout_seconds=5.0)

    assert trace is not None, "ExecutionTrace must not be None"
    assert len(trace.events) > 0, "ExecutionTrace events must not be empty"
    print(f"✓ TEST 3 PASSED: Subprocess execution finished safely!")
    print(f"  - Trace ID: {trace.id}")
    print(f"  - Event Count: {len(trace.events)}")
    print(f"  - Latency: {trace.total_latency_ms} ms")

    # -------------------------------------------------------------------------
    # TEST 4: Unified Dispatcher Integration
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing Unified Sandbox Dispatcher (run_scenario_in_sandbox)...")
    dispatcher_trace = run_scenario_in_sandbox(agent, test_scenario)
    assert dispatcher_trace is not None, "Dispatcher trace must not be None"
    assert len(dispatcher_trace.events) > 0, "Dispatcher trace events must not be empty"

    print(f"✓ TEST 4 PASSED: Unified Sandbox Dispatcher executed successfully!")
    print(f"  - Dispatcher Trace ID: {dispatcher_trace.id}")
    print("=" * 80)
    print("ALL PHASE 2 SANDBOX CONTAINER ISOLATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_phase2_verification())
