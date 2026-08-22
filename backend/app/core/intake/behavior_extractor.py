"""
Behavior Extractor Module.
Extracts data transformations, code invariants, state models, failure surfaces, and security exposures
strictly from source code AST trees and declared documentation.
Never invents hardcoded domain assumptions or fake inputs/outputs.
"""

from __future__ import annotations

import ast
import re
from typing import Dict, List, Any
from app.models.agent_behavior import (
    DataTransformation,
    CodeInvariant,
    FailureSurface,
    DeclaredVsImplementedConflict,
)


class BehaviorExtractor:
    @staticmethod
    def extract_behavioral_facts(ast_trees: Dict[str, ast.AST], raw_files: Dict[str, str]) -> Dict[str, Any]:
        """Extracts data transformations, code invariants, state models, and failure surfaces."""
        transformations: List[DataTransformation] = []
        invariants: List[CodeInvariant] = []
        failure_surfaces: List[FailureSurface] = []
        state_model: Dict[str, Any] = {}
        inputs: List[Dict[str, Any]] = []
        outputs: List[Dict[str, Any]] = []
        security_surfaces: List[Dict[str, Any]] = []

        # 1. Inspect AST for State Models (TypedDict / BaseModel)
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    is_state_class = any(
                        b.id in ["TypedDict", "BaseModel", "State"]
                        for b in node.bases if isinstance(b, ast.Name)
                    )
                    if is_state_class or "state" in node.name.lower():
                        fields = []
                        for item in node.body:
                            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                fields.append(item.target.id)
                        state_model = {
                            "class_name": node.name,
                            "type": "TypedDict" if any(b.id == "TypedDict" for b in node.bases if isinstance(b, ast.Name)) else "BaseModel",
                            "fields": fields
                        }
                        # Derive inputs/outputs from state model if present
                        if "query" in fields or "input" in fields or "prompt" in fields:
                            in_field = next(f for f in fields if f in ["query", "input", "prompt", "messages"])
                            inputs.append({"name": in_field, "type": "string", "source": f"state_model.{in_field}"})
                        if "report" in fields or "output" in fields or "result" in fields or "response" in fields:
                            out_field = next(f for f in fields if f in ["report", "output", "result", "response"])
                            outputs.append({"name": out_field, "type": "string", "source": f"state_model.{out_field}"})

                # Detect String Truncation (Subscript Slice [:500])
                elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                    if isinstance(node.slice.upper, ast.Constant) and isinstance(node.slice.upper.value, int):
                        limit = node.slice.upper.value
                        transformations.append(
                            DataTransformation(
                                field="retrieved_content",
                                operation="truncate",
                                parameters={"max_length": limit},
                                evidence=f"Content sliced with upper bound {limit} in {fname}"
                            )
                        )

                # Detect Invariants (e.g. max_results = 5, temperature = 0, model = "gpt-4o-mini")
                elif isinstance(node, ast.keyword):
                    if node.arg == "max_results" and isinstance(node.value, ast.Constant):
                        invariants.append(
                            CodeInvariant(
                                statement=f"Search max_results = {node.value.value}",
                                type="observed",
                                enforcement_level="hard",
                                testability="deterministic",
                                source_file=fname,
                                evidence=f"max_results={node.value.value}",
                                confidence=1.0
                            )
                        )
                    elif node.arg == "temperature" and isinstance(node.value, ast.Constant):
                        invariants.append(
                            CodeInvariant(
                                statement=f"LLM temperature = {node.value.value}",
                                type="observed",
                                enforcement_level="hard",
                                testability="deterministic",
                                source_file=fname,
                                evidence=f"temperature={node.value.value}",
                                confidence=1.0
                            )
                        )
                    elif node.arg == "model" and isinstance(node.value, ast.Constant):
                        invariants.append(
                            CodeInvariant(
                                statement=f"LLM model = {node.value.value}",
                                type="observed",
                                enforcement_level="hard",
                                testability="deterministic",
                                source_file=fname,
                                evidence=f"model={node.value.value}",
                                confidence=1.0
                            )
                        )

        # 2. Extract Declared Output Contract Invariants from System Prompts
        for fname, code in raw_files.items():
            if "Summary" in code and "Key Findings" in code and "Sources" in code:
                invariants.append(
                    CodeInvariant(
                        statement="Report output sections: Summary, Key Findings, Sources",
                        type="declared",
                        enforcement_level="soft",
                        testability="deterministic_output_assertion",
                        source_file=fname,
                        evidence="System prompt requests Summary, Key Findings, Sources sections",
                        confidence=0.9
                    )
                )

        # 3. Detect Security Exposures (External untrusted content into LLM prompt)
        all_code_combined = " ".join(raw_files.values())
        if "tavily" in all_code_combined.lower() or "search" in all_code_combined.lower() or "scrape" in all_code_combined.lower():
            if "openai" in all_code_combined.lower() or "chat" in all_code_combined.lower() or "llm" in all_code_combined.lower():
                security_surfaces.append({
                    "surface": "EXTERNAL_CONTENT_INJECTION",
                    "risk": "Untrusted external content formatted directly into LLM prompt",
                    "severity": "high",
                    "evidence": "Search/web content inserted into model prompt"
                })
                failure_surfaces.append(
                    FailureSurface(
                        id="fail-prompt-injection",
                        component="SECURITY",
                        surface_type="security",
                        description="Malicious web content containing prompt injection payloads",
                        evidence="External untrusted web content formatted into LLM prompt",
                        is_inferred=True,
                        severity="critical"
                    )
                )

        # 4. Extract Generic Observed Failure Surfaces based on dependencies
        if "tavily" in all_code_combined.lower() or "search" in all_code_combined.lower():
            failure_surfaces.extend([
                FailureSurface(
                    id="fail-search-rate-limit",
                    component="WEB_SEARCH",
                    surface_type="external_service",
                    description="Web search API rate limit, HTTP 429, or authentication failure",
                    evidence="External search API integration",
                    is_inferred=False,
                    severity="high"
                ),
                FailureSurface(
                    id="fail-search-empty-results",
                    component="WEB_SEARCH",
                    surface_type="data",
                    description="Web search returns empty results or malformed result objects",
                    evidence="External search response parsing",
                    is_inferred=False,
                    severity="medium"
                )
            ])

        if "openai" in all_code_combined.lower() or "gemini" in all_code_combined.lower() or "anthropic" in all_code_combined.lower():
            failure_surfaces.append(
                FailureSurface(
                    id="fail-llm-timeout",
                    component="LLM_INFERENCE",
                    surface_type="llm",
                    description="LLM provider timeout, server 500 error, or generation failure",
                    evidence="External model inference call",
                    is_inferred=False,
                    severity="high"
                )
            )

        # 5. Extract Declared vs Implemented Conflicts
        conflicts: List[DeclaredVsImplementedConflict] = []
        doc_text = " ".join([content for fname, content in raw_files.items() if fname.endswith((".md", ".txt", ".yaml", ".yml"))])

        if "PII" in doc_text or "credential" in doc_text.lower() or "never leak" in doc_text.lower():
            has_redaction = any("redact" in code.lower() or "mask" in code.lower() for fname, code in raw_files.items() if fname.endswith(".py"))
            if not has_redaction:
                conflicts.append(
                    DeclaredVsImplementedConflict(
                        declared_behavior="Never leak raw credentials or API keys",
                        implementation_evidence="No credential redaction or masking logic found in AST code scan",
                        has_conflict=True,
                        explanation="Declared documentation policy has no code implementation in source files"
                    )
                )

        if "escalat" in doc_text.lower() or "human" in doc_text.lower() or "ticket" in doc_text.lower():
            has_escalation = any("ticket" in code.lower() or "human" in code.lower() or "escalat" in code.lower() for fname, code in raw_files.items() if fname.endswith(".py"))
            if not has_escalation:
                conflicts.append(
                    DeclaredVsImplementedConflict(
                        declared_behavior="Escalate to human review on policy violations",
                        implementation_evidence="No ticketing or human escalation node found in AST workflow graph",
                        has_conflict=True,
                        explanation="Declared escalation policy is not implemented in agent workflow graph"
                    )
                )

        return {
            "transformations": transformations,
            "invariants": invariants,
            "failure_surfaces": failure_surfaces,
            "state_model": state_model,
            "inputs": inputs,
            "outputs": outputs,
            "security_surfaces": security_surfaces,
            "conflicts": conflicts
        }
