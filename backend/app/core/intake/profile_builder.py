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
        conflicts: Optional[List[DeclaredVsImplementedConflict]] = None,
        agent_version_id: Optional[str] = None,
        analysis_run_id: Optional[str] = None
    ) -> AgentBehaviorProfile:
        """Pure assembler: aggregates extracted facts into versioned AgentBehaviorProfile."""

        # Lifecycle readiness during Intake Analysis:
        # Sandbox has not been built yet -> sandbox_ready = False
        # Execution is blocked until sandbox and credentials are valid -> execution_ready = False
        has_creds = len(credential_references) == 0

        readiness = ReadinessBreakdown(
            analysis_ready=True,
            runtime_ready=True,
            dependencies_ready=True,
            credentials_ready=has_creds,
            sandbox_ready=False,
            execution_ready=False,
            blocked_reasons=[f"Missing required API credentials: {[c.name for c in credential_references]}"] if not has_creds else ["Sandbox environment not yet built"]
        )

        profile_id = f"abp-{uuid.uuid4().hex[:8]}"

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
            workflow_graph=workflow_graph,
            inputs=inputs or [],
            outputs=outputs or [],
            state_model=state_model or {},
            external_calls=external_calls,
            capabilities=capabilities,
            data_transformations=transformations,
            invariants=invariants,
            failure_surfaces=failure_surfaces,
            security_surfaces=security_surfaces or [],
            side_effects=[f"External service call to {c.get('capability', 'API')}" for c in external_calls],
            declared_behaviors=[f"Capability: {cap}" for cap in capabilities],
            observed_behaviors=[f"Workflow graph with {len(workflow_graph.nodes)} nodes"],
            conflicts=conflicts or [],
            readiness=readiness,
            confidence_score=0.98 if capabilities or workflow_graph.nodes else 0.5,
            analysis_run_id=analysis_run_id or f"run-{uuid.uuid4().hex[:6]}",
            created_at=_now()
        )
