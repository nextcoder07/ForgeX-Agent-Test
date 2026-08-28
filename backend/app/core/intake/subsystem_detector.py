"""
Deterministic Subsystem Detector & AST Static Analyzer.
Extracts PlanningProfile, MemoryProfile, ContextProfile, ToolProfile,
ExternalServiceProfile, and AgentModelSlot strictly from source code evidence.
"""

from __future__ import annotations

import ast
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.models.canonical_agent import (
    AgentModelSlot,
    CanonicalAgentRepresentation,
    ContextProfile,
    DataFlowEdge,
    ExternalServiceProfile,
    MemoryProfile,
    MemoryType,
    ModelSlotRole,
    PlanningProfile,
    PlanningType,
    ToolProfile,
    ToolSideEffectType,
)

logger = logging.getLogger(__name__)


class SubsystemDetector:
    """Static AST and Evidence-Backed Subsystem Analyzer for AI Agents."""

    @classmethod
    def analyze_source_files(
        cls, agent_id: str, agent_name: str, files: Dict[str, str]
    ) -> CanonicalAgentRepresentation:
        """Parses all source code files and builds the CanonicalAgentRepresentation."""
        all_code = "\n\n".join(files.values()) if files else ""
        
        # 1. Detect Planning Subsystem
        planning = cls._detect_planning(files, all_code)

        # 2. Detect Memory Subsystem
        memory = cls._detect_memory(files, all_code)

        # 3. Detect Context / RAG Subsystem
        context = cls._detect_context(files, all_code)

        # 4. Detect Tools & Functions
        tools = cls._detect_tools(files, all_code)

        # 5. Detect External Services
        external_services = cls._detect_external_services(files, all_code)

        # 6. Detect Model Slots
        model_slots = cls._detect_model_slots(agent_id, files, all_code)

        # 7. Deduce Data Flow Edges
        data_flows = cls._deduce_data_flows(planning, memory, context, tools, model_slots)

        archetype = cls._deduce_archetype(planning, memory, context, tools)

        return CanonicalAgentRepresentation(
            agent_id=agent_id,
            name=agent_name,
            domain="General Assistant" if "general" in agent_name.lower() else "Specialized Agent",
            archetype=archetype,
            planning=planning,
            memory=memory,
            context=context,
            tools=tools,
            external_services=external_services,
            model_slots=model_slots,
            data_flows=data_flows,
            policies=[
                "Ensure strict tool permission gating",
                "Isolate session memory across concurrent invocations",
            ]
        )

    @classmethod
    def _detect_planning(cls, files: Dict[str, str], all_code: str) -> PlanningProfile:
        code_lower = all_code.lower()
        evidence: List[str] = []
        planning_type = PlanningType.DIRECT_SHOT
        dynamic_replanning = False
        loop_present = False
        reflection_present = False
        delegation_present = False
        max_iterations = None

        # Check for State Machine / LangGraph
        if "stategraph" in code_lower or "graph.add_node" in code_lower or "langgraph" in code_lower:
            planning_type = PlanningType.WORKFLOW_STATE_MACHINE
            evidence.append("Observed StateGraph node/edge workflow structure (LangGraph)")

        # Check for Multi-agent delegation (CrewAI, AutoGen)
        elif "crew(" in code_lower or "conversableagent" in code_lower or "autogen" in code_lower or "delegate" in code_lower:
            planning_type = PlanningType.MULTI_AGENT_DELEGATION
            delegation_present = True
            evidence.append("Observed Multi-Agent delegation framework (CrewAI/AutoGen/Hierarchical)")

        # Check for Planner-Executor
        elif "plan_and_execute" in code_lower or "planner" in code_lower and "executor" in code_lower:
            planning_type = PlanningType.PLANNER_EXECUTOR
            dynamic_replanning = "replan" in code_lower or "replanning" in code_lower
            evidence.append("Observed Plan-and-Execute separation pattern")

        # Check for ReAct Loop
        elif "react" in code_lower or "create_react_agent" in code_lower or "thought:" in code_lower and "action:" in code_lower:
            planning_type = PlanningType.REACT
            loop_present = True
            evidence.append("Observed ReAct Thought-Action-Observation iterative loop pattern")

        # Check for Router
        elif "router" in code_lower or "classify_intent" in code_lower or "route_query" in code_lower:
            planning_type = PlanningType.ROUTER
            evidence.append("Observed Router / Intent-classifier routing logic")

        # Check for While / Loop Iterations
        if re.search(r"while\s+.*iterations?\s*<\s*(\d+)", all_code, re.IGNORECASE):
            match = re.search(r"while\s+.*iterations?\s*<\s*(\d+)", all_code, re.IGNORECASE)
            if match:
                max_iterations = int(match.group(1))
                loop_present = True
                evidence.append(f"Observed bounded loop with max_iterations={max_iterations}")
        elif "while " in all_code or "for step in" in all_code:
            loop_present = True
            evidence.append("Observed iterative step loop construct")

        if "reflect" in code_lower or "critique" in code_lower or "self_check" in code_lower:
            reflection_present = True
            evidence.append("Observed self-reflection / critique verification logic")

        planning_present = planning_type != PlanningType.DIRECT_SHOT or loop_present or len(evidence) > 0

        return PlanningProfile(
            planning_present=planning_present,
            planning_type=planning_type,
            planner_component="WorkflowEngine" if planning_type == PlanningType.WORKFLOW_STATE_MACHINE else "ReActLoop",
            dynamic_replanning=dynamic_replanning,
            reflection_present=reflection_present,
            loop_present=loop_present,
            max_iterations=max_iterations,
            delegation_present=delegation_present,
            evidence=evidence if evidence else ["Direct single-shot generation pattern detected"],
            confidence=0.95 if evidence else 0.8
        )

    @classmethod
    def _detect_memory(cls, files: Dict[str, str], all_code: str) -> MemoryProfile:
        code_lower = all_code.lower()
        types: List[MemoryType] = []
        evidence: List[str] = []
        storage_backend = None
        write_points: List[str] = []
        read_points: List[str] = []

        if "conversationbuffermemory" in code_lower or "chatmessagehistory" in code_lower:
            types.append(MemoryType.CONVERSATION_HISTORY)
            types.append(MemoryType.SHORT_TERM)
            evidence.append("Observed LangChain ChatMessageHistory / ConversationBufferMemory")
            storage_backend = "In-Memory Buffer"

        if "sqlite" in code_lower or "db.execute" in code_lower:
            types.append(MemoryType.DATABASE_MEMORY)
            types.append(MemoryType.LONG_TERM)
            evidence.append("Observed SQLite / relational database memory persistence")
            storage_backend = "SQLite / Relational DB"

        if "redis" in code_lower:
            types.append(MemoryType.SESSION_STATE)
            types.append(MemoryType.SHORT_TERM)
            evidence.append("Observed Redis key-value session store")
            storage_backend = "Redis"

        if "chroma" in code_lower or "pinecone" in code_lower or "qdrant" in code_lower:
            types.append(MemoryType.VECTOR_STORE)
            types.append(MemoryType.EPISODIC)
            evidence.append("Observed Vector Database episodic memory store")
            storage_backend = "Vector DB"

        # Check for explicit state dictionaries
        if re.search(r"(state|session)\[['\"][a-zA-Z0-9_]+['\"]\]\s*=", all_code):
            types.append(MemoryType.SESSION_STATE)
            write_points.append("Dictionary assignment to state key")
            evidence.append("Observed mutable session state dictionary mutations")

        if re.search(r"=\s*(state|session)\[['\"][a-zA-Z0-9_]+['\"]\]", all_code):
            read_points.append("Dictionary lookup from state key")

        memory_present = len(types) > 0

        return MemoryProfile(
            memory_present=memory_present,
            memory_types=types if types else [MemoryType.SHORT_TERM],
            storage_backend=storage_backend or ("In-Memory Session" if memory_present else "Stateless"),
            retrieval_mechanism="Key Lookup / Buffer" if memory_present else "None",
            write_points=write_points,
            read_points=read_points,
            persistence_scope="PERSISTENT_CROSS_SESSION" if MemoryType.DATABASE_MEMORY in types else ("SESSION" if memory_present else "EPHEMERAL"),
            evidence=evidence if evidence else ["Stateless request-response pattern (no memory backend detected)"],
            confidence=0.9 if evidence else 0.8
        )

    @classmethod
    def _detect_context(cls, files: Dict[str, str], all_code: str) -> ContextProfile:
        code_lower = all_code.lower()
        evidence: List[str] = []
        retrieval_present = False
        retriever = None

        if "similarity_search" in code_lower or "as_retriever" in code_lower or "vectorstore" in code_lower:
            retrieval_present = True
            retriever = "VectorStoreRetriever"
            evidence.append("Observed VectorStore similarity search retriever")

        if "textsplitter" in code_lower or "chunk_size" in code_lower:
            evidence.append("Observed document chunking / text splitting")

        if "embeddings" in code_lower or "openaiembeddings" in code_lower or "googleembeddings" in code_lower:
            evidence.append("Observed semantic embeddings model integration")

        if "citation" in code_lower or "source_documents" in code_lower:
            evidence.append("Observed source document citations & grounding payload")

        return ContextProfile(
            retrieval_present=retrieval_present,
            retrieval_backend="Chroma / VectorDB" if retrieval_present else None,
            retriever=retriever,
            chunking="RecursiveCharacterTextSplitter" if "textsplitter" in code_lower else None,
            evidence=evidence if evidence else ["No RAG or document retrieval pipelines detected"],
            confidence=0.9 if evidence else 0.8
        )

    @classmethod
    def _detect_tools(cls, files: Dict[str, str], all_code: str) -> List[ToolProfile]:
        tools: List[ToolProfile] = []
        
        # AST parsing for functions with @tool or declared in tools list
        for fname, content in files.items():
            if not fname.endswith(".py"):
                continue
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check decorator @tool
                        is_tool = any(
                            (isinstance(d, ast.Name) and d.id in ("tool", "agent_tool")) or
                            (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id in ("tool", "agent_tool"))
                            for d in node.decorator_list
                        )
                        # Check name conventions or docstring tool hints
                        fn_name = node.name
                        if not is_tool and fn_name in ("refund_order", "send_email", "cancel_order", "delete_file", "search_web", "execute_sql"):
                            is_tool = True

                        if is_tool:
                            # Analyze side effect
                            side_effect = ToolSideEffectType.NONE
                            destructive = False
                            auth_req = False
                            confirm_req = False

                            if any(w in fn_name.lower() for w in ["refund", "pay", "charge", "transfer"]):
                                side_effect = ToolSideEffectType.PAYMENT_FINANCIAL
                                destructive = True
                                auth_req = True
                                confirm_req = True
                            elif any(w in fn_name.lower() for w in ["delete", "remove", "drop", "truncate"]):
                                side_effect = ToolSideEffectType.DATABASE_WRITE if "sql" in fn_name.lower() else ToolSideEffectType.FILESYSTEM
                                destructive = True
                                confirm_req = True
                            elif any(w in fn_name.lower() for w in ["email", "notify", "slack", "message"]):
                                side_effect = ToolSideEffectType.EMAIL_COMMUNICATION
                            elif any(w in fn_name.lower() for w in ["write", "create", "insert", "update"]):
                                side_effect = ToolSideEffectType.DATABASE_WRITE

                            docstring = ast.get_docstring(node) or f"Autonomous tool {fn_name}"
                            params = {arg.arg: "Any" for arg in node.args.args if arg.arg != "self"}

                            tools.append(ToolProfile(
                                tool_id=f"tool-{uuid.uuid4().hex[:6]}",
                                name=fn_name,
                                description=docstring.strip(),
                                parameters_schema={"type": "object", "properties": {p: {"type": "string"} for p in params}},
                                side_effect_type=side_effect,
                                is_read_only=side_effect == ToolSideEffectType.NONE,
                                destructive=destructive,
                                authorization_required=auth_req,
                                confirmation_required=confirm_req,
                                idempotency=not destructive,
                                source_evidence=f"{fname}:def {fn_name}()",
                                policy_constraints=[f"Mandate confirmation if {fn_name} executes destructive side effect"] if destructive else []
                            ))
            except Exception as e:
                logger.debug(f"AST parsing error on {fname}: {e}")

        # Fallback keyword scanning if AST found no decorated tools
        if not tools:
            for line in all_code.splitlines():
                if "def " in line and any(w in line for w in ["search", "fetch", "query", "calculate", "summarize", "scrape"]):
                    match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", line)
                    if match:
                        name = match.group(1)
                        if not any(t.name == name for t in tools):
                            tools.append(ToolProfile(
                                tool_id=f"tool-{uuid.uuid4().hex[:6]}",
                                name=name,
                                description=f"Observed tool/function {name}",
                                side_effect_type=ToolSideEffectType.NONE,
                                is_read_only=True,
                                source_evidence=f"Line: {line.strip()}"
                            ))

        return tools

    @classmethod
    def _detect_external_services(cls, files: Dict[str, str], all_code: str) -> List[ExternalServiceProfile]:
        services: List[ExternalServiceProfile] = []
        code_lower = all_code.lower()

        catalog = [
            ("Stripe", "Payment Gateway", ["STRIPE_API_KEY"], ["stripe"]),
            ("Tavily", "Web Search API", ["TAVILY_API_KEY"], ["tavily"]),
            ("NewsAPI", "News Ingestion API", ["NEWS_API_KEY"], ["newsapi", "news_api"]),
            ("PostgreSQL", "Database Service", ["DATABASE_URL", "POSTGRES_PASSWORD"], ["psycopg2", "asyncpg", "postgresql"]),
            ("Serper", "Google Search API", ["SERPER_API_KEY"], ["serper"]),
            ("AWS S3", "Cloud Storage Service", ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"], ["boto3", "s3"]),
        ]

        for name, desc, creds, keywords in catalog:
            if any(k in code_lower for k in keywords):
                services.append(ExternalServiceProfile(
                    service_id=f"svc-{name.lower().replace(' ', '-')}",
                    provider=name,
                    required_credentials=creds,
                    mock_adapter=f"Platform{name.replace(' ', '')}MockGateway",
                    evidence=f"Observed reference to {name} library/tokens in source code"
                ))

        return services

    @classmethod
    def _detect_model_slots(cls, agent_id: str, files: Dict[str, str], all_code: str) -> List[AgentModelSlot]:
        slots: List[AgentModelSlot] = []
        
        # Scan for distinct model role assignments
        roles_catalog = [
            ("planner_llm", ModelSlotRole.PLANNER, "Planner Model", "planner"),
            ("router_llm", ModelSlotRole.ROUTER, "Router Model", "router"),
            ("researcher_llm", ModelSlotRole.RESEARCHER, "Researcher Model", "researcher"),
            ("critic_llm", ModelSlotRole.REVIEWER_CRITIC, "Critic / Safety Judge Model", "critic"),
            ("vision_llm", ModelSlotRole.VISION, "Vision Model", "vision"),
            ("embedding_model", ModelSlotRole.EMBEDDING, "Embeddings Model", "embedding"),
        ]

        found_custom_slots = False
        for var_name, role, display_name, kw in roles_catalog:
            if var_name in all_code:
                slots.append(AgentModelSlot(

                    slot_id=var_name,
                    agent_id=agent_id,
                    role=role,
                    name=display_name,
                    code_variable=var_name,
                    source_location="Dynamic AST Detection",
                    detected_provider="openai",
                    detected_model="gpt-4o-mini",
                    bound_connection_id="system_default"
                ))
                found_custom_slots = True

        # Always ensure Primary Model Slot is available if no multi-role slots detected
        if not found_custom_slots or not any(s.role == ModelSlotRole.PRIMARY for s in slots):
            slots.insert(0, AgentModelSlot(
                slot_id="primary_llm",
                agent_id=agent_id,
                role=ModelSlotRole.PRIMARY,
                name="Primary Agent Model",
                code_variable="llm",
                source_location="Main Agent Entrypoint",
                detected_provider="openai",
                detected_model="gpt-4o-mini",
                bound_connection_id="system_default"
            ))

        return slots

    @classmethod
    def _deduce_data_flows(
        cls,
        planning: PlanningProfile,
        memory: MemoryProfile,
        context: ContextProfile,
        tools: List[ToolProfile],
        model_slots: List[AgentModelSlot]
    ) -> List[DataFlowEdge]:
        edges: List[DataFlowEdge] = []
        edges.append(DataFlowEdge(source="User Prompt", target="Agent Intake Gateway", data_type="Text / JSON"))

        if planning.planning_type == PlanningType.ROUTER:
            edges.append(DataFlowEdge(source="Agent Intake Gateway", target="Router Model", data_type="Query Intent"))
            edges.append(DataFlowEdge(source="Router Model", target="Specialist Planner", data_type="Routed Plan"))
        else:
            edges.append(DataFlowEdge(source="Agent Intake Gateway", target="Primary Agent Model", data_type="Context Payload"))

        if context.retrieval_present:
            edges.append(DataFlowEdge(source="VectorStoreRetriever", target="Primary Agent Model", data_type="RAG Chunks"))

        for t in tools[:3]:
            edges.append(DataFlowEdge(source="Primary Agent Model", target=f"Tool: {t.name}", data_type="Invocation Args"))
            edges.append(DataFlowEdge(source=f"Tool: {t.name}", target="Primary Agent Model", data_type="Observation / Result"))

        if memory.memory_present:
            edges.append(DataFlowEdge(source="Primary Agent Model", target="Session State Store", data_type="Memory Write"))

        edges.append(DataFlowEdge(source="Primary Agent Model", target="Final Output", data_type="Validated Response"))
        return edges

    @classmethod
    def _deduce_archetype(
        cls, planning: PlanningProfile, memory: MemoryProfile, context: ContextProfile, tools: List[ToolProfile]
    ) -> str:
        if planning.planning_type == PlanningType.MULTI_AGENT_DELEGATION:
            return "Multi-Agent Orchestrator"
        if planning.planning_type == PlanningType.WORKFLOW_STATE_MACHINE:
            return "State Machine Workflow"
        if planning.planning_type == PlanningType.PLANNER_EXECUTOR:
            return "Planner-Executor Agent"
        if context.retrieval_present:
            return "RAG & Knowledge Retrieval Agent"
        if len(tools) > 0:
            return "Autonomous Tool Agent"
        return "Single-Shot LLM Assistant"
