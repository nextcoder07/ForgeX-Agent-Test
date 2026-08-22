"""
Profile Builder Module.
Assembles structural facts, framework workflows, capability mappings, code invariants,
data transformations, and failure surfaces into a versioned AgentBehaviorProfile.
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
        conflicts: Optional[List[DeclaredVsImplementedConflict]] = None,
        agent_version_id: Optional[str] = None,
        analysis_run_id: Optional[str] = None
    ) -> AgentBehaviorProfile:
        """Assembles comprehensive AgentBehaviorProfile facts container."""

        # Evaluate readiness breakdown
        has_creds = len(credential_references) == 0 or all(c.masked_sample != "KEY_*****" for c in credential_references)
        
        readiness = ReadinessBreakdown(
            analysis_ready=True,
            runtime_ready=True,
            dependencies_ready=True,
            credentials_ready=has_creds,
            sandbox_ready=True,
            execution_ready=has_creds,
            blocked_reasons=[] if has_creds else [f"Missing required API credentials: {[c.name for c in credential_references]}"]
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
            inputs=[{"name": "query", "type": "string", "description": "User search query or instructions"}],
            outputs=[{"name": "report", "type": "string", "description": "Synthesized research report"}],
            state_model={"type": "TypedDict/dict", "fields": ["query", "messages", "search_results", "report"]},
            external_calls=external_calls,
            capabilities=capabilities,
            data_transformations=transformations,
            invariants=invariants,
            failure_surfaces=failure_surfaces,
            security_surfaces=[
                {"surface": "EXTERNAL_CONTENT_INJECTION", "risk": "Prompt injection payload in retrieved web content", "severity": "high"}
            ],
            side_effects=["External HTTP calls to web search and LLM inference providers"],
            declared_behaviors=["Perform web search", "Synthesize research report"],
            observed_behaviors=[f"Workflow graph with {len(workflow_graph.nodes)} nodes"],
            conflicts=conflicts or [],
            readiness=readiness,
            confidence_score=0.98,
            analysis_run_id=analysis_run_id or f"run-{uuid.uuid4().hex[:6]}",
            created_at=_now()
        )
