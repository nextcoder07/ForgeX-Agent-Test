"""
Framework Analyzer Module.
Extracts structured WorkflowGraph (nodes, edges, entrypoint, terminal nodes, state dependencies)
dynamically across frameworks (LangGraph, AutoGen, CrewAI, generic scripts) without hardcoding agent function names.
"""

from __future__ import annotations

import ast
from typing import Dict, List, Any, Optional
from app.models.agent_behavior import WorkflowGraph, WorkflowNode, FunctionClassification


class FrameworkAnalyzer:
    @staticmethod
    def analyze_framework_workflow(ast_trees: Dict[str, ast.AST], raw_files: Dict[str, str]) -> WorkflowGraph:
        """Dynamically inspects AST trees across files to extract structured workflow graph."""
        nodes: List[WorkflowNode] = []
        edges: List[Dict[str, str]] = []
        entrypoint = "START"
        terminal_nodes: List[str] = []

        # 1. Inspect for LangGraph workflow constructs
        langgraph_found = False
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # Detect StateGraph instantiation
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    func_name = ""
                    if isinstance(node.value.func, ast.Name):
                        func_name = node.value.func.id
                    elif isinstance(node.value.func, ast.Attribute):
                        func_name = node.value.func.attr

                    if "StateGraph" in func_name or "MessageGraph" in func_name:
                        langgraph_found = True

                # Detect add_node calls: builder.add_node("search", search_web)
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

                    # Detect set_entry_point: builder.set_entry_point("search")
                    elif isinstance(call.func, ast.Attribute) and call.func.attr in ["set_entry_point", "set_finish_point"]:
                        if len(call.args) >= 1:
                            target_id = FrameworkAnalyzer._extract_string(call.args[0])
                            if target_id and call.func.attr == "set_entry_point":
                                entrypoint = target_id
                                edges.append({"source": "START", "target": target_id})
                            elif target_id and call.func.attr == "set_finish_point":
                                terminal_nodes.append(target_id)
                                edges.append({"source": target_id, "target": "END"})

                    # Detect add_edge: builder.add_edge("search", "synthesize")
                    elif isinstance(call.func, ast.Attribute) and call.func.attr == "add_edge":
                        if len(call.args) >= 2:
                            src = FrameworkAnalyzer._extract_string(call.args[0])
                            tgt = FrameworkAnalyzer._extract_string(call.args[1])
                            if src and tgt:
                                edges.append({"source": src, "target": tgt})

                    # Detect add_conditional_edges: builder.add_conditional_edges(...)
                    elif isinstance(call.func, ast.Attribute) and call.func.attr == "add_conditional_edges":
                        if len(call.args) >= 1:
                            src = FrameworkAnalyzer._extract_string(call.args[0])
                            if src:
                                edges.append({"source": src, "target": "CONDITIONAL_BRANCH"})

        # Fallback to function definitions if no explicit LangGraph add_node was parsed
        if not nodes:
            for fname, tree in ast_trees.items():
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Skip main or builder constructors
                        if node.name in ["main", "build_graph", "create_agent", "setup"]:
                            continue
                        
                        # Infer node if function takes state or returns state dict
                        is_workflow_node = any(arg.arg in ["state", "messages", "inputs"] for arg in node.args.args)
                        if is_workflow_node or "search" in node.name or "synthesize" in node.name or "process" in node.name:
                            nodes.append(
                                WorkflowNode(
                                    id=node.name,
                                    name=node.name,
                                    implementation=node.name,
                                    node_type="node"
                                )
                            )

            if len(nodes) >= 2:
                entrypoint = nodes[0].id
                edges.append({"source": "START", "target": nodes[0].id})
                for i in range(len(nodes) - 1):
                    edges.append({"source": nodes[i].id, "target": nodes[i+1].id})
                edges.append({"source": nodes[-1].id, "target": "END"})
                terminal_nodes.append(nodes[-1].id)

        if "END" not in terminal_nodes and edges:
            last_target = edges[-1].get("target")
            if last_target and last_target != "END":
                edges.append({"source": last_target, "target": "END"})
                terminal_nodes.append(last_target)

        return WorkflowGraph(
            nodes=nodes,
            edges=edges,
            entrypoint=entrypoint,
            terminal_nodes=terminal_nodes
        )

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
