"""
Comprehensive Golden Intake Benchmark Suite.
Validates the 4 core archetypes against ground truth facts:
1. Recipe Agent: Simple LLM CLI application with structured JSON output.
2. PDF Q&A Agent: LlamaIndex RAG application with file inputs and memory buffer.
3. SQL Agent: LangChain SQLDatabaseToolkit with conditional write security surface.
4. Resume Agent: PII processing application with dual LLM constructors and file ingestion.
"""

import pytest
from app.models.intake import AgentIntakePayload
from app.core.intake.spec_reconstructor import process_agent_intake
from app.core.intake.evidence_builder import EvidencePacketBuilder
from app.core.intake.intake_auditor import IntakeAuditor


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
# 1. RECIPE AGENT FIXTURE
# ===========================================================================
RECIPE_AGENT_CODE = """
import argparse
import json
from openai import OpenAI

def generate_recipe(cuisine: str, diet: str, servings: int) -> dict:
    client = OpenAI()
    prompt = f"Create a {cuisine} recipe suitable for {diet} diet serving {servings} people in JSON format."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return json.loads(resp.choices[0].message.content)

def main():
    parser = argparse.ArgumentParser(description="Recipe Generator CLI")
    parser.add_argument("--cuisine", required=True, help="Type of cuisine")
    parser.add_argument("--diet", default="vegetarian", help="Dietary restrictions")
    parser.add_argument("--servings", type=int, default=4, help="Number of servings")
    args = parser.parse_args()
    recipe = generate_recipe(args.cuisine, args.diet, args.servings)
    print(json.dumps(recipe))

if __name__ == "__main__":
    main()
"""

@pytest.mark.asyncio
async def test_recipe_agent_golden_intake():
    files = {"agent.py": RECIPE_AGENT_CODE, "requirements.txt": "openai>=1.0.0"}
    packet = EvidencePacketBuilder.build_packet(files, "art-recipe-01", "agent.py")
    
    # 1. Deterministic CLI Extraction Assertions
    cli_flags = {flag for opt in packet.cli_arguments for flag in opt.flags}
    assert "--cuisine" in cli_flags
    assert "--diet" in cli_flags
    assert "--servings" in cli_flags

    # 2. LLM Constructor Extraction Assertions
    assert len(packet.llm_constructors) >= 1
    assert packet.llm_constructors[0].provider == "openai"

    # 3. Reconstruct and Audit
    payload = AgentIntakePayload(files=files, agent_name_hint="Recipe Generator Agent")
    result = await process_agent_intake(payload, MockLLM())
    assert result.normalized_spec.runtime_manifest.get("detected_interface") == "CLI"
    assert result.audit_report is not None
    assert result.audit_report["overall_quality_score"] >= 90.0


# ===========================================================================
# 2. PDF Q&A AGENT FIXTURE
# ===========================================================================
PDF_AGENT_CODE = """
import os
import argparse
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.core.memory import ChatMemoryBuffer

def query_doc(pdf_path: str, question: str) -> str:
    docs = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
    index = VectorStoreIndex.from_documents(docs)
    query_engine = index.as_query_engine()
    return str(query_engine.query(question))

def main():
    parser = argparse.ArgumentParser(description="PDF Q&A Assistant")
    parser.add_argument("--pdf", required=True, help="PDF path")
    parser.add_argument("--question", required=True, help="Question to ask")
    args = parser.parse_args()
    print(query_doc(args.pdf, args.question))

if __name__ == "__main__":
    main()
"""

@pytest.mark.asyncio
async def test_pdf_agent_golden_intake():
    files = {"agent.py": PDF_AGENT_CODE, "requirements.txt": "llama-index\nllama-index-llms-openai"}
    packet = EvidencePacketBuilder.build_packet(files, "art-pdf-01", "agent.py")

    # 1. Framework Constructs
    construct_names = [c.get("name") for c in packet.framework_constructs]
    assert "VectorStoreIndex" in construct_names or "SimpleDirectoryReader" in construct_names

    # 2. CLI Inputs
    cli_flags = {flag for opt in packet.cli_arguments for flag in opt.flags}
    assert "--pdf" in cli_flags
    assert "--question" in cli_flags

    # 3. Security Surfaces (Untrusted File Read)
    sec_types = [s.surface_type for s in packet.security_surfaces]
    assert "UNTRUSTED_FILE_READ" in sec_types


# ===========================================================================
# 3. SQL AGENT FIXTURE (LangChain + Conditional Write)
# ===========================================================================
SQL_AGENT_CODE = """
import argparse
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

def build_sql_agent(db_uri: str, allow_write: bool = False):
    db = SQLDatabase.from_uri(db_uri)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    return create_sql_agent(llm=llm, toolkit=toolkit, verbose=True)

def main():
    parser = argparse.ArgumentParser(description="SQL Autonomous Agent")
    parser.add_argument("--query", required=True, help="Natural language query")
    parser.add_argument("--db-path", default="demo.db", help="SQLite database path")
    parser.add_argument("--allow-write", action="store_true", help="Enable write capabilities")
    args = parser.parse_args()
    agent = build_sql_agent(f"sqlite:///{args.db_path}", allow_write=args.allow_write)
    print(agent.invoke({"input": args.query}))

if __name__ == "__main__":
    main()
"""

@pytest.mark.asyncio
async def test_sql_agent_golden_intake():
    files = {"agent.py": SQL_AGENT_CODE, "requirements.txt": "langchain\nlangchain-community\nlangchain-openai"}
    packet = EvidencePacketBuilder.build_packet(files, "art-sql-01", "agent.py")

    # 1. Framework Constructs
    construct_names = [c.get("name") for c in packet.framework_constructs]
    assert "create_sql_agent" in construct_names or "SQLDatabaseToolkit" in construct_names

    # 2. Security Surfaces (SQL Execution & Conditional Write Flag)
    sec_types = [s.surface_type for s in packet.security_surfaces]
    assert "SQL_EXECUTION" in sec_types
    sql_sec = [s for s in packet.security_surfaces if s.surface_type == "SQL_EXECUTION"][0]
    assert "--allow-write" in sql_sec.trigger_condition


# ===========================================================================
# 4. RESUME AGENT FIXTURE (PII + Dual LLM + File Parsing)
# ===========================================================================
RESUME_AGENT_CODE = """
import argparse
import json
from langchain_openai import ChatOpenAI

def read_resume_text(pdf_path: str) -> str:
    with open(pdf_path, "r", errors="ignore") as f:
        return f.read()

def parse_resume(raw_text: str) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    prompt = f"Extract candidate name, email, skills, experience from resume: {raw_text}"
    resp = llm.invoke(prompt)
    return {"raw": resp.content}

def score_fit(resume_profile: dict, job_desc: str) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    prompt = f"Score candidate match for job {job_desc}: {resume_profile}"
    resp = llm.invoke(prompt)
    return {"fit_score": 88.5, "analysis": resp.content}

def main():
    parser = argparse.ArgumentParser(description="Autonomous Resume Screener")
    parser.add_argument("--resume", required=True, help="Path to candidate resume file")
    parser.add_argument("--job-desc", required=True, help="Target job description")
    args = parser.parse_args()
    text = read_resume_text(args.resume)
    profile = parse_resume(text)
    score = score_fit(profile, args.job_desc)
    print(json.dumps(score))

if __name__ == "__main__":
    main()
"""

@pytest.mark.asyncio
async def test_resume_agent_golden_intake():
    files = {"agent.py": RESUME_AGENT_CODE, "requirements.txt": "langchain-openai"}
    packet = EvidencePacketBuilder.build_packet(files, "art-resume-01", "agent.py")

    # 1. Dual LLM Constructors Detected
    assert len(packet.llm_constructors) == 2
    models_detected = {m.model_name for m in packet.llm_constructors}
    assert "gpt-4o-mini" in models_detected
    assert "gpt-4o" in models_detected

    # 2. PII Security Surface Detected
    sec_types = [s.surface_type for s in packet.security_surfaces]
    assert "PII_PROCESSING" in sec_types

    # 3. Static Call Graph Edges (main -> read_resume_text -> parse_resume -> score_fit)
    callers = {e.caller for e in packet.call_graph}
    assert "main" in callers
