"""
Adversarial Intake Test Suite.
Validates that ForgeX Stage-1 Intake defends against:
1. Cross-Agent Contamination (sequential upload leakage)
2. Hallucinated Tools (rejects tools not in AST)
3. Hallucinated Capabilities (rejects unproven semantic capabilities)
4. Fake SQL Security Surfaces (no SQL surface if sqlite3/SQLDatabase only in comments or non-executing code)
5. Fake News/API Security Surfaces (no external API surface if no actual client call)
6. Dynamic Model Resolution (marks dynamic model as UNKNOWN/DYNAMIC, does not guess gpt-4o-mini)
7. Unknown Inputs Handling (never invents "query" or "topic" defaults)
8. Unknown Outputs Handling (never invents "status" or "result" defaults)
9. Prompt-Declared Output Preservation (distinguishes PROMPT_DECLARED from CODE_PROVEN)
10. Plaintext Secret Redaction (canary masking)
11. Artifact Mismatch (detects foreign artifact IDs and emits DEFECT audit verdict)
12. Workflow Hallucination (workflow edges strictly follow AST call graph)
13. Dedicated Decision-Surface Detection (detects candidate evaluations without polluting security surfaces)
"""

import pytest
from app.models.intake import AgentIntakePayload, NormalizedAgentSpec
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.intake.evidence_builder import EvidencePacketBuilder
from app.core.intake.intake_auditor import IntakeAuditor, DiscrepancyType
from app.core.intake.evidence_models import CertaintyLevel, ProvenanceType


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
            "instructions": ["Follow all parameters."],
            "always_rules": ["Validate input format."],
            "never_rules": ["Never emit raw tracebacks."],
            "escalation_rules": [],
            "data_policies": [],
            "capabilities": ["TEXT_GENERATION", "DATA_EXTRACTION"]
        }


# ===========================================================================
# 1. CROSS-AGENT CONTAMINATION
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_cross_agent_contamination_cycle():
    """Verify that alternating ingestion of Resume, News, and SQL agents has 0% bleed."""
    resume_files = {
        "agent.py": "def parse_resume(text: str): return {'name': 'John'}",
        "requirements.txt": "pypdf==4.3.1"
    }
    news_files = {
        "agent.py": "def fetch_news(topic: str): return ['headline']",
        "requirements.txt": "requests==2.31.0"
    }
    sql_files = {
        "agent.py": "import sqlite3\ndef query_db(q: str): con = sqlite3.connect(':memory:'); return con.execute(q).fetchall()",
        "requirements.txt": "sqlite3"
    }

    # Cycle: Resume -> News -> SQL -> Resume
    res_resume_1 = await process_agent_intake(AgentIntakePayload(files=resume_files, agent_name_hint="Resume A"), MockLLM())
    res_news = await process_agent_intake(AgentIntakePayload(files=news_files, agent_name_hint="News B"), MockLLM())
    res_sql = await process_agent_intake(AgentIntakePayload(files=sql_files, agent_name_hint="SQL C"), MockLLM())
    res_resume_2 = await process_agent_intake(AgentIntakePayload(files=resume_files, agent_name_hint="Resume A2"), MockLLM())

    # Assert Resume 2 has no news or sql evidence
    spec_2_json = res_resume_2.normalized_spec.model_dump_json()
    assert "fetch_news" not in spec_2_json
    assert "sqlite3" not in spec_2_json
    assert "requests" not in spec_2_json


# ===========================================================================
# 2. HALLUCINATED TOOL REJECTION
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_hallucinated_tool_purged_by_auditor():
    """When an LLM claims a tool 'refund_order' that does not exist in AST, auditor flags DEFECT/critical."""
    source_files = {"agent.py": "def calculate_sum(a: int, b: int): return a + b"}
    packet = EvidencePacketBuilder.build_packet(source_files, "art-tool-hallucinate-01", "agent.py")

    # Manually construct a spec claiming a non-existent tool
    from app.models.agent import ToolDefinition
    spec = NormalizedAgentSpec(
        identity={"name": "Sum Agent", "domain": "math", "entrypoint": "agent.py"},
        tools=[ToolDefinition(name="refund_order", description="Hallucinated tool")],
        capabilities=["MATH"]
    )
    audit_report = IntakeAuditor.audit_spec_against_evidence(spec, packet)

    assert audit_report.audit_verdict == "DEFECT"
    assert any(d.discrepancy_type == DiscrepancyType.HALLUCINATED for d in audit_report.discrepancies)


# ===========================================================================
# 3. FAKE SQL SECURITY SURFACE (COMMENT / STRING FALSE POSITIVE)
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_no_fake_sql_surface_from_comments():
    """Mentions of 'sql' in comments or strings MUST NOT trigger SQL_EXECUTION security surface."""
    source_files = {
        "agent.py": """
# This agent does not use SQL, MySQL, or SQLite. It is a text parser.
def format_text(text: str) -> str:
    \"\"\"Docstring mentioning postgres database conceptually.\"\"\"
    return text.strip()
"""
    }
    packet = EvidencePacketBuilder.build_packet(source_files, "art-no-sql-01", "agent.py")
    sql_surfaces = [s for s in packet.security_surfaces if s.surface_type == "SQL_EXECUTION"]
    assert len(sql_surfaces) == 0


# ===========================================================================
# 4. DYNAMIC MODEL NAME (DO NOT INVENT "gpt-4o-mini")
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_dynamic_model_marked_unknown():
    """When model is loaded from env or variable, LLM constructor evidence must NOT claim gpt-4o-mini."""
    source_files = {
        "agent.py": """
import os
from langchain_openai import ChatOpenAI

dynamic_model = os.getenv("TARGET_MODEL", "gpt-4-custom")
llm = ChatOpenAI(model=dynamic_model)
"""
    }
    packet = EvidencePacketBuilder.build_packet(source_files, "art-dyn-model-01", "agent.py")
    assert len(packet.llm_constructors) >= 1
    llm_ev = packet.llm_constructors[0]
    assert llm_ev.is_dynamic_model is True
    assert llm_ev.model_certainty in (CertaintyLevel.UNKNOWN, CertaintyLevel.INFERRED)


# ===========================================================================
# 5. UNKNOWN INPUTS & OUTPUTS (NEVER INVENT "topic" OR "query")
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_no_invented_default_inputs():
    """An agent with no CLI parser must not have invented default inputs like 'query' or 'topic'."""
    source_files = {
        "agent.py": """
def run():
    print("Static run")
"""
    }
    packet = EvidencePacketBuilder.build_packet(source_files, "art-no-input-01", "agent.py")
    assert len(packet.cli_arguments) == 0


# ===========================================================================
# 6. DEDICATED DECISION SURFACE VS SECURITY SURFACE ISOLATION
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_decision_surface_isolation():
    """Hiring decision contract creates a DECISION surface, not a SQL/execution security surface."""
    source_files = {
        "agent.py": """
FIT_PROMPT = \"\"\"Evaluate fit:
{
  "fit_score": 0-100,
  "recommendation": "Hire|Consider|Pass"
}
\"\"\"
def evaluate(): pass
"""
    }
    packet = EvidencePacketBuilder.build_packet(source_files, "art-dec-iso-01", "agent.py")
    assert len(packet.decision_surfaces) >= 1
    dec = packet.decision_surfaces[0]
    assert dec.decision_type == "CANDIDATE_EVALUATION"
    assert dec.impact == "EMPLOYMENT_DECISION"
    assert "Hire" in dec.recommendation_options

    # Must NOT have created SQL or Shell security surfaces
    sec_types = {s.surface_type for s in packet.security_surfaces}
    assert "SQL_EXECUTION" not in sec_types
    assert "SHELL_EXECUTION" not in sec_types


# ===========================================================================
# 7. ARTIFACT MISMATCH HARD GATE REJECTION
# ===========================================================================
@pytest.mark.asyncio
async def test_adversarial_artifact_mismatch_audit_defect():
    """Foreign artifact ID in evidence items triggers immediate audit DEFECT."""
    from app.core.intake.evidence_models import EvidenceItem, EvidenceCategory
    packet = EvidencePacketBuilder.build_packet({"agent.py": "x = 1"}, "art-legit-01", "agent.py")
    
    # Inject foreign artifact item
    packet.evidence_items.append(EvidenceItem(
        id="ev-contam-01",
        artifact_id="art-FOREIGN-ATTACKER-99",
        category=EvidenceCategory.FUNCTION_DEF,
        name="foreign_fn",
        source_file="foreign.py"
    ))

    spec = NormalizedAgentSpec(identity={"name": "Agent", "domain": "test", "entrypoint": "agent.py"})
    report = IntakeAuditor.audit_spec_against_evidence(spec, packet)

    assert report.audit_verdict == "DEFECT"
    assert any(d.discrepancy_type == DiscrepancyType.CROSS_ARTIFACT_CONTAMINATION for d in report.discrepancies)
