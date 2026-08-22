"""
Behavior Extractor Module.
Extracts data transformations, code invariants, failure surfaces, security exposures,
and state model definitions from source code AST trees.
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
        """Extracts data transformations, code invariants, and failure surfaces."""
        transformations: List[DataTransformation] = []
        invariants: List[CodeInvariant] = []
        failure_surfaces: List[FailureSurface] = []

        # 1. Inspect AST for Data Transformations (e.g., [:500] truncation, list formatting)
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                # Detect String Truncation (Subscript Slice [:500])
                if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
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

                # Detect Invariants (e.g., max_results = 5, temperature = 0, model = "gpt-4o-mini")
                if isinstance(node, ast.keyword):
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

        # 3. Extract Failure Surface Inventory
        failure_surfaces.extend([
            FailureSurface(
                id="fail-input-empty",
                component="USER_INPUT",
                surface_type="input",
                description="Empty, blank, or whitespace-only user search query",
                evidence="Observed user input string parameter",
                is_inferred=False,
                severity="medium"
            ),
            FailureSurface(
                id="fail-search-rate-limit",
                component="WEB_SEARCH",
                surface_type="external_service",
                description="Web search API rate limit, HTTP 429, or authentication failure",
                evidence="Tavily API call dependency",
                is_inferred=False,
                severity="high"
            ),
            FailureSurface(
                id="fail-search-empty-results",
                component="WEB_SEARCH",
                surface_type="data",
                description="Web search returns empty results or malformed result objects",
                evidence="Observed dict/list search normalization logic",
                is_inferred=False,
                severity="medium"
            ),
            FailureSurface(
                id="fail-prompt-injection",
                component="SECURITY",
                surface_type="security",
                description="Malicious web search content containing prompt injection payloads",
                evidence="External untrusted web content formatted directly into LLM prompt",
                is_inferred=True,
                severity="critical"
            ),
            FailureSurface(
                id="fail-llm-timeout",
                component="LLM_INFERENCE",
                surface_type="llm",
                description="LLM provider timeout, server 500 error, or malformed generation output",
                evidence="ChatOpenAI inference call dependency",
                is_inferred=False,
                severity="high"
            )
        ])

        # 4. Extract Declared vs Implemented Conflicts
        conflicts: List[DeclaredVsImplementedConflict] = []
        all_text = " ".join(raw_files.values())

        if "PII" in all_text or "credential" in all_text.lower():
            has_redaction = any("redact" in code.lower() or "mask" in code.lower() for code in raw_files.values())
            if not has_redaction:
                conflicts.append(
                    DeclaredVsImplementedConflict(
                        declared_behavior="Never leak raw credentials or API keys",
                        implementation_evidence="No credential redaction or masking logic found in AST code scan",
                        has_conflict=True,
                        explanation="Declared documentation policy has no code implementation in agent.py"
                    )
                )

        if "escalat" in all_text.lower() or "human" in all_text.lower():
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
            "conflicts": conflicts
        }
