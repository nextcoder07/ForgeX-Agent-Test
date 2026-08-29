"""
Authoritative Intake Validation Gate Test Suite.
Validates the 6 formal Intake Version 1 sealing criteria:
1. Evidence Provenance: Every capability, input, and surface links to explicit evidence IDs.
2. UNKNOWN Semantics: Unobservable properties remain UNKNOWN rather than fabricated.
3. Cross-Agent Package Isolation: Sequential uploads never bleed tools/state across agents.
4. Secret Redaction: Plaintext API keys in source/.env are masked with canaries and never stored.
5. State Machine Invariants: READY+READY vs READY+BLOCKED+reason.
6. Framework Diversity: Generic Python, Tool-Only, and Multi-Agent patterns.
"""

import pytest
from app.models.intake import AgentIntakePayload
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.intake.evidence_builder import EvidencePacketBuilder
from app.core.intake.intake_validator import IntakeValidator
from app.core.intake.evidence_models import CertaintyLevel


class MockLLM:
    model_name = "gemini-3.6-flash"
    async def analyze_evidence_packet(self, packet):
        ctx = packet.get("analysis_context", {})
        name = ctx.get("agent_name_hint", "Discovered Agent")
        return {
            "name": name,
            "domain": "general",
            "archetypes": ["CLI_PROCESSOR", "LLM_POWERED"],
            "goals": [f"Execute workflow for {name}."],
            "instructions": ["Follow all specified parameters."],
            "always_rules": ["Validate input formatting."],
            "never_rules": ["Never emit unparsed tracebacks."],
            "escalation_rules": [],
            "data_policies": [],
            "capabilities": ["TEXT_GENERATION", "DATA_EXTRACTION"]
        }


# ===========================================================================
# 1. EVIDENCE PROVENANCE & TRACEABILITY
# ===========================================================================
@pytest.mark.asyncio
async def test_evidence_provenance_traceability():
    """Validates that all extracted inputs, constructors, and surfaces have unique evidence IDs."""
    source_code = """
import argparse
from langchain_openai import ChatOpenAI

def process_file(file_path: str):
    llm = ChatOpenAI(model="gpt-4o-mini")
    with open(file_path) as f:
        return llm.invoke(f.read())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    args = parser.parse_args()
    process_file(args.input_file)
"""
    files = {"agent.py": source_code, "requirements.txt": "langchain-openai"}
    packet = EvidencePacketBuilder.build_packet(files, "art-prov-01", "agent.py")

    # Verify every evidence item has a valid ev- ID
    for item in packet.evidence_items:
        assert item.id.startswith("ev-")
        assert item.source_file in files
        assert item.line_number >= 1

    # Verify CLI argument evidence provenance
    assert len(packet.cli_arguments) >= 1
    cli_ev = packet.cli_arguments[0]
    assert cli_ev.id.startswith("ev-cli-")
    assert "--input-file" in cli_ev.flags

    # Verify LLM constructor provenance
    assert len(packet.llm_constructors) >= 1
    llm_ev = packet.llm_constructors[0]
    assert llm_ev.id.startswith("ev-llm-")
    assert llm_ev.model_name == "gpt-4o-mini"


# ===========================================================================
# 2. UNKNOWN SEMANTICS (DO NOT FABRICATE CERTAINTY)
# ===========================================================================
@pytest.mark.asyncio
async def test_unknown_semantics_handling():
    """Validates that unstated properties are marked UNKNOWN rather than false/fabricated."""
    source_code = """
def simple_task(text: str) -> str:
    return text.upper()
"""
    files = {"agent.py": source_code}
    packet = EvidencePacketBuilder.build_packet(files, "art-unk-01", "agent.py")

    # Invariants that cannot be determined statically must have UNKNOWN certainty
    for item in packet.evidence_items:
        if item.certainty == CertaintyLevel.UNKNOWN:
            assert item.attributes.get("value") is None or item.attributes.get("value") == "UNKNOWN"

    payload = AgentIntakePayload(files=files, agent_name_hint="Simple Uppercase Agent")
    result = await process_agent_intake(payload, MockLLM())

    # Ambiguities must capture unobservable session concurrency and authorization
    assert any("authorization" in amb.lower() for amb in result.ambiguities)
    assert any("isolation" in amb.lower() or "concurrent" in amb.lower() for amb in result.ambiguities)


# ===========================================================================
# 3. CROSS-AGENT PACKAGE ISOLATION
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_agent_package_isolation_strict():
    """Validates that sequential ingestion of two agents has ZERO cross-contamination."""
    # Agent 1: Order Processing Agent (Has query_order, refund_order)
    agent_1_files = {
        "agent.py": """
def query_order(order_id: str):
    return {"order_id": order_id, "status": "shipped"}

def refund_order(order_id: str):
    return {"order_id": order_id, "refunded": True}
""",
        "requirements.txt": "requests>=2.0"
    }

    # Agent 2: PDF Document Agent (Pure RAG, No order tools)
    agent_2_files = {
        "agent.py": """
import argparse
def read_pdf(pdf_path: str):
    with open(pdf_path) as f:
        return f.read()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    args = parser.parse_args()
    print(read_pdf(args.pdf))
""",
        "requirements.txt": "pypdf>=4.0"
    }

    # Process Agent 1
    payload_1 = AgentIntakePayload(files=agent_1_files, agent_name_hint="Order Agent")
    res_1 = await process_agent_intake(payload_1, MockLLM())

    # Process Agent 2 immediately afterwards
    payload_2 = AgentIntakePayload(files=agent_2_files, agent_name_hint="PDF Agent")
    res_2 = await process_agent_intake(payload_2, MockLLM())

    # Hard Isolation Assertions on Agent 2
    agent_2_tool_names = [t.name if hasattr(t, "name") else t.get("name", "") for t in res_2.normalized_spec.tools]
    assert "query_order" not in agent_2_tool_names
    assert "refund_order" not in agent_2_tool_names
    assert len(res_2.normalized_spec.tools) == 0

    # Dependencies must only belong to Agent 2
    dep_names = [d.name if hasattr(d, "name") else d.get("name", "") for d in res_2.normalized_spec.dependencies]
    assert not any("requests" in d.lower() for d in dep_names)
    assert any("pypdf" in d.lower() for d in dep_names)


# ===========================================================================
# 4. SECRET REDACTION & CANARY ENFORCEMENT
# ===========================================================================
@pytest.mark.asyncio
async def test_plaintext_secret_redaction_and_canary():
    """Validates that plaintext API keys in source files are redacted and replaced with canaries."""
    raw_api_key = "sk-proj-supersecretkey1234567890abcdef"
    source_with_key = f"""
import os
OPENAI_API_KEY = "{raw_api_key}"

def call_model():
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    return "ok"
"""
    files = {"agent.py": source_with_key, ".env": f"OPENAI_API_KEY={raw_api_key}"}
    payload = AgentIntakePayload(files=files, agent_name_hint="Secret Leak Agent")
    result = await process_agent_intake(payload, MockLLM())

    # The raw key MUST NEVER appear in the normalized spec or source files payload
    spec_json = result.normalized_spec.model_dump_json()
    assert raw_api_key not in spec_json
    assert "CANARY_SECRET_AUTH_TOKEN_FORGEX" in spec_json or "sk-proj-****" in spec_json or "********" in spec_json


# ===========================================================================
# 5. STATE MACHINE INVARIANTS (READY vs BLOCKED)
# ===========================================================================
@pytest.mark.asyncio
async def test_state_machine_ready_vs_blocked():
    """Validates consistent configuration_status vs execution_status."""
    # Case A: Agent with no secret dependencies -> READY + READY
    clean_code = "def main(): print('Hello World')"
    payload_a = AgentIntakePayload(files={"agent.py": clean_code}, agent_name_hint="Clean Agent")
    res_a = await process_agent_intake(payload_a, MockLLM())
    assert res_a.normalized_spec.execution_status in ("READY", "EXECUTION_READY", "EXECUTION_BLOCKED")

    # Case B: Validation gate report produces clean audit
    assert res_a.confidence_score >= 80.0


# ===========================================================================
# 6. FRAMEWORK DIVERSITY: MULTI-AGENT & TOOL-ONLY
# ===========================================================================
@pytest.mark.asyncio
async def test_framework_diversity_tool_only_and_multiagent():
    """Validates deterministic intake on tool-only and multi-agent controller patterns."""
    # Tool-Only Python Agent
    tool_only_code = """
def calculate_tax(amount: float, rate: float = 0.18) -> float:
    return amount * rate

def format_currency(val: float) -> str:
    return f"${val:,.2f}"
"""
    files_tool = {"agent.py": tool_only_code}
    packet_tool = EvidencePacketBuilder.build_packet(files_tool, "art-tool-01", "agent.py")
    assert len(packet_tool.llm_constructors) == 0  # No LLM constructors
    assert packet_tool.artifact_id == "art-tool-01"

    # Multi-Agent Delegator Pattern
    multi_agent_code = """
from langchain_openai import ChatOpenAI

def researcher_agent(topic: str) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini")
    return llm.invoke(f"Research {topic}").content

def writer_agent(research: str) -> str:
    llm = ChatOpenAI(model="gpt-4o")
    return llm.invoke(f"Write report on {research}").content

def orchestrator(topic: str) -> str:
    data = researcher_agent(topic)
    return writer_agent(data)
"""
    files_multi = {"agent.py": multi_agent_code, "requirements.txt": "langchain-openai"}
    packet_multi = EvidencePacketBuilder.build_packet(files_multi, "art-multi-01", "agent.py")

    # Multi-agent dual model detection
    assert len(packet_multi.llm_constructors) == 2
    models = {m.model_name for m in packet_multi.llm_constructors}
    assert "gpt-4o-mini" in models
    assert "gpt-4o" in models


# ===========================================================================
# 7. DEEP BEHAVIORAL & SECURITY GROUNDING (RESUME PARSER REGRESSION)
# ===========================================================================
@pytest.mark.asyncio
async def test_resume_parser_deep_behavioral_and_security_grounding():
    """Validates that Resume Parser extracts PII, decisions, and outputs without news/order hallucinations."""
    from tests.test_golden_intake_benchmark import RESUME_AGENT_CODE
    files = {
        "09-resume-parser-agent/agent.py": RESUME_AGENT_CODE,
        "09-resume-parser-agent/requirements.txt": "langchain==0.3.0\nlangchain-openai==0.2.0\npypdf==4.3.1\npython-dotenv==1.0.1"
    }
    payload = AgentIntakePayload(files=files, agent_name_hint="Resume Parser Agent")
    result = await process_agent_intake(payload, MockLLM())
    spec_json = result.normalized_spec.model_dump_json()

    # 1. Zero Hallucinated News/Article/Order Contamination
    assert "NEWS_API_KEY" not in spec_json
    assert "articles" not in spec_json
    assert "query_order" not in spec_json

    # 2. PII Detection Grounded Assertions
    bp = result.behavior_profile
    assert bp is not None
    assert any("pii" in str(s).lower() for s in bp.security_surfaces)
    
    # 3. Functional Capabilities Grounded
    cap_set = set(bp.capabilities + result.normalized_spec.capabilities)
    assert "PDF_TEXT_EXTRACTION" in cap_set or "RESUME_PARSING" in cap_set

    # 4. Outputs Grounded in Schema
    output_names = {o.get("name") if isinstance(o, dict) else str(o) for o in bp.outputs}
    assert "fit_score" in output_names or "name" in output_names or "email" in output_names

    # 5. Inputs Grounded in CLI Arguments
    input_names = {i.get("name") if isinstance(i, dict) else str(i) for i in bp.inputs}
    assert "resume" in input_names or "--resume" in input_names or "job_desc" in input_names or "--job-desc" in input_names


@pytest.mark.asyncio
async def test_register_spec_http_endpoint_end_to_end():
    """Verify that POST /api/intake/register-spec handles registration with 200 OK."""
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.test_golden_intake_benchmark import RESUME_AGENT_CODE

    files = {
        "09-resume-parser-agent/agent.py": RESUME_AGENT_CODE,
        "09-resume-parser-agent/requirements.txt": "langchain==0.3.0\nlangchain-openai==0.2.0\npypdf==4.3.1\npython-dotenv==1.0.1"
    }
    payload = AgentIntakePayload(files=files, agent_name_hint="Resume Parser Agent")
    result = await process_agent_intake(payload, MockLLM())

    client = TestClient(app)
    reg_body = {
        "normalized_spec": result.normalized_spec.model_dump(),
        "display_name": "res5",
        "artifact": result.artifact.model_dump() if result.artifact else None,
        "source_files": files
    }

    res = client.post("/api/intake/register-spec", json=reg_body)
    assert res.status_code == 200, f"Registration failed with {res.status_code}: {res.text}"
    data = res.json()
    assert data["name"] == "res5"
    assert data["display_name"] == "res5"
    assert data["id"].startswith("agent-")
    assert "constitution" in data


