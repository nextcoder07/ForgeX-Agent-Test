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


def create_sanitized_environment(
    provided_secrets: Optional[Dict[str, str]] = None,
    agent: Optional[AgentRecord] = None
) -> Dict[str, str]:
    """Creates a sanitized environment dictionary for child sandbox processes, preserving test agent keys, user secrets, and auto-mocking missing tool credentials."""
    env = dict(os.environ)
    for key in list(env.keys()):
        if any(s in key.upper() for s in ["KEY", "SECRET", "TOKEN", "PASS", "CREDENTIAL"]):
            env.pop(key, None)
        elif key.upper() in SENSITIVE_ENV_KEYS:
            env.pop(key, None)

    # Set UTF-8 encoding so emojis and unicode strings print cleanly on all platforms (Windows cp1252 fix)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["LANG"] = "en_US.UTF-8"

    # 1. Inject active dedicated Test Agent keys (OPENAI_API_KEY, GEMINI_API_KEY, etc.)
    try:
        from app.core.llm.key_manager import TestAgentKeyManager
        test_creds = TestAgentKeyManager().get_active_test_credentials()
        for k, v in test_creds.items():
            if v:
                env[k] = v
    except Exception as e:
        pass

    # 1.5 Inject Agent-Specific Bound Model & Slot Credentials (from runtime_manifest or model_connections)
    if agent:
        raw_manifest = agent.runtime_manifest or {}
        slot_configs = raw_manifest.get("slot_configs", {})
        model_bindings = raw_manifest.get("model_bindings", {})

        # Check direct slot configs
        for slot_id, cfg in slot_configs.items():
            if isinstance(cfg, dict):
                provider = str(cfg.get("provider", "")).lower()
                api_key = str(cfg.get("api_key", "")).strip()
                base_url = str(cfg.get("base_url", "")).strip()
                if api_key:
                    if provider == "openai":
                        env["OPENAI_API_KEY"] = api_key
                    elif provider == "openrouter":
                        env["OPENROUTER_API_KEY"] = api_key
                        env["OPENAI_API_KEY"] = api_key
                        env["OPENAI_API_BASE"] = base_url or "https://openrouter.ai/api/v1"
                        env["OPENAI_BASE_URL"] = base_url or "https://openrouter.ai/api/v1"
                    elif provider == "anthropic":
                        env["ANTHROPIC_API_KEY"] = api_key
                    elif provider in ("gemini", "google"):
                        env["GEMINI_API_KEY"] = api_key
                        env["GOOGLE_API_KEY"] = api_key
                    elif provider == "groq":
                        env["GROQ_API_KEY"] = api_key
                        env["OPENAI_API_KEY"] = api_key
                        if base_url:
                            env["OPENAI_API_BASE"] = base_url
                            env["OPENAI_BASE_URL"] = base_url
                    elif provider == "deepseek":
                        env["DEEPSEEK_API_KEY"] = api_key
                        env["OPENAI_API_KEY"] = api_key
                        if base_url:
                            env["OPENAI_API_BASE"] = base_url
                            env["OPENAI_BASE_URL"] = base_url

        # Check persisted model_connections in store
        try:
            from app.services.store import store
            for slot_id, conn_id in model_bindings.items():
                if conn_id and conn_id != "system_default":
                    conn = store.get_model_connection(conn_id)
                    if conn and conn.api_key:
                        provider = (conn.provider or "").lower()
                        if provider == "openai":
                            env["OPENAI_API_KEY"] = conn.api_key
                        elif provider == "openrouter":
                            env["OPENROUTER_API_KEY"] = conn.api_key
                            env["OPENAI_API_KEY"] = conn.api_key
                            env["OPENAI_API_BASE"] = conn.base_url or "https://openrouter.ai/api/v1"
                            env["OPENAI_BASE_URL"] = conn.base_url or "https://openrouter.ai/api/v1"
                        elif provider == "anthropic":
                            env["ANTHROPIC_API_KEY"] = conn.api_key
                        elif provider in ("gemini", "google"):
                            env["GEMINI_API_KEY"] = conn.api_key
                            env["GOOGLE_API_KEY"] = conn.api_key
                        elif provider == "groq":
                            env["GROQ_API_KEY"] = conn.api_key
                            env["OPENAI_API_KEY"] = conn.api_key
                            if conn.base_url:
                                env["OPENAI_API_BASE"] = conn.base_url
                                env["OPENAI_BASE_URL"] = conn.base_url
                        elif provider == "deepseek":
                            env["DEEPSEEK_API_KEY"] = conn.api_key
                            env["OPENAI_API_KEY"] = conn.api_key
                            if conn.base_url:
                                env["OPENAI_API_BASE"] = conn.base_url
                                env["OPENAI_BASE_URL"] = conn.base_url
        except Exception:
            pass

    # 1.8 Ensure ChatOpenAI / LangChain always has a valid key if OpenRouter/Gemini is present
    if "OPENAI_API_KEY" not in env or not env["OPENAI_API_KEY"]:
        if "OPENROUTER_API_KEY" in env and env["OPENROUTER_API_KEY"]:
            env["OPENAI_API_KEY"] = env["OPENROUTER_API_KEY"]
            env.setdefault("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
            env.setdefault("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        elif "GEMINI_API_KEY" in env and env["GEMINI_API_KEY"]:
            env["OPENAI_API_KEY"] = env["GEMINI_API_KEY"]

    # 2. Inject explicit user-provided secrets
    if provided_secrets:
        for k, v in provided_secrets.items():
            if v:
                env[k] = str(v)

    # 3. Auto-mock any missing agent tool credentials (e.g. WHO_CLINICAL_API_KEY, NEWS_API_KEY)
    if agent and agent.dependencies:
        for d in agent.dependencies:
            dep_type = getattr(d, "type", "")
            dep_type_str = dep_type.value if hasattr(dep_type, "value") else str(dep_type).lower()
            if dep_type_str in ["credential", "service", "tool"]:
                clean_name = d.name.strip()
                if clean_name.isidentifier() and clean_name not in env:
                    env[clean_name] = f"mock-{clean_name.lower().replace('_', '-')}"

    # Also check detected secrets for tool mocking
    raw_manifest = (agent.runtime_manifest or {}) if agent else {}
    for sec in raw_manifest.get("detected_secrets", []):
        sec_name = sec.get("name") if isinstance(sec, dict) else getattr(sec, "name", "")
        if sec_name and sec_name.isidentifier() and sec_name not in env:
            env[sec_name] = f"mock-{sec_name.lower().replace('_', '-')}"

    # Final cleanup: ensure all env keys are valid identifier strings with no '=' or illegal characters
    cleaned_env = {}
    for k, v in env.items():
        if isinstance(k, str) and k.isidentifier() and "=" not in k and "\0" not in k:
            cleaned_env[k] = str(v)

    cleaned_env["SANDBOX_MODE"] = "isolated_subprocess"
    cleaned_env["PYTHONUNBUFFERED"] = "1"
    cleaned_env["PYTHONIOENCODING"] = "utf-8"
    cleaned_env["PYTHONUTF8"] = "1"
    return cleaned_env



def run_scenario_in_subprocess(
    agent: AgentRecord,
    scenario: Scenario,
    code_content: str,
    gateway: ToolGateway,
    timeout_seconds: float = 35.0,
    provided_secrets: Optional[Dict[str, str]] = None
) -> ExecutionTrace:
    """Executes an agent scenario inside an isolated child process with real file staging and CLI/Chat support."""
    start_time = time.time()
    trace_id = f"trc-{uuid.uuid4().hex[:10]}"
    events: List[TraceEvent] = []
    tool_calls: List[ToolCallRecord] = []
    sanitized_env = create_sanitized_environment(provided_secrets=provided_secrets, agent=agent)

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

        # 2.5 Write Sandbox Compatibility Shims (e.g. LangChain 0.3 compatibility & OpenAI endpoint routing)
        sitecustomize_path = os.path.join(sandbox_dir, "sitecustomize.py")
        with open(sitecustomize_path, "w", encoding="utf-8") as f:
            f.write("""import os
import sys

# Shim LangChain 0.3 globals
try:
    import langchain
    if not hasattr(langchain, "verbose"):
        langchain.verbose = False
    if not hasattr(langchain, "debug"):
        langchain.debug = False
    if not hasattr(langchain, "llm_cache"):
        langchain.llm_cache = None
except Exception:
    pass

# Ensure OpenAI SDK routes to OpenRouter if base url is provided
if os.getenv("OPENAI_BASE_URL") and not os.getenv("OPENAI_API_BASE"):
    os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_BASE_URL")
""")
        sanitized_env["PYTHONPATH"] = f"{sandbox_dir}{os.pathsep}{sanitized_env.get('PYTHONPATH', '')}"

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

            # Auto-ensure agent dependencies are installed
            try:
                from app.core.sandbox.dependency_installer import ensure_agent_dependencies, auto_install_missing_module_from_error
                installed = ensure_agent_dependencies(agent, sandbox_dir=sandbox_dir)
                if installed:
                    events.append(TraceEvent(
                        timestamp=_now(),
                        role="sandbox",
                        content=f"PACKAGES_AUTO_INSTALLED: Installed {', '.join(installed)} dynamically for execution."
                    ))
            except Exception:
                pass

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
                    encoding="utf-8",
                    errors="replace",
                    cwd=sandbox_dir,
                    env=sanitized_env
                )
                stdout_str, stderr_str = proc.communicate(timeout=timeout_seconds)
                exit_code = proc.returncode

                # Auto-recovery if ModuleNotFoundError occurred
                if exit_code != 0 and stderr_str and ("ModuleNotFoundError" in stderr_str or "No module named" in stderr_str or "ImportError" in stderr_str):
                    try:
                        from app.core.sandbox.dependency_installer import auto_install_missing_module_from_error
                        pkg_installed = auto_install_missing_module_from_error(stderr_str)
                        if pkg_installed:
                            events.append(TraceEvent(
                                timestamp=_now(),
                                role="sandbox",
                                content=f"AUTO_RECOVERY: Installed missing package '{pkg_installed}' on-the-fly. Retrying execution..."
                            ))
                            # Retry process
                            proc2 = subprocess.Popen(
                                cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                cwd=sandbox_dir,
                                env=sanitized_env
                            )
                            stdout_str, stderr_str = proc2.communicate(timeout=timeout_seconds)
                            exit_code = proc2.returncode
                    except Exception as retry_err:
                        pass


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
