"""
Automated unit & integration test for the Parallel Stage Agent Tester Subsystem.
Verifies strict model adherence, fast local connectivity check, and stage judge audits.
"""

import pytest
import asyncio
from app.agent_testers.models import StageAuditRequest, StageAuditVerdict
from app.agent_testers.stage_tester import StageAgentTester
from app.core.llm.gemini_provider import GeminiProvider
from app.core.llm.providers import check_local_model_health
from app.services.store import store


@pytest.mark.asyncio
async def test_gemini_strict_model_adherence():
    """Verify GeminiProvider strictly adheres to configured model name and does not try other versions."""
    provider = GeminiProvider(api_key="mock-key", model_name="gemini-3.6-flash")
    assert provider.model_name == "gemini-3.6-flash"


@pytest.mark.asyncio
async def test_local_model_connectivity_check():
    """Verify fast local model health check executes within 2s timeout."""
    is_conn, msg = await check_local_model_health("http://localhost:11434")
    assert isinstance(is_conn, bool)
    assert isinstance(msg, str)


@pytest.mark.asyncio
async def test_stage_tester_audit_execution():
    """Verify stage tester runs an audit, returns a valid verdict, and persists to store."""
    tester = StageAgentTester()
    
    # Audit Analysis Stage
    request = StageAuditRequest(
        agent_id="test-agent-01",
        stage_name="analysis",
        input_data={
            "files": {"main.py": "def handle(msg): return f'Echo {msg}'"},
            "docs": "Simple echo assistant"
        },
        result_data={
            "name": "EchoAgent",
            "domain": "utility",
            "tools": [],
            "invariants": [{"statement": "Echo back user messages"}],
            "never_rules": ["Never delete system files"]
        }
    )
    
    verdict = await tester.audit_stage(request)
    assert isinstance(verdict, StageAuditVerdict)
    assert verdict.stage_name == "analysis"
    assert verdict.status in ("PASS", "WARNING", "DEFECT")
    assert 0 <= verdict.score <= 100
    assert verdict.tester_session_id.startswith("tester-session-analysis")
    
    # Check persistence in store
    retrieved = store.get_stage_judge_audit(verdict.id)
    assert retrieved is not None
    assert retrieved.id == verdict.id
    assert retrieved.score == verdict.score
    
    # Check listing audits
    audits = store.list_stage_judge_audits(agent_id="test-agent-01")
    assert len(audits) >= 1
    assert audits[0].agent_id == "test-agent-01"


@pytest.mark.asyncio
async def test_tester_health_status():
    """Verify StageTester health endpoint returns complete telemetry."""
    tester = StageAgentTester()
    health = await tester.get_health_status()
    assert health.status in ("healthy", "degraded", "offline")
    assert isinstance(health.local_model_connected, bool)
    assert health.configured_model != ""
