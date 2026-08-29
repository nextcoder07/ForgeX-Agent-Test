"""
Pure Assembler Profile Builder Module.
Assembles structural facts, framework workflows, capability mappings, code invariants,
data transformations, and failure surfaces into a versioned AgentBehaviorProfile.
Never hardcodes default domain inputs, outputs, or state assumptions.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import Dict, List, Any, Optional
from app.models.agent_behavior import (
    AgentBehaviorProfile,
    WorkflowGraph,
    DataTransformation,
    CodeInvariant,
    FailureSurface,
    DeclaredVsImplementedConflict,
    ReadinessBreakdown,
    InterfaceContract,
    OutputContract,
)
from app.models.dependency_model import DetectedSecret


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class ProfileBuilder:
    @staticmethod
    def build_behavior_profile(
        agent_id: str,
        agent_name: str,
        domain: str,
        workflow_graph: WorkflowGraph,
        capabilities: List[str],
        external_calls: List[Dict[str, Any]],
        credential_references: List[DetectedSecret],
        transformations: List[DataTransformation],
        invariants: List[CodeInvariant],
        failure_surfaces: List[FailureSurface],
        state_model: Optional[Dict[str, Any]] = None,
        inputs: Optional[List[Dict[str, Any]]] = None,
        outputs: Optional[List[Dict[str, Any]]] = None,
        security_surfaces: Optional[List[Dict[str, Any]]] = None,
        decision_surfaces: Optional[List[Dict[str, Any]]] = None,
        side_effects: Optional[List[str]] = None,
        conflicts: Optional[List[DeclaredVsImplementedConflict]] = None,
        interface_contract: Optional[InterfaceContract] = None,
        output_contract: Optional[OutputContract] = None,
        dependency_requirements: Optional[List[Dict[str, Any]]] = None,
        agent_version_id: Optional[str] = None,
        analysis_run_id: Optional[str] = None
    ) -> AgentBehaviorProfile:
        """Pure assembler: aggregates extracted facts into versioned AgentBehaviorProfile."""

        # Lifecycle readiness during Intake Analysis:
        # Sandbox has not been built yet -> sandbox_ready = False
        # Execution is blocked until sandbox and credentials are valid -> execution_ready = False
        has_creds = len(credential_references) == 0

        cred_names = [c.name if hasattr(c, "name") else c.get("name", "") for c in credential_references]
        readiness = ReadinessBreakdown(
            analysis_ready=True,
            runtime_ready=True,
            dependencies_ready=True,
            credentials_ready=has_creds,
            sandbox_ready=False,
            execution_ready=False,
            blocked_reasons=[f"Missing required API credentials: {cred_names}"] if not has_creds else ["Sandbox environment not yet built"]
        )

        profile_id = f"abp-{uuid.uuid4().hex[:8]}"

        # Assemble comprehensive side effects
        assembled_side_effects = list(dict.fromkeys(
            (side_effects or []) +
            ([f"MODEL_INFERENCE: {c.get('class_name', 'LLM')}" for c in external_calls if "LLM" in c.get("capability", "")] or ["MODEL_INFERENCE: LLM"]) +
            ([f"FILESYSTEM_READ: {t.field}" for t in transformations if "pdf" in t.field or "file" in t.field] or []) +
            ([f"DATABASE_OPERATION: {c.get('class_name', 'SQL')}" for c in external_calls if "SQL" in c.get("capability", "")] or [])
        ))

        normalized_security = []
        for item in (security_surfaces or []):
            if isinstance(item, dict):
                norm = dict(item)
                sev = str(norm.get("severity", "")).upper()
                norm["severity"] = sev
                normalized_security.append(norm)
            else:
                normalized_security.append(item)

        return AgentBehaviorProfile(
            id=profile_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id or f"ver-{agent_id[:8]}",
            schema_version="v1",
            identity={
                "name": agent_name,
                "domain": domain,
                "entrypoint": workflow_graph.entrypoint
            },
            goal=f"Execute {domain} tasks using discovered workflow nodes and external capabilities.",
            interface_contract=interface_contract or InterfaceContract(
                entrypoint=workflow_graph.entrypoint,
                interface_type="CLI" if (workflow_graph.entrypoint and workflow_graph.entrypoint.endswith(".py")) else "UNKNOWN"
            ),
            output_contract=output_contract or OutputContract(
                stdout_format="TEXT",
                exit_codes={0: "SUCCESS"}
            ),
            dependency_requirements=dependency_requirements or [],
            workflow_graph=workflow_graph,
            inputs=inputs or [],
            outputs=outputs or [],
            state_model=state_model or {},
            external_calls=external_calls,
            capabilities=capabilities,
            data_transformations=transformations,
            invariants=invariants,
            failure_surfaces=failure_surfaces,
            security_surfaces=normalized_security,
            decision_surfaces=decision_surfaces or [],
            side_effects=assembled_side_effects,
            declared_behaviors=[f"Capability: {cap}" for cap in capabilities],
            observed_behaviors=[f"Workflow graph with {len(workflow_graph.nodes)} nodes"],
            conflicts=conflicts or [],
            readiness=readiness,
            confidence_score=0.98 if capabilities or workflow_graph.nodes else 0.5,
            analysis_run_id=analysis_run_id or f"run-{uuid.uuid4().hex[:6]}",
            created_at=_now()
        )
