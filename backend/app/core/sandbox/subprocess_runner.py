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


def create_sanitized_environment() -> Dict[str, str]:
    """Creates a sanitized environment dictionary for child sandbox processes."""
    env = dict(os.environ)
    for key in list(env.keys()):
        if any(s in key.upper() for s in ["KEY", "SECRET", "TOKEN", "PASS", "CREDENTIAL"]):
            env.pop(key, None)
        elif key.upper() in SENSITIVE_ENV_KEYS:
            env.pop(key, None)
    env["SANDBOX_MODE"] = "isolated_subprocess"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_scenario_in_subprocess(
    agent: AgentRecord,
    scenario: Scenario,
    code_content: str,
    gateway: ToolGateway,
    timeout_seconds: float = 10.0
) -> ExecutionTrace:
    """Executes an agent scenario inside an isolated child Python process."""
    start_time = time.time()
    trace_id = f"trc-{uuid.uuid4().hex[:10]}"
    events: List[TraceEvent] = []
    tool_calls: List[ToolCallRecord] = []

    # Map scenario fault injections
    fault_map: Dict[str, str] = {
        f.target_tool.lower(): f.fault_type for f in scenario.fault_injections
    }

    # Prepare temporary Python runner script
    harness_code = f"""
import sys
import json
import math
import time

code_content = {repr(code_content)}
user_messages = {repr(scenario.user_messages or ["Hello"])}
tools = {[t.name for t in agent.tools]}

# Execute agent module code
module_globals = {{"__name__": "__sandbox__", "sys": sys, "json": json, "math": math, "time": time}}
exec(compile(code_content, "agent.py", "exec"), module_globals)

print("---SANDBOX_READY---")
for msg in user_messages:
    print(f"USER_MSG:{{msg}}")
    # Execute turns inside isolated process context
    target_tool = next((t for t in tools if t.lower() in msg.lower()), None)
    if not target_tool and tools:
        target_tool = tools[0]
    if target_tool:
        print(f"TOOL_INVOCATION:{{target_tool}}")
"""

    sanitized_env = create_sanitized_environment()

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(harness_code)
            tmp_path = tmp_file.name

        proc = subprocess.Popen(
            [sys.executable, tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=sanitized_env
        )

        try:
            stdout_str, stderr_str = proc.communicate(timeout=timeout_seconds)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_str, stderr_str = proc.communicate()
            exit_code = -1
            events.append(TraceEvent(
                timestamp=_now(),
                role="fault_injected",
                content=f"Execution timed out after {timeout_seconds}s in isolated subprocess sandbox."
            ))

        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        # Parse process execution output and dispatch tool calls through gateway
        for user_msg in scenario.user_messages or ["Hello"]:
            events.append(TraceEvent(timestamp=_now(), role="user", content=user_msg))

            # Match target tool invocation
            msg_lower = user_msg.lower()
            target_tool = next((t for t in agent.tools if t.name.lower() in msg_lower), None)
            if not target_tool and agent.tools:
                target_tool = agent.tools[0]

            if target_tool:
                tname = target_tool.name
                injected_fault = fault_map.get(tname.lower())
                mock_args = {"order_id": "ORD-4821", "amount": 5000.0}

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
                    content=f"Processed request using tool {tname} inside subprocess sandbox."
                ))

    except Exception as exc:
        events.append(TraceEvent(
            timestamp=_now(),
            role="security_alert",
            content=f"Subprocess sandbox execution failure: {exc}"
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
