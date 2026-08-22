"""
Scenario Execution Contract Compiler.
Compiles a validated, executable Scenario into a strict ScenarioExecutionContract.
The execution sandbox runner consumes this contract directly without semantic re-interpretation.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario, ScenarioExecutionContract


def compile_scenario_execution_contract(
    scenario: Scenario,
    agent: AgentRecord,
    working_directory: str = "/workspace",
    execution_mode: str = "subprocess",
    model_binding: Optional[Dict[str, Any]] = None
) -> ScenarioExecutionContract:
    """Compiles a Scenario into an explicit, deterministic ScenarioExecutionContract."""
    manifest = agent.runtime_manifest or {}
    entrypoint = manifest.get("entrypoint", "agent.py")
    interface = (scenario.interface_type or "CLI").upper()

    # 1. Compile Command Arguments
    command: List[str] = []
    if interface == "CLI":
        raw_args = scenario.invocation.get("args", [])
        if not raw_args and "arguments" in scenario.invocation:
            raw_args = scenario.invocation["arguments"]
        elif not raw_args and "command" in scenario.invocation:
            parts = scenario.invocation["command"].split()
            if len(parts) > 1 and "python" in parts[0]:
                raw_args = parts[2:] if parts[1].endswith(".py") else parts[1:]
            elif len(parts) > 1 and parts[0].endswith(".py"):
                raw_args = parts[1:]

        command = [sys.executable, os.path.join(working_directory, entrypoint)] + list(raw_args)

    # 2. Stage Artifacts Mapping
    staged_artifacts = []
    for art in scenario.input_artifacts:
        if isinstance(art, dict) and "path" in art:
            staged_artifacts.append({
                "relative_path": art["path"],
                "content": art.get("content", ""),
                "mime_type": art.get("mime_type", "text/plain")
            })

    # 3. Environment Bindings
    env_bindings = {
        "SANDBOX_AGENT_ID": agent.id,
        "SANDBOX_SCENARIO_ID": scenario.id,
        "PYTHONUNBUFFERED": "1",
        "SANDBOX_INTERFACE": interface
    }

    # 4. Timeout & Policies
    timeout = float(scenario.execution_limits.get("timeout_seconds", 30.0))

    return ScenarioExecutionContract(
        scenario_id=scenario.id,
        agent_id=agent.id,
        working_directory=working_directory,
        command=command,
        env_bindings=env_bindings,
        staged_artifacts=staged_artifacts,
        network_policy_id="sandbox-web-restricted",
        filesystem_policy_id="sandbox-files-v1",
        timeout_seconds=timeout,
        execution_mode=execution_mode,
        model_binding=model_binding or {
            "original_model": getattr(agent, "model_dependency", "unknown"),
            "executed_model": "simulation" if execution_mode == "simulation" else "local",
            "model_substitution": execution_mode == "simulation"
        }
    )
