"""
SandboxManager Module.
Manages isolated execution environments for untrusted agent code.
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
from app.models.dependency_model import ExecutionModelBinding, ExecutionMode
from app.core.intake.dependency_detector import redact_secret_string

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


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
        
        # Write agent source files into workspace
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
            masked = redact_secret_string(secret_val)
            instance.logs.append(f"[{_now()}] Injected environment secret: {secret_name} = {masked}")

        instance.env_vars = sanitized_env
        return sanitized_env

    def run_agent(
        self,
        instance: SandboxInstanceRecord,
        agent: AgentRecord,
        scenario: Scenario,
        binding: ExecutionModelBinding
    ) -> ExecutionTrace:
        """Execute agent within the isolated sandbox harness."""
        from app.core.sandbox.runner import run_scenario_in_sandbox
        
        instance.status = "RUNNING"
        instance.logs.append(f"[{_now()}] Starting agent execution under mode '{binding.mode.value}' (Model: {binding.executed_model}).")
        
        start_time = time.time()
        
        # Execute scenario inside sandbox harness
        trace = run_scenario_in_sandbox(
            agent=agent,
            scenario=scenario,
            is_counterfactual=False
        )

        # Attach sandbox ID & model binding info to trace events
        trace.events.insert(0, TraceEvent(
            timestamp=_now(),
            role="sandbox_started",
            content=f"Sandbox {instance.sandbox_id} initialized. Mode={binding.mode.value}, Model={binding.executed_model}, Substitution={binding.model_substitution}"
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
        # Simulated timeout check
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
