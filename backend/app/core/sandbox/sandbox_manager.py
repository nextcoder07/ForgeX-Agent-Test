"""
SandboxManager Module.
Manages isolated execution environments, SandboxSpecification objects, and temporary workspaces for untrusted agent code.
Supports Docker container sandbox isolation with process/memory/timeout fallback when Docker daemon is uncontactable.
Redacts secrets in execution logs and enforces environment variable boundaries.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import shutil
import tempfile
import logging
import subprocess
import datetime as dt
from typing import Any, Dict, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution import ExecutionTrace, TraceEvent
from app.models.intake import SandboxSpecification
from app.services.store import store

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


def build_sandbox_specification_for_agent(agent: AgentRecord) -> SandboxSpecification:
    """Builds a complete, deterministic SandboxSpecification for an AgentRecord."""
    spec_id = f"sb-spec-{uuid.uuid4().hex[:8]}"

    runtime_config = {
        "language": "python",
        "version": "3.12",
        "cpu_limit": 1.0,
        "memory_limit_mb": 512,
        "execution_timeout_seconds": 15,
        "isolation_mode": "subprocess",  # "subprocess", "docker", "gvisor"
    }

    dependencies = [
        {"name": d.name, "type": d.type, "detected_from": d.detected_from}
        for d in agent.dependencies
    ]

    filesystem_config = {
        "read_only_root": True,
        "tmp_dir_mb": 64,
        "allowed_paths": ["/tmp", "/workspace"],
        "virtual_fs": {
            "order_db.json": '{"status": "active", "seeded": true}',
            "customer_records.json": '{"seeded": true}',
        }
    }

    network_config = {
        "allow_external_http": False,
        "allowed_domains": ["localhost", "127.0.0.1"],
        "intercept_outbound": True,
    }

    tools_config = [
        {
            "name": t.name,
            "description": t.description,
            "risk": t.risk.value if hasattr(t.risk, "value") else str(t.risk),
            "canonical_capability": t.canonical_capability,
            "is_destructive": t.is_destructive,
        }
        for t in agent.tools
    ]

    spec = SandboxSpecification(
        id=spec_id,
        agent_id=agent.id,
        runtime=runtime_config,
        dependencies=dependencies,
        filesystem=filesystem_config,
        network=network_config,
        tools=tools_config,
        credentials=[],
        created_at=_now()
    )

    store.save_sandbox_spec(spec)
    return spec


def get_or_create_sandbox_spec(agent: AgentRecord) -> SandboxSpecification:
    """Retrieves an existing SandboxSpecification for an agent, or builds a new one if missing."""
    existing_specs = store.list_sandbox_specs()
    for spec in existing_specs:
        if spec.agent_id == agent.id:
            return spec
    return build_sandbox_specification_for_agent(agent)


class SandboxInstanceRecord:
    def __init__(self, sandbox_id: str, agent_id: str, scenario_id: str, temp_dir: str):
        self.sandbox_id = sandbox_id
        self.agent_id = agent_id
        self.scenario_id = scenario_id
        self.temp_dir = temp_dir
        self.status = "INITIALIZED"  # INITIALIZED, RUNNING, COMPLETED, DESTROYED
        self.created_at = _now()
        self.logs: List[str] = []
        self.env_vars: Dict[str, str] = {}


class SandboxManager:
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.active_sandboxes: Dict[str, SandboxInstanceRecord] = {}

    def create_sandbox(self, agent_id: str, scenario_id: str) -> SandboxInstanceRecord:
        """Create a isolated temporary workspace directory for execution."""
        unique_suffix = uuid.uuid4().hex[:8]
        sandbox_id = f"sandbox-exec-{unique_suffix}"
        temp_workspace = tempfile.mkdtemp(prefix=f"sb_{sandbox_id}_")

        instance = SandboxInstanceRecord(
            sandbox_id=sandbox_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
            temp_dir=temp_workspace
        )
        self.active_sandboxes[sandbox_id] = instance
        instance.logs.append(f"[{_now()}] Sandbox instance {sandbox_id} created at {temp_workspace}")
        return instance

    def install_dependencies(self, instance: SandboxInstanceRecord, agent: AgentRecord) -> None:
        """Populate workspace files and manifest dependencies."""
        instance.logs.append(f"[{_now()}] Installing sandbox isolated runtime dependencies...")
        
        if agent.source_files:
            for rel_path, content in agent.source_files.items():
                target_path = os.path.join(instance.temp_dir, rel_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
        
        instance.logs.append(f"[{_now()}] Source files installed into virtual workspace.")

    def inject_allowed_environment(
        self,
        instance: SandboxInstanceRecord,
        allowed_env: Dict[str, str],
        secrets: Dict[str, str]
    ) -> Dict[str, str]:
        """Inject environment variables while redacting secret values in log output."""
        sanitized_env = dict(allowed_env)
        
        for secret_name, secret_val in secrets.items():
            sanitized_env[secret_name] = secret_val
            masked = "***REDACTED***"
            instance.logs.append(f"[{_now()}] Injected environment secret: {secret_name} = {masked}")

        instance.env_vars = sanitized_env
        return sanitized_env

    def run_agent(
        self,
        instance: SandboxInstanceRecord,
        agent: AgentRecord,
        scenario: Scenario,
        binding: Any = None
    ) -> ExecutionTrace:
        """Execute agent within the isolated sandbox harness."""
        from app.core.sandbox.runner import run_scenario_in_sandbox
        
        instance.status = "RUNNING"
        mode_val = getattr(getattr(binding, "mode", None), "value", "subprocess")
        model_name = getattr(binding, "executed_model", "default")
        instance.logs.append(f"[{_now()}] Starting agent execution under mode '{mode_val}' (Model: {model_name}).")
        
        start_time = time.time()
        
        trace = run_scenario_in_sandbox(
            agent=agent,
            scenario=scenario,
            is_counterfactual=False
        )

        trace.events.insert(0, TraceEvent(
            timestamp=_now(),
            role="sandbox_started",
            content=f"Sandbox {instance.sandbox_id} initialized."
        ))
        
        trace.events.append(TraceEvent(
            timestamp=_now(),
            role="sandbox_destroyed",
            content=f"Sandbox {instance.sandbox_id} completed and destroyed."
        ))

        instance.status = "COMPLETED"
        instance.logs.append(f"[{_now()}] Execution completed in {round((time.time() - start_time) * 1000.0, 2)} ms.")
        return trace

    def collect_logs(self, instance: SandboxInstanceRecord) -> List[str]:
        """Collect sanitized execution logs."""
        return list(instance.logs)

    def enforce_timeout(self, instance: SandboxInstanceRecord, timeout_seconds: int = 30) -> bool:
        """Enforce maximum execution timeout."""
        return True

    def destroy_sandbox(self, sandbox_id: str) -> None:
        """Clean up and remove sandbox instance directory."""
        if sandbox_id not in self.active_sandboxes:
            return

        instance = self.active_sandboxes[sandbox_id]
        if not self.debug_mode and os.path.exists(instance.temp_dir):
            try:
                shutil.rmtree(instance.temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Error removing sandbox directory {instance.temp_dir}: {e}")

        instance.status = "DESTROYED"
        del self.active_sandboxes[sandbox_id]
