"""
Specialized Framework Detectors for LangChain, LlamaIndex, CrewAI, Agno, and Generic Python.
Extracts framework-native constructs and normalizes them into canonical ForgeX concepts.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Set
from app.core.intake.evidence_models import EvidenceCategory, EvidenceItem, CertaintyLevel


class FrameworkDetectionResult:
    def __init__(
        self,
        framework_name: str,
        confidence: float,
        constructs: List[Dict[str, Any]],
        detected_tools: List[Dict[str, Any]],
        detected_memory: Optional[Dict[str, Any]],
        evidence_items: List[EvidenceItem]
    ):
        self.framework_name = framework_name
        self.confidence = confidence
        self.constructs = constructs
        self.detected_tools = detected_tools
        self.detected_memory = detected_memory
        self.evidence_items = evidence_items


class LangChainDetector:
    @staticmethod
    def inspect(ast_trees: Dict[str, ast.AST], artifact_id: str) -> Optional[FrameworkDetectionResult]:
        constructs = []
        tools = []
        evidence_items = []
        is_langchain = False
        memory_info = None

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # 1. Imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    names = [alias.name for alias in node.names]
                    if "langchain" in module or any("langchain" in n for n in names):
                        is_langchain = True
                        ev_id = f"ev-lc-imp-{len(evidence_items)+1}"
                        evidence_items.append(EvidenceItem(
                            id=ev_id,
                            artifact_id=artifact_id,
                            category=EvidenceCategory.FRAMEWORK_CONSTRUCT,
                            name=f"LangChain Import ({module})",
                            source_file=fname,
                            line_number=getattr(node, "lineno", 1),
                            attributes={"module": module, "names": names}
                        ))

                # 2. Agent / Toolkit Constructors
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in ("create_sql_agent", "create_react_agent", "create_openai_tools_agent", "create_agent"):
                        is_langchain = True
                        constructs.append({
                            "type": "agent_constructor",
                            "name": func_name,
                            "file": fname,
                            "line": getattr(node, "lineno", 1)
                        })
                        ev_id = f"ev-lc-con-{len(evidence_items)+1}"
                        evidence_items.append(EvidenceItem(
                            id=ev_id,
                            artifact_id=artifact_id,
                            category=EvidenceCategory.FRAMEWORK_CONSTRUCT,
                            name=f"LangChain Agent Factory: {func_name}",
                            source_file=fname,
                            line_number=getattr(node, "lineno", 1),
                            attributes={"constructor": func_name}
                        ))

                    if func_name in ("SQLDatabaseToolkit", "SQLDatabase"):
                        constructs.append({
                            "type": "database_toolkit",
                            "name": func_name,
                            "file": fname,
                            "line": getattr(node, "lineno", 1)
                        })

                # 3. Tool Decorators (@tool)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in node.decorator_list:
                        dec_name = dec.id if isinstance(dec, ast.Name) else (dec.func.id if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) else "")
                        if dec_name == "tool":
                            is_langchain = True
                            tools.append({
                                "name": node.name,
                                "type": "langchain_tool_decorator",
                                "file": fname,
                                "line": getattr(node, "lineno", 1)
                            })

        if not is_langchain:
            return None

        return FrameworkDetectionResult(
            framework_name="LangChain",
            confidence=1.0 if constructs else 0.85,
            constructs=constructs,
            detected_tools=tools,
            detected_memory=memory_info,
            evidence_items=evidence_items
        )


class LlamaIndexDetector:
    @staticmethod
    def inspect(ast_trees: Dict[str, ast.AST], artifact_id: str) -> Optional[FrameworkDetectionResult]:
        constructs = []
        tools = []
        evidence_items = []
        is_llamaindex = False
        memory_info = None

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # 1. Imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    names = [alias.name for alias in node.names]
                    if "llama_index" in module or any("llama_index" in n for n in names):
                        is_llamaindex = True
                        ev_id = f"ev-llama-imp-{len(evidence_items)+1}"
                        evidence_items.append(EvidenceItem(
                            id=ev_id,
                            artifact_id=artifact_id,
                            category=EvidenceCategory.FRAMEWORK_CONSTRUCT,
                            name=f"LlamaIndex Import ({module})",
                            source_file=fname,
                            line_number=getattr(node, "lineno", 1),
                            attributes={"module": module, "names": names}
                        ))

                # 2. Core LlamaIndex Constructs
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in ("VectorStoreIndex", "SimpleDirectoryReader", "as_query_engine", "as_chat_engine"):
                        is_llamaindex = True
                        constructs.append({
                            "type": "rag_construct",
                            "name": func_name,
                            "file": fname,
                            "line": getattr(node, "lineno", 1)
                        })
                        ev_id = f"ev-llama-con-{len(evidence_items)+1}"
                        evidence_items.append(EvidenceItem(
                            id=ev_id,
                            artifact_id=artifact_id,
                            category=EvidenceCategory.FRAMEWORK_CONSTRUCT,
                            name=f"LlamaIndex RAG Construct: {func_name}",
                            source_file=fname,
                            line_number=getattr(node, "lineno", 1),
                            attributes={"construct": func_name}
                        ))

                    if func_name in ("ChatMemoryBuffer", "VectorMemory"):
                        memory_info = {
                            "type": func_name,
                            "file": fname,
                            "line": getattr(node, "lineno", 1)
                        }

        if not is_llamaindex:
            return None

        return FrameworkDetectionResult(
            framework_name="LlamaIndex",
            confidence=1.0 if constructs else 0.85,
            constructs=constructs,
            detected_tools=tools,
            detected_memory=memory_info,
            evidence_items=evidence_items
        )


class FrameworkRegistry:
    @staticmethod
    def detect_framework(ast_trees: Dict[str, ast.AST], artifact_id: str) -> FrameworkDetectionResult:
        # 1. Check LangChain
        lc = LangChainDetector.inspect(ast_trees, artifact_id)
        if lc:
            return lc

        # 2. Check LlamaIndex
        li = LlamaIndexDetector.inspect(ast_trees, artifact_id)
        if li:
            return li

        # 3. Fallback to Generic Python
        return FrameworkDetectionResult(
            framework_name="Generic Python",
            confidence=1.0,
            constructs=[],
            detected_tools=[],
            detected_memory=None,
            evidence_items=[
                EvidenceItem(
                    id=f"ev-fw-generic-{artifact_id[:6]}",
                    artifact_id=artifact_id,
                    category=EvidenceCategory.FRAMEWORK_CONSTRUCT,
                    name="Standard Python Application Architecture",
                    source_file="agent.py",
                    line_number=1
                )
            ]
        )
