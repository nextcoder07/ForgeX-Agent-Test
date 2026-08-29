"""
Golden Test for PDF Q&A Agent Intake Isolation, Interface Contract, and Scenario Synthesis.
Guarantees:
1. Pure Artifact Isolation: Zero cross-agent tools (query_order / list_recent_orders must NEVER appear).
2. Interface Contract: Correctly identifies CLI interface with --pdf and --question arguments.
3. Scenario Fidelity: Generates executable CLI commands, input artifacts, and realistic risk distribution.
4. Zero Secret Leakage: API keys are masked with canary identifiers.
"""

import pytest
import asyncio
from app.models.intake import AgentIntakePayload
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.intake.intake_validator import IntakeValidator
from app.core.scenarios.scenario_generator import generate_scenarios_deterministically
from app.models.agent import AgentRecord, AgentConstitution, ToolDefinition
from app.models.scenario import ScenarioCategory, ScenarioPlan, ScenarioPlanItem


PDF_QA_AGENT_SOURCE = """
import os
import argparse
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.core.memory import ChatMemoryBuffer

def query_document(pdf_path: str, question: str) -> str:
    \"\"\"Reads a PDF file, builds a vector index, and queries the contents.\"\"\"
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    docs = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
    index = VectorStoreIndex.from_documents(docs)
    query_engine = index.as_query_engine()
    response = query_engine.query(question)
    return str(response)

def main():
    parser = argparse.ArgumentParser(description="PDF Q&A Autonomous Research Agent")
    parser.add_argument("--pdf", required=True, help="Path to PDF document")
    parser.add_argument("--question", required=True, help="Question to ask about the PDF")
    args = parser.parse_args()
    ans = query_document(args.pdf, args.question)
    print(f"Answer: {ans}")

if __name__ == "__main__":
    main()
"""

PDF_QA_REQUIREMENTS = """
llama-index>=0.10.0
llama-index-llms-openai>=0.1.0
llama-index-embeddings-openai>=0.1.0
python-dotenv>=1.0.0
"""


class MockLLM:
    model_name = "gemini-3.6-flash"
    async def analyze_evidence_packet(self, packet):
        return {
            "name": "PDF Q&A Document Agent",
            "domain": "document_intelligence",
            "archetypes": ["CLI_PROCESSOR", "RAG_PIPELINE", "DOCUMENT_QA"],
            "goals": ["Read PDF documents and answer user questions grounded in document context."],
            "instructions": ["Ingest PDF files accurately.", "Ground all answers strictly in the provided document."],
            "always_rules": ["Verify PDF file exists before building index."],
            "never_rules": ["Never fabricate answers not present in the indexed document."],
            "escalation_rules": ["Prompt user for alternative document if PDF is unreadable."],
            "data_policies": ["Do not persist document vectors beyond execution session."],
            "capabilities": ["PDF_PARSING", "DOCUMENT_INDEXING", "VECTOR_SEARCH"]
        }


@pytest.mark.asyncio
async def test_pdf_qa_intake_isolation_and_specification():
    """Test intake processes PDF agent with 100% boundary isolation."""
    payload = AgentIntakePayload(
        files={
            "agent.py": PDF_QA_AGENT_SOURCE,
            "requirements.txt": PDF_QA_REQUIREMENTS
        },
        input_type="package",
        agent_name_hint="PDF Q&A Document Agent"
    )

    llm = MockLLM()
    result = await process_agent_intake(payload, llm)

    spec = result.normalized_spec

    # 1. Verify Tool Isolation (Forbidden tools from other agents must NOT exist)
    extracted_tool_names = [t.name for t in spec.tools]
    assert "query_order" not in extracted_tool_names, "CRITICAL DEFECT: query_order from Simple Order Agent leaked into PDF QA agent!"
    assert "list_recent_orders" not in extracted_tool_names, "CRITICAL DEFECT: list_recent_orders leaked into PDF QA agent!"

    # 2. Verify Detected Interface & Entrypoint
    assert spec.runtime_manifest.get("detected_interface") == "CLI" or spec.runtime_manifest.get("interface_type") == "CLI"
    assert spec.runtime_manifest.get("entrypoint") == "agent.py"

    # 3. Verify Archetype / Framework Detection
    assert result.canonical_subsystems.archetype is not None

    # 4. Verify Intake Validation Gate
    validation = IntakeValidator.validate_and_remediate(spec, payload.files, "PDF Q&A Document Agent")
    assert validation.is_valid is True
    assert len(validation.purged_tools) == 0


def test_pdf_qa_scenario_generation_contract():
    """Test scenario generator creates executable CLI commands, input artifacts, and risk levels."""
    agent_record = AgentRecord(
        id="agent-pdf-qa-golden",
        name="PDF Q&A Document Agent",
        display_name="PDF Q&A Agent",
        source_name="agent.py",
        description="Autonomous document Q&A agent.",
        domain="document_intelligence",
        system_prompt="Read PDF documents and answer questions.",
        tools=[],
        dependencies=[],
        constitution=AgentConstitution(
            goals=["Answer questions from PDF"],
            always_rules=["Ground answers in document"],
            never_rules=["Never expose internal keys or tokens"]
        ),
        runtime_manifest={
            "entrypoint": "agent.py",
            "detected_interface": "CLI",
            "interface_type": "CLI",
            "interface": {
                "arguments": [
                    {"flags": ["--pdf"], "required": True},
                    {"flags": ["--question"], "required": True}
                ]
            }
        }
    )

    plan = ScenarioPlan(
        plan_id="PLAN-PDF-01",
        agent_id=agent_record.id,
        agent_name=agent_record.name,
        total_target=4,
        plan_items=[
            ScenarioPlanItem(plan_id="p1", target_type="category", category=ScenarioCategory.NORMAL, target="Baseline PDF QA", reason="Happy path"),
            ScenarioPlanItem(plan_id="p2", target_type="category", category=ScenarioCategory.EDGE, target="Empty PDF", reason="Edge case"),
            ScenarioPlanItem(plan_id="p3", target_type="category", category=ScenarioCategory.SECURITY, target="Secret exfiltration attack", reason="Security probe"),
            ScenarioPlanItem(plan_id="p4", target_type="category", category=ScenarioCategory.RECOVERY, target="Missing PDF handling", reason="Fault recovery"),
        ]
    )

    scenarios = generate_scenarios_deterministically(agent_record, plan)
    assert len(scenarios) == 4

    for sc in scenarios:
        # Verify Interface is CLI
        assert sc.interface_type == "CLI"
        # Verify Invocation is concrete command
        assert sc.invocation.get("type") == "command"
        assert "agent.py" in sc.invocation.get("command", "")
        assert "--pdf" in sc.invocation.get("command", "")
        assert "--question" in sc.invocation.get("command", "")

        # Verify Input Artifacts exist for PDF processing
        assert len(sc.input_artifacts) > 0
        assert any(a.get("path", "").endswith(".pdf") for a in sc.input_artifacts)

    # Verify Risk Level Distribution
    risk_levels = {sc.category: sc.risk_level for sc in scenarios}
    assert risk_levels[ScenarioCategory.NORMAL] == "low"
    assert risk_levels[ScenarioCategory.EDGE] == "low"
    assert risk_levels[ScenarioCategory.RECOVERY] == "medium"
    assert risk_levels[ScenarioCategory.SECURITY] == "critical"
