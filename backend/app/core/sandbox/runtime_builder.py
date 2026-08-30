"""
Runtime Builder Module.
Creates isolated runtime execution workspaces, mounts agent source artifacts,
stages scenario inputs, provisions dependencies, verifies imports, and redacts secrets.
"""

from __future__ import annotations

import os
import sys
import tempfile
import datetime as dt
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.execution_manifest import ExecutionManifest
from app.core.dependencies.runtime_smoke_tester import RuntimeSmokeTester
from app.core.sandbox.dependency_installer import ensure_agent_dependencies, is_module_installed


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RuntimeEnvironmentRecord(BaseModel):
    id: str
    agent_id: str
    agent_version_id: str
    artifact_hash: str
    workspace_dir: str
    python_executable: str = sys.executable
    sanitized_env: Dict[str, str] = Field(default_factory=dict)
    verified_packages: List[str] = Field(default_factory=list)
    status: str = "READY"  # "READY", "PROVISIONING", "BLOCKED", "FAILED"
    blockers: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class RuntimeBuilder:
    """Manages creation, dependency provisioning, and cleanup of isolated agent execution workspaces."""

    @staticmethod
    def provision_runtime_environment(
        manifest: ExecutionManifest,
        code_content: str,
        provided_secrets: Optional[Dict[str, str]] = None
    ) -> RuntimeEnvironmentRecord:
        """Provisions an isolated execution workspace and verifies runtime readiness."""
        provided_secrets = provided_secrets or {}
        agent_id = manifest.agent.agent_id
        version_id = manifest.agent.agent_version_id
        art_hash = manifest.agent.artifact_hash
        env_id = f"rt-{agent_id}-{version_id}-{art_hash}"

        blockers: List[str] = []
        verified_packages: List[str] = []

        # 1. Check Required Credentials
        for cred in manifest.credentials:
            if cred.required and cred.status not in ("AVAILABLE", "PLATFORM_PROVIDED"):
                # Check environment
                if not (os.getenv(cred.key_name) or provided_secrets.get(cred.key_name)):
                    blockers.append(f"Missing required credential: {cred.key_name}")

        # 2. Check Package Import Specs
        for dep in manifest.dependencies:
            pkg = dep.package_name
            imp = dep.import_name
            if not is_module_installed(imp) and not RuntimeSmokeTester._package_is_importable(pkg):
                blockers.append(f"Missing importable package: {pkg} (import name: '{imp}')")
            else:
                verified_packages.append(pkg)

        status = "BLOCKED" if blockers else "READY"

        # Build Sanitized Environment Dictionary
        sanitized_env = dict(os.environ)
        # Strip Platform System Secrets
        for sec in ("SUPABASE_KEY", "SUPABASE_URL", "DATABASE_URL", "JWT_SECRET", "SECRET_KEY"):
            sanitized_env.pop(sec, None)

        sanitized_env["PYTHONIOENCODING"] = "utf-8"
        sanitized_env["PYTHONUTF8"] = "1"

        # Inject Provided User Secrets
        for k, v in provided_secrets.items():
            if v and not v.startswith("your_"):
                sanitized_env[k] = v

        temp_dir = tempfile.mkdtemp(prefix=f"sandbox_rt_{agent_id[:8]}_")

        return RuntimeEnvironmentRecord(
            id=env_id,
            agent_id=agent_id,
            agent_version_id=version_id,
            artifact_hash=art_hash,
            workspace_dir=temp_dir,
            python_executable=sys.executable,
            sanitized_env=sanitized_env,
            verified_packages=verified_packages,
            status=status,
            blockers=blockers
        )
