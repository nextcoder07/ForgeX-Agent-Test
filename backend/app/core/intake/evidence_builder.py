"""
Authoritative Evidence Packet Builder.
Assembles raw source files, AST facts, framework constructs, CLI arguments,
LLM constructors, security surfaces, and call graphs into an indexed, traceable EvidencePacket.
"""

from __future__ import annotations

import ast
import hashlib
from typing import Any, Dict, List
from app.core.intake.evidence_models import (
    EvidencePacket,
    EvidenceItem,
    EvidenceCategory,
    CertaintyLevel,
)
from app.core.intake.static_extractor import StaticCodeExtractor
from app.core.intake.framework_detectors import FrameworkRegistry
from app.core.intake.dependency_detector import DependencyDetector


class EvidencePacketBuilder:
    @staticmethod
    def build_packet(
        source_files: Dict[str, str],
        artifact_id: str,
        entrypoint: str = "agent.py"
    ) -> EvidencePacket:
        """Constructs an exhaustive, canonical EvidencePacket from source files."""
        ast_trees: Dict[str, ast.AST] = {}
        for fname, content in source_files.items():
            if fname.lower().endswith(".py"):
                try:
                    ast_trees[fname] = ast.parse(content)
                except Exception:
                    pass

        # 1. Framework Native Constructs
        fw_result = FrameworkRegistry.detect_framework(ast_trees, artifact_id)

        # 2. CLI Arguments
        cli_options = StaticCodeExtractor.extract_cli_arguments(ast_trees, artifact_id)

        # 3. LLM Constructors
        llm_constructors = StaticCodeExtractor.extract_llm_constructors(ast_trees, artifact_id)

        # 4. Security Surfaces
        security_surfaces = StaticCodeExtractor.extract_security_surfaces(ast_trees, source_files, cli_options)

        # 5. Static Call Graph
        call_graph = StaticCodeExtractor.extract_static_call_graph(ast_trees)

        # 6. Package Dependencies & Environment Variables
        combined_code = "\n".join(source_files.values())
        package_deps = DependencyDetector.detect_runtime_packages(combined_code, source_files)
        env_secrets = DependencyDetector.detect_environment_secrets(combined_code, source_files)

        # 7. Aggregate Evidence Items
        evidence_items: List[EvidenceItem] = []
        evidence_items.extend(fw_result.evidence_items)

        # CLI evidence items
        for opt in cli_options:
            evidence_items.append(EvidenceItem(
                id=opt.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.CLI_ARGUMENT,
                certainty=CertaintyLevel.FACT,
                name=f"CLI Argument: {', '.join(opt.flags)}",
                source_file=opt.source_file,
                line_number=opt.line_number,
                attributes={"flags": opt.flags, "type": opt.argument_type, "required": opt.required}
            ))

        # LLM evidence items
        for llm in llm_constructors:
            evidence_items.append(EvidenceItem(
                id=llm.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.LLM_CONSTRUCTOR,
                certainty=CertaintyLevel.FACT,
                name=f"LLM Constructor: {llm.source_class}(model='{llm.model_name}')",
                source_file=llm.source_file,
                line_number=llm.line_number,
                attributes={"provider": llm.provider, "model": llm.model_name, "temp": llm.temperature}
            ))

        # Security evidence items
        for sec in security_surfaces:
            evidence_items.append(EvidenceItem(
                id=sec.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.SECURITY_SURFACE,
                certainty=CertaintyLevel.FACT,
                name=f"Security Surface: {sec.surface_type} ({sec.severity})",
                source_file=sec.source_file,
                line_number=sec.line_number,
                attributes={"type": sec.surface_type, "severity": sec.severity, "description": sec.description}
            ))

        # Dependencies
        for idx, dep in enumerate(package_deps):
            evidence_items.append(EvidenceItem(
                id=f"ev-dep-{idx+1}",
                artifact_id=artifact_id,
                category=EvidenceCategory.IMPORT,
                certainty=CertaintyLevel.FACT,
                name=f"Package Dependency: {dep.name}",
                source_file="requirements.txt",
                line_number=1,
                attributes={"package": dep.name, "type": dep.type}
            ))

        # Build packet
        return EvidencePacket(
            artifact_id=artifact_id,
            entrypoint=entrypoint,
            source_files=source_files,
            evidence_items=evidence_items,
            cli_arguments=cli_options,
            llm_constructors=llm_constructors,
            security_surfaces=security_surfaces,
            call_graph=call_graph,
            framework_constructs=fw_result.constructs,
            detected_packages=[d.name for d in package_deps],
            environment_variables=[s.name for s in env_secrets],
            side_effects=[]
        )
