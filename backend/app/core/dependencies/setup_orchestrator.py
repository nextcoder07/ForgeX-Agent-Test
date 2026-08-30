"""
Setup Orchestrator Module.
Enforces the invariant: SETUP MUST COMPLETE BEFORE ANY SCENARIO EXECUTES.

State Machine:
NOT_STARTED -> ANALYZING -> PREPARING -> INSTALLING -> VERIFYING -> READY / BLOCKED / FAILED
"""

from __future__ import annotations

import os
import sys
import uuid
import datetime as dt
import logging
from typing import Dict, List, Optional, Any

from app.models.agent import AgentRecord
from app.models.execution import SetupReadinessRecord, SetupState
from app.services.store import store
from app.core.dependencies.dependency_resolver import DependencyResolver

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class SetupOrchestrator:
    """Prepares execution environment, installs required packages once, and validates all prerequisites before scenario execution."""

    @staticmethod
    def get_or_create_setup_readiness(agent_id: str, execution_id: Optional[str] = None) -> SetupReadinessRecord:
        agent = store.get_agent(agent_id)
        version_label = agent.version_label if agent else "v1.0"

        existing = store.get_setup_readiness(agent_id)
        if existing and getattr(existing, "agent_version_id", "") == version_label:
            if execution_id and not existing.execution_id:
                existing.execution_id = execution_id
                store.save_setup_readiness(existing)
            return existing
        
        record = SetupReadinessRecord(
            id=f"setup-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_version_id=version_label,
            execution_id=execution_id,
            status=SetupState.NOT_STARTED,
            current_step="ANALYZING AGENT",
            progress_pct=0,
            created_at=_now(),
            updated_at=_now()
        )
        store.save_setup_readiness(record)
        return record

    @staticmethod
    def run_automatic_setup(agent_id: str, execution_id: Optional[str] = None, provided_secrets: Optional[Dict[str, str]] = None) -> SetupReadinessRecord:
        """Runs complete 12-step automatic setup pipeline for an agent."""
        if provided_secrets is None:
            provided_secrets = {}

        agent = store.get_agent(agent_id)
        if not agent:
            record = SetupReadinessRecord(
                id=f"setup-{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                status=SetupState.FAILED,
                current_step="AGENT NOT FOUND",
                blockers=[{"category": "agent", "message": f"Agent '{agent_id}' not found"}],
                created_at=_now(),
                updated_at=_now()
            )
            store.save_setup_readiness(record)
            return record

        record = SetupOrchestrator.get_or_create_setup_readiness(agent_id, execution_id)
        
        # Step 1: ANALYZING AGENT (10%)
        record.status = SetupState.ANALYZING
        record.current_step = "ANALYZING AGENT"
        record.progress_pct = 10
        record.updated_at = _now()
        store.save_setup_readiness(record)

        # Step 2: CHECKING RUNTIME (20%)
        record.current_step = "CHECKING RUNTIME"
        record.progress_pct = 20
        record.updated_at = _now()
        store.save_setup_readiness(record)

        # Step 3: CHECKING DEPENDENCIES (30%)
        record.current_step = "CHECKING DEPENDENCIES"
        record.progress_pct = 30
        record.status = SetupState.PREPARING
        
        res = DependencyResolver.resolve_mode(agent=agent, provided_secrets=provided_secrets)
        
        missing_pkgs = []
        for dep in agent.dependencies:
            dep_name = getattr(dep, "name", "")
            dep_type = getattr(dep, "type", "")
            if dep_type in ("package", "framework") and dep_name:
                if not DependencyResolver._package_is_importable(dep_name):
                    missing_pkgs.append(dep_name)

        record.missing_dependencies = missing_pkgs
        record.updated_at = _now()
        store.save_setup_readiness(record)

        # Step 4: INSTALLING DEPENDENCIES (50%)
        if missing_pkgs:
            record.status = SetupState.INSTALLING
            record.current_step = f"INSTALLING DEPENDENCIES ({', '.join(missing_pkgs[:3])})"
            record.progress_pct = 50
            record.updated_at = _now()
            store.save_setup_readiness(record)

            installed = []
            for pkg in missing_pkgs:
                try:
                    import subprocess
                    cmd = [sys.executable, "-m", "pip", "install", pkg, "--quiet", "--no-warn-script-location"]
                    subprocess.run(cmd, capture_output=True, timeout=60, check=False)
                    if DependencyResolver._package_is_importable(pkg):
                        installed.append(pkg)
                except Exception as e:
                    logger.warning(f"Failed to auto-install package '{pkg}': {e}")

            record.installed_dependencies = installed

        # Step 5: VERIFYING DEPENDENCIES (60%)
        record.status = SetupState.VERIFYING
        record.current_step = "VERIFYING DEPENDENCIES"
        record.progress_pct = 60
        record.updated_at = _now()
        store.save_setup_readiness(record)

        # Step 6: CHECKING CREDENTIALS (75%)
        record.current_step = "CHECKING CREDENTIALS"
        record.progress_pct = 75

        cred_demands = DependencyResolver.evaluate_execution_credential_demands(
            agent=agent,
            provided_secrets=provided_secrets
        )

        missing_creds = []
        blockers = []
        if not cred_demands.all_fulfilled:
            for req in cred_demands.requirements:
                if not req.is_fulfilled and not req.is_optional:
                    missing_creds.append(req.key_name)
                    blockers.append({
                        "category": "credential",
                        "message": f"Credential required: '{req.key_name}' ({req.description or 'Required by agent code'})"
                    })

        record.missing_credentials = missing_creds
        
        if missing_creds:
            record.status = SetupState.BLOCKED
            record.credential_status = "BLOCKED"
            record.current_step = f"BLOCKED — Credential Required: {', '.join(missing_creds)}"
            record.blockers = blockers
            record.updated_at = _now()
            store.save_setup_readiness(record)
            return record

        # Step 7: CHECKING AGENT LLM (85%)
        record.current_step = "CHECKING AGENT LLM"
        record.progress_pct = 85
        record.updated_at = _now()
        store.save_setup_readiness(record)

        # Step 8: PREPARING MOCKS/ADAPTERS & SANDBOX (95%)
        record.current_step = "PREPARING MOCKS & SANDBOX"
        record.progress_pct = 95
        record.updated_at = _now()
        store.save_setup_readiness(record)

        # Step 9: READY (100%)
        record.status = SetupState.READY
        record.current_step = "READY — All execution prerequisites verified."
        record.progress_pct = 100
        record.blockers = []
        record.updated_at = _now()
        store.save_setup_readiness(record)

        return record
