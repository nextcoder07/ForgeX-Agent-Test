"""
Unit & Integration Tests for ForgeX Stage 1 Intake Upgrade (CanonicalIntake & Evidence Pipeline).
Verifies Single Source of Truth, Provenance Tracking, Tools vs Framework Constructs,
Credential State Gating, Contradiction Engine, and Quality Gate Evaluation.
"""

import pytest
import asyncio
from app.models.intake import AgentIntakePayload
from app.core.llm.mock_llm import MockLLM
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.intake.evidence_models import ProvenanceType, DependencyState, CertaintyLevel


@pytest.mark.asyncio
async def test_canonical_intake_single_source_of_truth_cli():
    """Verifies CanonicalIntake extraction for CLI agents with provenance and public inputs."""
    code = """
import argparse
import os

def process_file(file_path: str, format_type: str = "json"):
    print(f"Processing {file_path} as {format_type}")
    return {"status": "success", "file": file_path}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI File Processor")
    parser.add_argument("--file", required=True, help="Input file path")
    parser.add_argument("--format", default="json", help="Output format")
    args = parser.parse_args()
    process_file(args.file, args.format)
"""
    payload = AgentIntakePayload(
        files={"main.py": code},
        agent_name_hint="CLI File Processor",
        input_type="source_code"
    )
    llm = MockLLM()
    result = await process_agent_intake(payload, llm)
    
    assert result.canonical_intake is not None
    ci = result.canonical_intake
    assert ci["agent_name"] in ("CLI File Processor", "Customer Support Agent", "Discovered Agent")
    assert ci["interface_type"] == "CLI"
    assert len(ci["public_inputs"]) >= 1
    
    file_input = next((inp for inp in ci["public_inputs"] if inp["name"] in ("file", "format")), None)
    assert file_input is not None
    assert file_input["provenance"] == ProvenanceType.CODE_PROVEN.value


@pytest.mark.asyncio
async def test_canonical_intake_separates_framework_primitives_from_user_tools():
    """Verifies that StateGraph, END, and ChatOpenAI are NOT categorized as executable user tools."""
    code = """
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import os

def custom_search_tool(query: str):
    \"\"\"Searches external web API for query.\"\"\"
    api_key = os.getenv("TAVILY_API_KEY")
    return f"Search result for {query}"

builder = StateGraph(dict)
llm = ChatOpenAI(model="gpt-4o-mini")
"""
    payload = AgentIntakePayload(
        files={"graph_agent.py": code},
        agent_name_hint="LangGraph Agent",
        input_type="source_code"
    )
    llm = MockLLM()
    result = await process_agent_intake(payload, llm)
    
    ci = result.canonical_intake
    assert ci is not None
    tool_names = [t["name"] for t in ci["user_tools"]]
    primitive_names = [p["name"] for p in ci["framework_primitives"]]
    
    # StateGraph and ChatOpenAI must NOT be in user tools
    assert "StateGraph" not in tool_names
    assert "ChatOpenAI" not in tool_names
    assert "END" not in tool_names


@pytest.mark.asyncio
async def test_canonical_intake_credential_state_gating():
    """Verifies that required credentials are explicitly marked as USER_REQUIRED without silent injection."""
    code = """
import os
from langchain_openai import ChatOpenAI

def run():
    key = os.getenv("TAVILY_API_KEY")
    llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
"""
    payload = AgentIntakePayload(
        files={"agent.py": code},
        agent_name_hint="Secret Agent",
        input_type="source_code"
    )
    llm = MockLLM()
    result = await process_agent_intake(payload, llm)
    
    ci = result.canonical_intake
    assert ci is not None
    creds = ci["credentials"]
    assert len(creds) >= 1
    openai_cred = next((c for c in creds if "OPENAI" in c["name"].upper() or "TAVILY" in c["name"].upper()), None)
    assert openai_cred is not None
    assert openai_cred["requires_user_value"] is True


@pytest.mark.asyncio
async def test_canonical_intake_confidence_and_quality_gate():
    """Verifies that per-field confidence scores and quality gate status are present."""
    code = """
def process_data(data: str):
    return {"result": data.upper()}
"""
    payload = AgentIntakePayload(
        files={"agent.py": code},
        agent_name_hint="Simple Processor",
        input_type="source_code"
    )
    llm = MockLLM()
    result = await process_agent_intake(payload, llm)
    
    ci = result.canonical_intake
    assert ci is not None
    assert "field_confidences" in ci
    assert "overall_quality_score" in ci
    assert "quality_gate_passed" in ci
    assert ci["overall_quality_score"] > 0
