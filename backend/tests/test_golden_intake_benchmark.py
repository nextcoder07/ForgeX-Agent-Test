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

    # 2. Granular Database Security Surfaces (Connectivity, Generation, Execution, Mutation)
    sec_types = [s.surface_type for s in packet.security_surfaces]
    assert "DATABASE_CONNECTIVITY" in sec_types
    assert "SQL_QUERY_GENERATION" in sec_types
    assert "SQL_EXECUTION" in sec_types
    assert "DATABASE_MUTATION" in sec_types

    # 3. Output Contract Extraction
    assert len(packet.output_structures) > 0
    assert any(o.field_name == "output" for o in packet.output_structures)

    # 4. End-to-end Process Intake Verification
    payload = AgentIntakePayload(files=files, agent_name_hint="SQL Autonomous Agent")
    result = await process_agent_intake(payload, MockLLM())
    
    # Workflow graph enrichment
    wf_nodes = result.behavior_profile.workflow_graph.nodes
    assert len(wf_nodes) >= 2
    build_node = next((n for n in wf_nodes if n.id == "build_sql_agent"), None)
    assert build_node is not None
    assert "db_uri" in build_node.inputs
    assert len(build_node.external_dependencies) > 0


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


# ===========================================================================
# 5. NEWS SUMMARIZER AGENT FIXTURE (Network + URL Credential + Content Injection)
# ===========================================================================
NEWS_AGENT_CODE = '''"""
News Summarizer Agent using AutoGen.

Fetches news articles and produces structured summaries with key insights.
"""

import argparse
import os
import requests
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def fetch_news(topic: str, count: int = 5) -> list[dict]:
    if not NEWS_API_KEY:
        return [
            {"title": f"Major development in {topic}", "description": f"Researchers announce breakthrough in {topic} field.", "url": "https://example.com/1", "source": {"name": "Tech News"}}
        ]

    url = f"https://newsapi.org/v2/everything?q={topic}&language=en&pageSize={count}&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    response = requests.get(url, timeout=10)
    data = response.json()
    return data.get("articles", [])


def summarize_news(topic: str, articles: list[dict]) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    articles_text = "\\n\\n".join(
        f"Title: {a['title']}\\nSource: {a.get('source', {}).get('name', 'Unknown')}\\nSummary: {a.get('description', 'N/A')}"
        for a in articles[:5]
    )

    messages = [
        SystemMessage(content="You are a news analyst. Create a structured news briefing."),
        HumanMessage(content=f"Topic: {topic}\\n\\nArticles:\\n{articles_text}"),
    ]

    response = llm.invoke(messages)
    return response.content


def main():
    parser = argparse.ArgumentParser(description="News Summarizer Agent")
    parser.add_argument("--topic", default="artificial intelligence", help="News topic to search")
    parser.add_argument("--count", type=int, default=5, help="Number of articles to fetch")
    args = parser.parse_args()

    articles = fetch_news(args.topic, args.count)
    summary = summarize_news(args.topic, articles)
    print(summary)


if __name__ == "__main__":
    main()
'''

@pytest.mark.asyncio
async def test_news_agent_golden_intake():
    files = {
        "agent.py": NEWS_AGENT_CODE,
        "requirements.txt": "langchain==0.3.0\nlangchain-core==0.3.0\nlangchain-openai==0.2.0\nrequests==2.32.3\npython-dotenv==1.0.1"
    }
    payload = AgentIntakePayload(files=files, agent_name_hint="News Summarizer Agent")
    result = await process_agent_intake(payload, MockLLM())
    spec = result.normalized_spec
    bp = result.behavior_profile
    ev = result.evidence_packet

    # 1. Network Side-Effect Promoted to Canonical Spec & Profile
    assert bp is not None
    assert any("NETWORK" in s.upper() or "HTTP" in s.upper() or "newsapi.org" in s for s in spec.side_effects)
    assert any("NETWORK" in s.upper() or "HTTP" in s.upper() or "newsapi.org" in s for s in bp.side_effects)

    # 2. Security Detection: CREDENTIAL_IN_URL & EXTERNAL_CONTENT_INJECTION
    sec_surface_types = {s.get("surface_type") if isinstance(s, dict) else getattr(s, "surface_type", "") for s in spec.security_surfaces}
    assert "CREDENTIAL_IN_URL" in sec_surface_types
    assert "EXTERNAL_CONTENT_INJECTION" in sec_surface_types

    # 3. Functional vs Technical Capabilities
    cap_set = set(spec.capabilities + bp.capabilities)
    assert "NEWS_RETRIEVAL" in cap_set or "NEWS_SUMMARIZATION" in cap_set or "STRUCTURED_NEWS_BRIEFING" in cap_set
    assert "LLM_INFERENCE" in cap_set or "HTTP_API_ACCESS" in cap_set

    # 4. Input Promotion Fidelity: Type & Defaults
    inputs_by_name = {i["name"]: i for i in bp.inputs if isinstance(i, dict)}
    assert "count" in inputs_by_name
    assert inputs_by_name["count"]["type"] == "integer"
    assert inputs_by_name["count"]["default"] == 5
    assert inputs_by_name["count"]["required"] is False

    assert "topic" in inputs_by_name
    assert inputs_by_name["topic"]["type"] == "string"
    assert inputs_by_name["topic"]["default"] == "artificial intelligence"
    assert inputs_by_name["topic"]["required"] is False

    # 5. Workflow external dependencies: Noisy builtins filtered out
    fetch_node = next((n for n in bp.workflow_graph.nodes if n.id == "fetch_news"), None)
    assert fetch_node is not None
    assert "get" not in fetch_node.external_dependencies
    assert "json" not in fetch_node.external_dependencies
    assert "title" not in fetch_node.external_dependencies

    # 6. Workflow Edges: main -> fetch_news -> summarize_news
    edge_pairs = [(e["source"], e["target"]) for e in bp.workflow_graph.edges]
    assert ("main", "fetch_news") in edge_pairs
    assert ("fetch_news", "summarize_news") in edge_pairs

    # 7. Framework conflict detected (Docstring claims AutoGen, implementation is LangChain)
    audit = result.audit_report
    assert audit is not None
    discrepancies_list = audit.get("discrepancies", []) if isinstance(audit, dict) else getattr(audit, "discrepancies", [])
    discrepancy_types = [d.get("field") if isinstance(d, dict) else getattr(d, "field", "") for d in discrepancies_list]
    assert "framework" in discrepancy_types


EMAIL_AGENT_CODE = """\"\"\"
Email Drafting Agent using CrewAI.

A two-agent crew that drafts professional emails:
- Analyst agent: understands context and tone requirements
- Writer agent: drafts the final email

Usage:
    python agent.py
    python agent.py --context "Follow up on the Q3 proposal sent last week" --tone "professional"
\"\"\"

import argparse
import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def build_email_crew(context: str, tone: str, recipient: str) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

    analyst = Agent(
        role="Email Context Analyst",
        goal="Understand the email context, extract key points, and define the structure",
        backstory="You are an expert business communication analyst who distills complex situations into clear email requirements.",
        llm=llm,
        verbose=False,
    )

    writer = Agent(
        role="Professional Email Writer",
        goal="Draft clear, concise, and effective professional emails",
        backstory="You are a professional copywriter specializing in business emails that get responses.",
        llm=llm,
        verbose=False,
    )

    analyze_task = Task(
        description=f\"\"\"Analyze this email requirement:
Context: {context}
Recipient: {recipient}
Desired tone: {tone}

Extract: purpose, key points to cover, call to action, subject line suggestion.\"\"\",
        agent=analyst,
        expected_output="Structured email brief: purpose, key points, CTA, and suggested subject line",
    )

    write_task = Task(
        description=f\"\"\"Using the analysis, draft a complete professional email.
Tone: {tone}. Recipient: {recipient}.
Include: Subject line, greeting, body paragraphs, closing, signature placeholder.
Keep it concise — under 200 words for the body.\"\"\",
        agent=writer,
        expected_output="Complete formatted email ready to send",
        context=[analyze_task],
    )

    crew = Crew(
        agents=[analyst, writer],
        tasks=[analyze_task, write_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return str(result)


def main():
    parser = argparse.ArgumentParser(description="Email Drafting Agent")
    parser.add_argument("--context", default="Follow up on our product demo from last Tuesday. They seemed interested but haven't responded.", help="Email context/purpose")
    parser.add_argument("--tone", default="professional and friendly", help="Email tone")
    parser.add_argument("--recipient", default="a potential client", help="Who the email is for")
    args = parser.parse_args()

    print(f"\\n✉️  Drafting email...\\n")
    email = build_email_crew(args.context, args.tone, args.recipient)

    print("=" * 60)
    print("📧 DRAFTED EMAIL")
    print("=" * 60)
    print(email)


if __name__ == "__main__":
    main()
"""


@pytest.mark.asyncio
async def test_email_crewai_agent_golden_intake():
    """Validates the multi-agent CrewAI Email Drafting Agent intake extraction."""
    analysis_files = {
        "05-email-drafting-agent/agent.py": EMAIL_AGENT_CODE,
        "05-email-drafting-agent/requirements.txt": "crewai==0.80.0\nlangchain-openai==0.2.0\npython-dotenv==1.0.1\n",
        "05-email-drafting-agent/.env.example": "OPENAI_API_KEY=your_openai_api_key_here\n",
    }

    payload = AgentIntakePayload(files=analysis_files, agent_name_hint="Email Drafting Agent")
    result = await process_agent_intake(payload, MockLLM())

    norm_spec = result.normalized_spec
    bp = norm_spec.behavior_profile
    assert bp is not None

    # 1. Multi-Agent Framework Detected as CrewAI
    assert norm_spec.identity.get("framework") == "CrewAI"

    # 2. Multi-Agent sub-nodes and tasks extracted in workflow
    node_ids = [n.id for n in bp.workflow_graph.nodes]
    assert "analyze_task" in node_ids
    assert "write_task" in node_ids
    assert "build_email_crew" in node_ids
    assert "main" in node_ids

    # 3. Context flow edge: analyze_task -> write_task
    edge_pairs = [(e["source"], e["target"]) for e in bp.workflow_graph.edges]
    assert ("analyze_task", "write_task") in edge_pairs

    # 4. Output contract extracted with semantic type and constraints
    assert len(norm_spec.outputs) > 0
    email_output = next((o for o in norm_spec.outputs if o.get("name") == "email" or o.get("semantic_type") == "EMAIL_DRAFT"), None)
    assert email_output is not None
    assert email_output.get("semantic_type") == "EMAIL_DRAFT"
    assert "Complete formatted email ready to send" in email_output.get("description", "")
    assert email_output.get("constraints", {}).get("body_max_words") == 200

    # 5. Framework evidence provenance count > 0
    audit = result.audit_report
    assert audit is not None
    field_confidences = {f["field_name"]: f for f in audit.get("field_confidences", [])}
    assert "framework" in field_confidences
    assert field_confidences["framework"]["evidence_count"] > 0
    assert field_confidences["framework"]["certainty"] == "FACT"

    # 6. Inputs preserved with defaults
    inputs_by_name = {i["name"]: i for i in norm_spec.inputs}
    assert "context" in inputs_by_name
    assert "tone" in inputs_by_name
    assert "recipient" in inputs_by_name
    assert inputs_by_name["recipient"]["default"] == "a potential client"


