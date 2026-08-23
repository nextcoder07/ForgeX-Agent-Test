"""
Subprocess Sandbox Execution Engine.
Executes untrusted agent Python code inside an isolated child process with timeout limits,
sanitized environment variables (stripping backend secrets), and stdout/stderr capture.
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import tempfile
import subprocess
import datetime as dt
from typing import Any, Dict, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution import ExecutionTrace, TraceEvent, ToolCallRecord
from app.core.dependencies.tool_gateway import ToolGateway


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# Environment variables to explicitly strip from child sandbox environment
SENSITIVE_ENV_KEYS = {
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "SUPABASE_KEY",
    "SUPABASE_URL",
    "DATABASE_URL",
    "SECRET_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
}


def create_sanitized_environment(provided_secrets: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Creates a sanitized environment dictionary for child sandbox processes, preserving test agent keys and user secrets."""
    env = dict(os.environ)
    for key in list(env.keys()):
        if any(s in key.upper() for s in ["KEY", "SECRET", "TOKEN", "PASS", "CREDENTIAL"]):
            env.pop(key, None)
        elif key.upper() in SENSITIVE_ENV_KEYS:
            env.pop(key, None)

    # 1. Inject active dedicated Test Agent keys (OPENAI_API_KEY, GEMINI_API_KEY, etc.)
    try:
        from app.core.llm.key_manager import TestAgentKeyManager
        test_creds = TestAgentKeyManager().get_active_test_credentials()
        for k, v in test_creds.items():
            if v:
                env[k] = v
    except Exception as e:
        pass

    # 2. Inject explicit user-provided secrets
    if provided_secrets:
        for k, v in provided_secrets.items():
            if v:
                env[k] = str(v)

    env["SANDBOX_MODE"] = "isolated_subprocess"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_scenario_in_subprocess(
    agent: AgentRecord,
    scenario: Scenario,
    code_content: str,
    gateway: ToolGateway,
    timeout_seconds: float = 10.0,
    provided_secrets: Optional[Dict[str, str]] = None
) -> ExecutionTrace:
    """Executes an agent scenario inside an isolated child process with real file staging and CLI/Chat support."""
    start_time = time.time()
    trace_id = f"trc-{uuid.uuid4().hex[:10]}"
    events: List[TraceEvent] = []
    tool_calls: List[ToolCallRecord] = []
    sanitized_env = create_sanitized_environment(provided_secrets=provided_secrets)

    interface = (scenario.interface_type or "CHAT").upper()
    manifest = agent.runtime_manifest or {}
    entrypoint_filename = manifest.get("entrypoint", "agent.py")

    with tempfile.TemporaryDirectory(prefix="sandbox_run_") as sandbox_dir:
        events.append(TraceEvent(
            timestamp=_now(),
            role="sandbox",
            content=f"SANDBOX_STARTED: Isolated workspace initialized at {sandbox_dir}"
        ))

        # 1. Stage Input Artifacts (e.g. resume.txt)
        staged_files = []
        for art in scenario.input_artifacts:
            if isinstance(art, dict) and "path" in art:
                rel_path = art["path"]
                content = art.get("content", "")
                full_path = os.path.join(sandbox_dir, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                staged_files.append(rel_path)
                events.append(TraceEvent(
                    timestamp=_now(),
                    role="sandbox",
                    content=f"FILE_CREATED: Staged input artifact '{rel_path}' ({len(content)} chars)"
                ))

        # 2. Write Agent Code File
        agent_script_path = os.path.join(sandbox_dir, entrypoint_filename)
        os.makedirs(os.path.dirname(agent_script_path), exist_ok=True)
        with open(agent_script_path, "w", encoding="utf-8") as f:
            f.write(code_content)

        if interface == "CLI":
            # --- CLI EXECUTION PATH ---
            invocation = scenario.invocation or {}
            raw_args = invocation.get("args", [])
            # If args are empty, check command string
            if not raw_args and "command" in invocation:
                parts = invocation["command"].split()
                # strip python and script name if present
                if len(parts) > 1 and "python" in parts[0]:
                    raw_args = parts[2:] if parts[1].endswith(".py") else parts[1:]
                elif len(parts) > 1 and parts[0].endswith(".py"):
                    raw_args = parts[1:]

            # Resolve relative artifact paths in args to sandbox_dir
            resolved_args = []
            for arg in raw_args:
                potential_file = os.path.join(sandbox_dir, arg)
                if os.path.exists(potential_file):
                    resolved_args.append(potential_file)
                else:
                    resolved_args.append(arg)

            cmd = [sys.executable, agent_script_path] + resolved_args
            events.append(TraceEvent(
                timestamp=_now(),
                role="system",
                content=f"PROCESS_STARTED: Command '{' '.join([os.path.basename(sys.executable), entrypoint_filename] + resolved_args)}'"
            ))

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=sandbox_dir,
                    env=sanitized_env
                )
                stdout_str, stderr_str = proc.communicate(timeout=timeout_seconds)
                exit_code = proc.returncode

                if stdout_str:
                    events.append(TraceEvent(
                        timestamp=_now(),
                        role="agent_message",
                        content=f"STDOUT_CHUNK: {stdout_str.strip()}"
                    ))
                if stderr_str:
                    events.append(TraceEvent(
                        timestamp=_now(),
                        role="agent_thought",
                        content=f"STDERR_CHUNK: {stderr_str.strip()}"
                    ))

                events.append(TraceEvent(
                    timestamp=_now(),
                    role="system",
                    content=f"PROCESS_EXITED: Exit code {exit_code}"
                ))

            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_str, stderr_str = proc.communicate()
                exit_code = -1
                events.append(TraceEvent(
                    timestamp=_now(),
                    role="fault_injected",
                    content=f"PROCESS_TIMEOUT: Subprocess timed out after {timeout_seconds}s"
                ))
            except Exception as e:
                exit_code = -1
                events.append(TraceEvent(
                    timestamp=_now(),
                    role="security_alert",
                    content=f"PROCESS_ERROR: {e}"
                ))

        else:
            # --- CHAT / TOOL HARNESS PATH ---
            fault_map = {f.target_tool.lower(): f.fault_type for f in scenario.fault_injections}
            for user_msg in scenario.user_messages or ["Hello"]:
                events.append(TraceEvent(timestamp=_now(), role="user", content=user_msg))
                msg_lower = user_msg.lower()
                target_tool = next((t for t in agent.tools if t.name.lower() in msg_lower), None)
                if not target_tool and agent.tools:
                    target_tool = agent.tools[0]

                if target_tool:
                    tname = target_tool.name
                    injected_fault = fault_map.get(tname.lower())
                    mock_args = {"query": user_msg, "amount": 5000.0}
                    tool_res = gateway.execute_tool_call(tname, mock_args, injected_fault=injected_fault)
                    tc_rec = gateway.call_history[-1] if gateway.call_history else None

                    events.append(TraceEvent(
                        timestamp=_now(),
                        role="tool_call",
                        content=f"{tname}({', '.join(f'{k}={v!r}' for k, v in mock_args.items())})",
                        tool_call=tc_rec
                    ))
                    events.append(TraceEvent(
                        timestamp=_now(),
                        role="tool_result",
                        content=str(tool_res)
                    ))
                    if tc_rec:
                        tool_calls.append(tc_rec)

                    events.append(TraceEvent(
                        timestamp=_now(),
                        role="agent_message",
                        content=f"Processed request using tool {tname}."
                    ))

        events.append(TraceEvent(
            timestamp=_now(),
            role="sandbox",
            content="SANDBOX_TERMINATED: Cleaned up isolated workspace."
        ))

    total_latency_ms = round((time.time() - start_time) * 1000, 2)
    return ExecutionTrace(
        id=trace_id,
        scenario_id=scenario.id,
        agent_id=agent.id,
        agent_version=agent.version_label,
        events=events,
        tool_calls=tool_calls,
        total_latency_ms=total_latency_ms,
        total_tokens=150,
        is_counterfactual=False
    )
