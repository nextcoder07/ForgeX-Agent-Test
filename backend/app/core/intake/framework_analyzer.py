"""
Framework Analyzer Module.
Extracts structured WorkflowGraph and Framework Identity strictly based on code evidence
(e.g., LangGraph StateGraph, CrewAI Agent/Crew, AutoGen ConversableAgent, or generic script).
Never invents sequential edges when no framework workflow is proven.
"""

from __future__ import annotations

import ast
from typing import Dict, List, Any, Optional
from app.models.agent_behavior import WorkflowGraph, WorkflowNode


class FrameworkAnalyzer:
    @staticmethod
    def analyze_framework_workflow(ast_trees: Dict[str, ast.AST] = None, raw_files: Dict[str, str] = None) -> Dict[str, Any]:
        """Dynamically inspects AST trees to extract framework identity and structured workflow graph."""
        ast_trees = ast_trees or {}
        raw_files = raw_files or {}
        nodes: List[WorkflowNode] = []
        edges: List[Dict[str, str]] = []
        entrypoint = "START"
        terminal_nodes: List[str] = []
        framework_name = "unknown"
        framework_confidence = 0.1
        evidence: List[str] = []

        # 1. LangGraph Framework Detection
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # Detect StateGraph or MessageGraph instantiation
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    func_name = FrameworkAnalyzer._extract_callable_name(node.value.func)
                    if "StateGraph" in func_name or "MessageGraph" in func_name:
                        framework_name = "LangGraph"
                        framework_confidence = 0.99
                        evidence.append(f"StateGraph instantiated in {fname}")

                # Detect builder.add_node("node_name", function_reference)
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    call = node.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == "add_node":
                        if len(call.args) >= 2:
                            node_id = FrameworkAnalyzer._extract_string(call.args[0])
                            impl_func = FrameworkAnalyzer._extract_name(call.args[1])
                            if node_id:
                                nodes.append(
                                    WorkflowNode(
                                        id=node_id,
                                        name=node_id,
                                        implementation=impl_func or node_id,
                                        node_type="node"
                                    )
                                )
                                evidence.append(f"add_node('{node_id}', {impl_func})")

                    # Detect set_entry_point / set_finish_point
                    elif isinstance(call.func, ast.Attribute) and call.func.attr in ["set_entry_point", "set_finish_point"]:
                        if len(call.args) >= 1:
                            target_id = FrameworkAnalyzer._extract_string(call.args[0])
                            if target_id and call.func.attr == "set_entry_point":
                                entrypoint = target_id
                                edges.append({"source": "START", "target": target_id})
                                evidence.append(f"set_entry_point('{target_id}')")
                            elif target_id and call.func.attr == "set_finish_point":
                                terminal_nodes.append(target_id)
                                edges.append({"source": target_id, "target": "END"})
                                evidence.append(f"set_finish_point('{target_id}')")

                    # Detect add_edge: builder.add_edge("search", "synthesize")
                    elif isinstance(call.func, ast.Attribute) and call.func.attr == "add_edge":
                        if len(call.args) >= 2:
                            src = FrameworkAnalyzer._extract_string(call.args[0])
                            tgt = FrameworkAnalyzer._extract_string(call.args[1])
                            if src and tgt:
                                edges.append({"source": src, "target": tgt})
                                evidence.append(f"add_edge('{src}', '{tgt}')")

                    # Detect add_conditional_edges
                    elif isinstance(call.func, ast.Attribute) and call.func.attr == "add_conditional_edges":
                        if len(call.args) >= 1:
                            src = FrameworkAnalyzer._extract_string(call.args[0])
                            if src:
                                edges.append({"source": src, "target": "CONDITIONAL_BRANCH"})
                                evidence.append(f"add_conditional_edges('{src}')")

        # 2. CrewAI Framework Detection
        if framework_name == "unknown":
            all_text = " ".join(raw_files.values())
            if "from crewai" in all_text or "import Crew" in all_text or "Agent(" in all_text:
                framework_name = "CrewAI"
                framework_confidence = 0.95
                evidence.append("CrewAI SDK imported/instantiated")

        # 3. AutoGen Framework Detection
        if framework_name == "unknown":
            all_text = " ".join(raw_files.values())
            if "autogen" in all_text or "ConversableAgent" in all_text or "UserProxyAgent" in all_text:
                framework_name = "AutoGen"
                framework_confidence = 0.95
                evidence.append("AutoGen SDK imported/instantiated")

        # 4. Fallback for Generic / Script (No framework):
        # Do NOT invent sequential edges! Only report verified functions as nodes with low framework confidence.
        if framework_name == "unknown" and not nodes:
            for fname, tree in ast_trees.items():
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name not in ["main", "setup", "teardown", "__init__"]:
                            nodes.append(
                                WorkflowNode(
                                    id=node.name,
                                    name=node.name,
                                    implementation=node.name,
                                    node_type="function"
                                )
                            )

        # Normalize terminal nodes if edges exist
        if edges and "END" not in terminal_nodes:
            last_target = edges[-1].get("target")
            if last_target and last_target != "END":
                terminal_nodes.append(last_target)

        workflow_graph = WorkflowGraph(
            nodes=nodes,
            edges=edges,
            entrypoint=entrypoint,
            terminal_nodes=terminal_nodes
        )

        return {
            "framework": framework_name,
            "confidence": framework_confidence,
            "evidence": evidence,
            "workflow_graph": workflow_graph
        }

    @staticmethod
    def _extract_string(node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""

    @staticmethod
    def _extract_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""

    @staticmethod
    def _extract_callable_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
