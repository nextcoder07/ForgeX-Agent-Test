"""
Acceptance Test Script verifying the complete Intake -> Scenario Fallback -> Sandbox Spec -> Execution gate.
"""

import sys
import os
import asyncio
import json
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.intake import AgentIntakePayload, RegisterSpecRequest
from app.core.intake.spec_reconstructor import process_agent_intake
from app.api.intake import register_normalized_spec
from app.api.scenarios import execute_scenario_generation_run
from app.models.scenario import ScenarioGenerationRequest
from app.services.store import store
from app.core.llm.gemini_provider import GeminiProvider


async def mock_generate_scenarios(self, evidence: dict, plan: dict) -> list:
    raise Exception("429 RESOURCE_EXHAUSTED: Daily request limit reached.")


async def mock_generate(self, system: str, user: str, temperature: float = 0.2, conversation_id=None, stage=None) -> str:
    raise Exception("429 RESOURCE_EXHAUSTED: GenerateRequestsPerDayPerProjectPerModel-FreeTier quota exceeded.")


# Apply patches globally to simulate total LLM outage
GeminiProvider.generate_scenarios = mock_generate_scenarios
GeminiProvider.generate = mock_generate


async def run_acceptance_test():
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test-agents", "09-news-summarizer-agent"))
    if not os.path.exists(agent_dir):
        agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "500-AI-Agents-Projects", "agents", "06-news-summarizer-agent"))

    files = {}
    for root, _, fnames in os.walk(agent_dir):
        for f in fnames:
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                rel = os.path.relpath(p, agent_dir).replace(os.sep, "/")
                files[rel] = fp.read()

    payload = AgentIntakePayload(
        files=files,
        input_type="folder",
        agent_name_hint="News-summary-acceptance"
    )

    llm = GeminiProvider()

    print("[TEST] 1. Executing Intake (Failing Gemini)...")
    result = await process_agent_intake(payload, llm)
    print(f"   -> Intake Status: {result.analysis_status} (Confidence: {result.confidence_score}%)")
    assert result.analysis_status == "PARTIAL", "Should fall back to partial on LLM failure"

    # Save details
    reg_req = RegisterSpecRequest(
        normalized_spec=result.normalized_spec,
        display_name="News-summary-acceptance",
        artifact=result.artifact,
        source_files=files
    )

    print("\n[TEST] 2. Registering Agent & Behavior Profile & Sandbox Spec...")
    agent_rec = await register_normalized_spec(reg_req)
    
    # Verify registration status returned and saved
    reg_status = agent_rec.runtime_manifest.get("registration_status")
    print(f"   -> Registration Status: {json.dumps(reg_status)}")
    assert reg_status is not None
    assert reg_status["agent_status"] == "SUCCESS"
    assert reg_status["sandbox_spec_status"] == "SUCCESS"

    # Verify Sandbox Spec
    sandbox_spec = store.get_sandbox_spec(agent_rec.id) or next((s for s in store.list_sandbox_specs() if s.agent_id == agent_rec.id), None)
    print(f"   -> Sandbox Spec found: {sandbox_spec is not None}")
    assert sandbox_spec is not None
    print(f"   -> Sandbox Status: {sandbox_spec.status} (Blockers: {sandbox_spec.blockers})")
    print(f"   -> Sandbox Language: {sandbox_spec.runtime.get('language')}")
    assert sandbox_spec.runtime.get("language") == "python"

    # 3. Scenario Generation with total Gemini failure
    print("\n[TEST] 3. Triggering Scenario Generation (Gemini Quota Failure)...")
    gen_req = ScenarioGenerationRequest(
        agent_id=agent_rec.id,
        target_count=8
    )
    
    # We call execute_scenario_generation_run. Under the hood, LLM calls fail and fall back to deterministic scenarios
    run_result = await execute_scenario_generation_run(gen_req)
    print(f"   -> Run Status: {run_result.status}")
    print(f"   -> Generation Method: {run_result.generation_method}")
    print(f"   -> AI Status: {run_result.ai_status}")
    print(f"   -> Failure Reason: {run_result.failure_reason}")
    print(f"   -> Generated Scenarios: {run_result.generated_count}")
    print(f"   -> Ready Scenarios: {run_result.ready_count}")

    assert run_result.status == "PARTIAL", "Should report status as PARTIAL when falling back to deterministic generation"
    assert run_result.generation_method == "deterministic", "Should use deterministic generation fallback"
    assert run_result.generated_count >= 8, "Should generate at least 8 fallback scenarios"
    assert run_result.ready_count > 0, "At least one generated scenario should be READY"

    print("\n" + "=" * 60)
    print("ACCEPTANCE TESTS PASSED - ALL 10 BOTTLENECK CRITERIA MET!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_acceptance_test())
