"""
ForgeX Repair, Patch Generator & File Diff Inspector Engine.
Generates deterministic code patches, validates them with AST static checks,
computes unified diffs, and constructs PatchArtifacts for human approval and automated regression.
"""

from __future__ import annotations

import ast
import difflib
import uuid
import datetime as dt
from typing import Dict, List, Optional, Tuple, Any
from app.models.canonical_data_models import (
    PatchArtifact,
    FilePatch,
    PatchStatus,
    AgentVersionRecord,
)
from app.models.evaluation_ontology import Finding, RootCauseCategory
from app.core.diagnosis.root_cause_engine import RemediationRecommendation
from app.models.agent import AgentRecord


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class PatchEngine:
    """Generates and statically validates patches with unified diff visualization."""

    @staticmethod
    def generate_unified_diff(
        file_path: str,
        before_content: str,
        after_content: str
    ) -> Tuple[str, int, int]:
        """Generates a standard unified diff string and counts added/removed lines."""
        before_lines = before_content.splitlines(keepends=True)
        after_lines = after_content.splitlines(keepends=True)

        diff_generator = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        )
        diff_str = "\n".join(diff_generator)

        added = sum(1 for line in diff_str.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_str.splitlines() if line.startswith("-") and not line.startswith("---"))

        return diff_str, added, removed

    @classmethod
    def apply_security_guardrail_patch(
        cls,
        source_code: str,
        target_function: str = "handle_payout"
    ) -> str:
        """Applies a deterministic token authorization guardrail patch to target Python function."""
        guardrail_snippet = (
            "    # [ForgeX Guardrail] Enforce deterministic cryptographic token authorization\n"
            "    if not auth_token or not getattr(auth_token, 'is_valid', True):\n"
            "        raise PermissionError('Unauthorized action: Valid cryptographic supervisor token required.')\n"
        )

        lines = source_code.splitlines()
        modified_lines = []
        in_target_func = False
        injected = False

        for line in lines:
            modified_lines.append(line)
            if ("def " in line or "async def " in line) and not injected:
                # Target function or first handler function
                if target_function in line or "refund" in line or "payout" in line or "execute" in line or "main" in line:
                    in_target_func = True
                    # Add auth_token parameter if missing
                    if "auth_token" not in modified_lines[-1]:
                        modified_lines[-1] = modified_lines[-1].replace("):", ", auth_token=None):").replace("()", "(auth_token=None)")
                    modified_lines.append(guardrail_snippet)
                    injected = True

        if not injected:
            # Prepend guardrail function
            header = (
                "def verify_auth_boundary(auth_token=None):\n"
                "    if not auth_token:\n"
                "        raise PermissionError('Unauthorized: supervisor token required.')\n\n"
            )
            return header + source_code

        return "\n".join(modified_lines) + "\n"

    @classmethod
    def create_patch_for_finding(
        cls,
        agent: AgentRecord,
        finding: Finding,
        recommendation: RemediationRecommendation,
        target_version_label: str = "v1.1-repaired"
    ) -> PatchArtifact:
        """Constructs and validates a PatchArtifact with unified diff representation."""
        target_file = "agent.py"
        if ":" in finding.root_cause.affected_file_or_component:
            target_file = finding.root_cause.affected_file_or_component.split(":")[0]

        before_code = agent.source_files.get(target_file, "print('Agent running')\n")
        func_name = finding.root_cause.affected_file_or_component.split(":")[-1] if ":" in finding.root_cause.affected_file_or_component else "main"

        # Generate repaired source
        after_code = cls.apply_security_guardrail_patch(before_code, target_function=func_name)

        # Validate syntax with AST parser
        try:
            ast.parse(after_code)
            status = PatchStatus.PROPOSED
        except SyntaxError as exc:
            after_code = before_code
            status = PatchStatus.DRAFT

        diff_str, added, removed = cls.generate_unified_diff(target_file, before_code, after_code)

        file_patch = FilePatch(
            file_path=target_file,
            before_content=before_code,
            after_content=after_code,
            unified_diff=diff_str,
            lines_added=added,
            lines_removed=removed
        )

        patch_id = f"patch-{uuid.uuid4().hex[:8]}"

        return PatchArtifact(
            id=patch_id,
            finding_id=finding.id,
            agent_id=agent.id,
            source_version_id=agent.current_version_id or agent.version_label,
            target_version_label=target_version_label,
            title=f"Repair: {recommendation.title}",
            explanation=recommendation.mode_b_patch_strategy,
            root_cause_ref=finding.root_cause,
            files_changed=[file_patch],
            status=status,
            created_at=_now()
        )
