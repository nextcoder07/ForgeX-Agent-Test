"""
Authoritative Evidence Packet Builder.
Assembles raw source files, AST facts, framework constructs, CLI arguments,
functions, LLM constructors, side-effects, security surfaces, decision surfaces,
output structures, and call graphs into an indexed, traceable EvidencePacket.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List
from app.core.intake.evidence_models import (
    EvidencePacket,
    EvidenceItem,
    EvidenceCategory,
    CertaintyLevel,
    ProvenanceType,
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

        # 1. Functions & Signatures
        functions = StaticCodeExtractor.extract_functions(ast_trees, artifact_id)

        # 2. CLI Arguments
        cli_options = StaticCodeExtractor.extract_cli_arguments(ast_trees, artifact_id)

        # 3. LLM Client Constructors
        llm_constructors = StaticCodeExtractor.extract_llm_constructors(ast_trees, artifact_id)

        # 4. AST Side-Effects (Filesystem, Database, Subprocess, Network)
        side_effects = StaticCodeExtractor.extract_side_effects(ast_trees, artifact_id)

        # 5. Security Surfaces (Strictly derived from AST side effects & CLI inputs)
        security_surfaces = StaticCodeExtractor.extract_security_surfaces(
            ast_trees=ast_trees,
            side_effects=side_effects,
            cli_options=cli_options,
            artifact_id=artifact_id
        )

        # 6. Dedicated Decision Surfaces (Scoring, Recommendations, Hiring, Approvals)
        decision_surfaces = StaticCodeExtractor.extract_decision_surfaces(
            ast_trees=ast_trees,
            source_files=source_files,
            artifact_id=artifact_id
        )

        # 7. Structured Output Schemas
        output_structures = StaticCodeExtractor.extract_output_structures(
            ast_trees=ast_trees,
            source_files=source_files,
            artifact_id=artifact_id
        )

        # 8. Static Call Graph & Conditional Branches
        call_graph = StaticCodeExtractor.extract_static_call_graph(ast_trees)
        conditional_branches = StaticCodeExtractor.extract_conditional_branches(ast_trees, artifact_id)

        # 9. Framework Native Constructs
        fw_result = FrameworkRegistry.detect_framework(ast_trees, artifact_id)

        # 10. Package Dependencies & Environment Secrets
        combined_code = "\n".join(source_files.values())
        package_deps = DependencyDetector.detect_runtime_packages(combined_code, source_files)
        env_secrets = DependencyDetector.detect_environment_secrets(combined_code, source_files)

        # 11. Aggregate Evidence Items
        evidence_items: List[EvidenceItem] = []
        evidence_items.extend(fw_result.evidence_items)

        # Function Evidence Items
        for fn in functions:
            evidence_items.append(EvidenceItem(
                id=fn.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.FUNCTION_DEF,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"Function: {fn.name}({', '.join(fn.arguments)})",
                source_file=fn.source_file,
                line_number=fn.line_number,
                attributes={"arguments": fn.arguments, "decorators": fn.decorators}
            ))

        # CLI Option Evidence Items
        for opt in cli_options:
            evidence_items.append(EvidenceItem(
                id=opt.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.CLI_ARGUMENT,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"CLI Argument: {', '.join(opt.flags)}",
                source_file=opt.source_file,
                line_number=opt.line_number,
                attributes={"flags": opt.flags, "type": opt.argument_type, "required": opt.required}
            ))

        # LLM Constructor Evidence Items
        for llm in llm_constructors:
            evidence_items.append(EvidenceItem(
                id=llm.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.LLM_CONSTRUCTOR,
                certainty=llm.model_certainty,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"LLM Constructor: {llm.source_class}(model='{llm.model_name}')",
                source_file=llm.source_file,
                line_number=llm.line_number,
                attributes={"provider": llm.provider, "model": llm.model_name, "is_dynamic": llm.is_dynamic_model}
            ))

        # Side Effect Evidence Items
        for se in side_effects:
            cat = EvidenceCategory.FILESYSTEM_OPERATION if se.side_effect_type.value == "FILESYSTEM" else (
                EvidenceCategory.DATABASE_OPERATION if se.side_effect_type.value == "DATABASE" else (
                    EvidenceCategory.SUBPROCESS_EXECUTION if se.side_effect_type.value == "SUBPROCESS" else EvidenceCategory.NETWORK_CALL
                )
            )
            evidence_items.append(EvidenceItem(
                id=se.id,
                artifact_id=artifact_id,
                category=cat,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"Side Effect: {se.side_effect_type.value} ({se.operation}) on {se.target}",
                source_file=se.source_file,
                line_number=se.line_number,
                attributes={"target": se.target, "operation": se.operation, "evidence": se.evidence}
            ))

        # Security Surface Evidence Items
        for sec in security_surfaces:
            evidence_items.append(EvidenceItem(
                id=sec.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.SECURITY_SURFACE,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"Security Surface: {sec.surface_type} ({sec.severity})",
                source_file=sec.source_file,
                line_number=sec.line_number,
                attributes={"type": sec.surface_type, "severity": sec.severity, "description": sec.description},
                supporting_evidence_ids=sec.supporting_evidence_ids
            ))

        # Decision Surface Evidence Items
        for dec in decision_surfaces:
            evidence_items.append(EvidenceItem(
                id=dec.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.DECISION_SURFACE,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"Decision Surface: {dec.decision_type} -> {dec.impact}",
                source_file=dec.source_file,
                line_number=dec.line_number,
                attributes={"type": dec.decision_type, "impact": dec.impact, "options": dec.recommendation_options}
            ))

        # Output Structure Evidence Items
        for out in output_structures:
            evidence_items.append(EvidenceItem(
                id=out.id,
                artifact_id=artifact_id,
                category=EvidenceCategory.OUTPUT_STRUCTURE,
                certainty=CertaintyLevel.FACT if out.provenance == ProvenanceType.CODE_PROVEN else CertaintyLevel.INFERRED,
                provenance=out.provenance,
                name=f"Output Field: {out.field_name} ({out.field_type})",
                source_file=out.source_file,
                line_number=out.line_number,
                attributes={"field": out.field_name, "type": out.field_type, "provenance": out.provenance.value}
            ))

        # Package Dependencies
        req_file = next((f for f in source_files.keys() if f.endswith("requirements.txt") or f.endswith("pyproject.toml") or f.endswith("Pipfile")), None)
        for idx, dep in enumerate(package_deps):
            detected_src = getattr(dep, "detected_from", "")
            dep_source_file = detected_src if detected_src in source_files else (req_file or entrypoint)
            evidence_items.append(EvidenceItem(
                id=f"ev-dep-{idx+1}",
                artifact_id=artifact_id,
                category=EvidenceCategory.IMPORT,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.DOC_DECLARED if "requirements" in getattr(dep, "detected_from", "") or req_file else ProvenanceType.CODE_PROVEN,
                name=f"Package Dependency: {dep.name}",
                source_file=dep_source_file,
                line_number=1,
                attributes={"package": dep.name, "type": dep.type}
            ))

        # Environment Secrets
        env_file = next((f for f in source_files.keys() if f.endswith(".env") or f.endswith(".env.example")), None) or entrypoint
        for idx, sec_var in enumerate(env_secrets):
            sec_name = sec_var.name if hasattr(sec_var, "name") else str(sec_var)
            evidence_items.append(EvidenceItem(
                id=f"ev-env-{idx+1}",
                artifact_id=artifact_id,
                category=EvidenceCategory.ENVIRONMENT_VARIABLE,
                certainty=CertaintyLevel.FACT,
                provenance=ProvenanceType.CODE_PROVEN,
                name=f"Environment Variable: {sec_name}",
                source_file=env_file,
                line_number=1,
                attributes={"variable": sec_name}
            ))

        return EvidencePacket(
            artifact_id=artifact_id,
            entrypoint=entrypoint,
            source_files=source_files,
            evidence_items=evidence_items,
            functions=functions,
            cli_arguments=cli_options,
            llm_constructors=llm_constructors,
            security_surfaces=security_surfaces,
            decision_surfaces=decision_surfaces,
            output_structures=output_structures,
            call_graph=call_graph,
            conditional_branches=conditional_branches,
            framework_constructs=fw_result.constructs,
            detected_packages=[d.name for d in package_deps],
            environment_variables=[s.name if hasattr(s, "name") else str(s) for s in env_secrets],
            side_effects=side_effects
        )
