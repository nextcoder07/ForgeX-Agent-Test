"""
Automated unit & integration test for the Canonical Subsystem Detector & AST Analyzer.
Verifies evidence-backed extraction of Planning, Memory, RAG, Tools, External Services,
and Agent Model Slots.
"""

import pytest
from app.core.intake.subsystem_detector import SubsystemDetector
from app.models.canonical_agent import PlanningType, ToolSideEffectType, MemoryType


def test_react_and_tool_detection():
    """Verify ReAct pattern, tool declarations, and financial side-effect classification."""
    files = {
        "agent.py": '''
from langchain.tools import tool

@tool
def refund_order(order_id: str, amount: float):
    """Refunds customer order through payment gateway."""
    return {"status": "refunded", "order_id": order_id, "amount": amount}

@tool
def fetch_user_history(user_id: str):
    """Fetches user transaction history."""
    return {"user_id": user_id, "history": []}

def run_agent(query: str):
    # Thought-Action-Observation loop
    thought = "Need to refund user"
    action = refund_order(order_id="ORD-1", amount=500.0)
    return action
'''
    }

    rep = SubsystemDetector.analyze_source_files(
        agent_id="test-agent-react",
        agent_name="Customer Support Agent",
        files=files
    )

    assert rep.archetype in ("Autonomous Tool Agent", "ReAct-Style Agent")
    assert len(rep.tools) >= 2
    
    refund_tool = next((t for t in rep.tools if t.name == "refund_order"), None)
    assert refund_tool is not None
    assert refund_tool.side_effect_type == ToolSideEffectType.PAYMENT_FINANCIAL
    assert refund_tool.destructive is True
    assert refund_tool.authorization_required is True

    fetch_tool = next((t for t in rep.tools if t.name == "fetch_user_history"), None)
    assert fetch_tool is not None
    assert fetch_tool.is_read_only is True


def test_planner_executor_and_memory_detection():
    """Verify Planner-Executor architecture and SQLite / ConversationBufferMemory detection."""
    files = {
        "planner.py": '''
import sqlite3
from langchain.memory import ConversationBufferMemory

planner_llm = "gpt-4o"
executor_llm = "gpt-4o-mini"
memory = ConversationBufferMemory()

def plan_and_execute(goal: str):
    conn = sqlite3.connect("memory.db")
    plan = ["step1", "step2"]
    return plan
'''
    }

    rep = SubsystemDetector.analyze_source_files(
        agent_id="test-agent-planner",
        agent_name="Travel Planning Agent",
        files=files
    )

    assert rep.planning.planning_present is True
    assert rep.planning.planning_type == PlanningType.PLANNER_EXECUTOR
    assert rep.memory.memory_present is True
    assert MemoryType.CONVERSATION_HISTORY in rep.memory.memory_types
    assert MemoryType.DATABASE_MEMORY in rep.memory.memory_types
    assert len(rep.model_slots) >= 2


def test_rag_and_external_service_detection():
    """Verify RAG retriever and external API services (Stripe, Tavily) detection."""
    files = {
        "rag_agent.py": '''
import stripe
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

stripe.api_key = "sk_test_123"

def query_knowledge_base(query: str):
    vectorstore = Chroma(embedding_function=OpenAIEmbeddings())
    retriever = vectorstore.as_retriever()
    docs = vectorstore.similarity_search(query)
    return docs
'''
    }

    rep = SubsystemDetector.analyze_source_files(
        agent_id="test-agent-rag",
        agent_name="Financial RAG Agent",
        files=files
    )

    assert rep.context.retrieval_present is True
    assert rep.context.retriever == "VectorStoreRetriever"
    assert any(s.provider == "Stripe" for s in rep.external_services)
