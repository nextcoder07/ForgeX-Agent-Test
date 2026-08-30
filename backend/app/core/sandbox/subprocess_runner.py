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


# Environment variables that are strictly internal backend secrets and must never leak to child sandbox
SENSITIVE_ENV_KEYS = {
    "SUPABASE_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "DATABASE_URL",
    "SECRET_KEY",
    "JWT_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "STRIPE_SECRET_KEY",
    "ADMIN_PASSWORD",
}


SAFE_SYSTEM_ENV_KEYS = {
    "PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
    "HOME", "USERPROFILE", "LANG", "LC_ALL", "PYTHONIOENCODING", "PYTHONUTF8", "TERM"
}

def create_sanitized_environment(
    provided_secrets: Optional[Dict[str, str]] = None,
    agent: Optional[AgentRecord] = None
) -> Dict[str, str]:
    """Creates a sanitized environment dictionary using an explicit allowlist for child sandbox processes."""
    env = {}
    
    # 1. Allow only safe system environment variables
    for key, val in os.environ.items():
        if key.upper() in SAFE_SYSTEM_ENV_KEYS and key.upper() not in SENSITIVE_ENV_KEYS:
            env[key] = val

    # Set UTF-8 encoding so emojis and unicode strings print cleanly on all platforms (Windows cp1252 fix)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["LANG"] = "en_US.UTF-8"

    # 1.5 Ensure PYTHONPATH contains all active sys.path entries so installed packages (crewai, setuptools, etc.) are available
    python_paths = [p for p in sys.path if p and os.path.exists(p)]
    existing_ppath = env.get("PYTHONPATH", "")
    if existing_ppath:
        for p in existing_ppath.split(os.path.pathsep):
            if p and p not in python_paths:
                python_paths.append(p)
    env["PYTHONPATH"] = os.path.pathsep.join(python_paths)

    # 2. Inject active dedicated Test Agent keys (OPENAI_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY, etc.)
    try:
        from app.core.llm.key_manager import TestAgentKeyManager
        test_creds = TestAgentKeyManager().get_active_test_credentials()
        for k, v in test_creds.items():
            if v and not v.startswith("your_"):
                env[k] = v
    except Exception as e:
        pass

    # 2.5. Inject configuration secrets extracted from uploaded agent repository files (.env, config.json)
    if agent and agent.source_files:
        try:
            from app.core.dependencies.runtime_smoke_tester import RuntimeSmokeTester
            file_sec = RuntimeSmokeTester.extract_secrets_from_source_files(agent.source_files)
            for k, v in file_sec.items():
                if v and not v.startswith("your_"):
                    env[k] = v
        except Exception:
            pass

    # 3. Inject Agent-Specific Bound Model & Slot Credentials (from runtime_manifest or model_connections)
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
                if api_key and not api_key.startswith("your_"):
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
                            env["OPENAI_MAX_TOKENS"] = "1024"
                            env["MAX_TOKENS"] = "1024"
                            if conn.model_identifier:
                                target_mod = conn.model_identifier
                                if "/" not in target_mod:
                                    target_mod = f"openai/{target_mod}"
                                env["OPENAI_MODEL_NAME"] = target_mod
                                env["OPENAI_MODEL"] = target_mod
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

    # 4. Ensure ChatOpenAI / LangChain routes to OpenRouter/Groq/Ollama if no direct OpenAI key
    # langchain-openai uses OPENAI_BASE_URL (openai SDK >=1.x) AND legacy OPENAI_API_BASE
    if "OPENAI_API_KEY" not in env or not env["OPENAI_API_KEY"] or env.get("OPENAI_API_KEY") == "ollama":
        if "OPENROUTER_API_KEY" in env and env["OPENROUTER_API_KEY"]:
            env["OPENAI_API_KEY"] = env["OPENROUTER_API_KEY"]
            env["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
            env["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
            env["OPENAI_MAX_TOKENS"] = "1024"
            env["MAX_TOKENS"] = "1024"
        elif "GROQ_API_KEY" in env and env["GROQ_API_KEY"]:
            env["OPENAI_API_KEY"] = env["GROQ_API_KEY"]
            env["OPENAI_API_BASE"] = "https://api.groq.com/openai/v1"
            env["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
        elif "GEMINI_API_KEY" in env and env["GEMINI_API_KEY"]:
            env["OPENAI_API_KEY"] = env["GEMINI_API_KEY"]

    # 5. Inject explicit user-provided secrets (highest priority)
    if provided_secrets:
        for k, v in provided_secrets.items():
            if v and isinstance(v, str):
                env[k] = v

    # 6. Apply OpenAI-compatible bridges for OpenRouter, Groq, or local gateways
    if env.get("OPENROUTER_API_KEY") and (not env.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY").startswith("sk-or-")):
        env["OPENAI_API_KEY"] = env["OPENROUTER_API_KEY"]
        env["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
        env["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
        env["OPENAI_MAX_TOKENS"] = "1024"
        env["MAX_TOKENS"] = "1024"
    elif env.get("GROQ_API_KEY") and not env.get("OPENAI_API_KEY"):
        env["OPENAI_API_KEY"] = env["GROQ_API_KEY"]
        env["OPENAI_API_BASE"] = "https://api.groq.com/openai/v1"
        env["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"

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

    # 0. Enforce Preflight Smoke Test Verification
    from app.core.dependencies.runtime_smoke_tester import RuntimeSmokeTester
    smoke_res = RuntimeSmokeTester.run_smoke_test(agent, provided_secrets=provided_secrets)
    if not smoke_res.is_executable:
        block_msg = f"PRE-FLIGHT / DEPENDENCY_BLOCK: {smoke_res.blocking_reason}"
        if smoke_res.blockers:
            block_msg += f" — {'; '.join(smoke_res.blockers)}"
        events.append(TraceEvent(
            timestamp=_now(),
            role="preflight",
            content=block_msg
        ))
        return ExecutionTrace(
            id=trace_id,
            scenario_id=scenario.id,
            agent_id=agent.id,
            agent_version=scenario.agent_version_id or "v1.0",
            status="BLOCKED",
            termination_reason=smoke_res.blocking_reason,
            events=events,
            tool_calls=[],
            total_latency_ms=0.0,
            trajectory_hash=None
        )

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

        # 2.5 Write Sandbox Compatibility Shims (LangChain 0.3, OpenAI endpoint routing, TavilySearch fallback)
        # Determine if we have a real Tavily key to inject into shim
        _tavily_key_for_shim = sanitized_env.get("TAVILY_API_KEY", "")
        _openai_base_for_shim = sanitized_env.get("OPENAI_BASE_URL") or sanitized_env.get("OPENAI_API_BASE") or ""
        _openai_key_for_shim = sanitized_env.get("OPENAI_API_KEY", "")
        sitecustomize_path = os.path.join(sandbox_dir, "sitecustomize.py")
        with open(sitecustomize_path, "w", encoding="utf-8") as f:
            f.write(f"""import os
import sys

# --- ForgeX Sandbox Compatibility Shim ---

# 1. Shim LangChain 0.3 globals
try:
    import langchain
    if not hasattr(langchain, 'verbose'):
        langchain.verbose = False
    if not hasattr(langchain, 'debug'):
        langchain.debug = False
    if not hasattr(langchain, 'llm_cache'):
        langchain.llm_cache = None
except Exception:
    pass

# 2. Ensure both OPENAI_API_BASE and OPENAI_BASE_URL are always in sync
#    (openai SDK >=1.x reads OPENAI_BASE_URL; LangChain 0.x reads OPENAI_API_BASE)
openai_base = os.getenv('OPENAI_BASE_URL') or os.getenv('OPENAI_API_BASE')
if openai_base:
    os.environ['OPENAI_API_BASE'] = openai_base
    os.environ['OPENAI_BASE_URL'] = openai_base

# 3. Patch langchain_openai.ChatOpenAI to route through platform gateway when no real OpenAI key
_PLATFORM_BASE = {_openai_base_for_shim!r}
_PLATFORM_KEY = {_openai_key_for_shim!r}
if _PLATFORM_BASE:
    try:
        from langchain_openai import ChatOpenAI as _OrigChatOpenAI
        _orig_chat_init = _OrigChatOpenAI.__init__
        def _patched_chat_init(self, *args, **kwargs):
            # Redirect to platform gateway unless caller provides their own base_url
            if 'openai_api_base' not in kwargs and 'base_url' not in kwargs:
                kwargs['openai_api_base'] = _PLATFORM_BASE
                kwargs['base_url'] = _PLATFORM_BASE
            if 'openai_api_key' not in kwargs and 'api_key' not in kwargs and _PLATFORM_KEY:
                kwargs['openai_api_key'] = _PLATFORM_KEY
            _orig_chat_init(self, *args, **kwargs)
        _OrigChatOpenAI.__init__ = _patched_chat_init
    except Exception:
        pass

# 4. Patch TavilySearch to use a no-network stub when TAVILY_API_KEY is absent / invalid
_TAVILY_KEY = os.getenv('TAVILY_API_KEY', '')
if not _TAVILY_KEY or _TAVILY_KEY.startswith('your_') or _TAVILY_KEY.endswith('_here'):
    try:
        import langchain_tavily as _lt
        class _StubTavilySearch:
            def __init__(self, *args, **kwargs):
                self.max_results = kwargs.get('max_results', 3)
            def invoke(self, query):
                return {{'results': [{{
                    'url': 'https://example.com/stub',
                    'title': f'[STUB] Search result for: {{query}}',
                    'content': f'ForgeX sandbox stub result. No TAVILY_API_KEY provided. Query: {{query}}'
                }}]}}
            def run(self, query):
                return self.invoke(query)
        _lt.TavilySearch = _StubTavilySearch
        import sys
        if 'langchain_tavily' in sys.modules:
            sys.modules['langchain_tavily'].TavilySearch = _StubTavilySearch
    except Exception:
        pass
""")
        sanitized_env["PYTHONPATH"] = f"{sandbox_dir}{os.pathsep}{sanitized_env.get('PYTHONPATH', '')}"

        # --- UNIFIED REAL AGENT SUBPROCESS EXECUTION ---
        invocation = scenario.invocation or {}
        raw_args = invocation.get("args", [])
        if not raw_args and "command" in invocation:
            parts = invocation["command"].split()
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

        # Auto-inject CLI flag and scenario user prompt for CLI agents when args are missing or bare
        # e.g. [] or ['search laptops'] → ['--request', 'search laptops']
        primary_flag = None
        agent_inputs = getattr(agent, "inputs", None) or []
        for inp in agent_inputs:
            if isinstance(inp, dict):
                flag = inp.get("flag") or f"--{inp.get('name', 'request').replace('_', '-')}"
                primary_flag = flag
                break
        if not primary_flag:
            manifest = getattr(agent, "runtime_manifest", None) or {}
            for cli_arg in manifest.get("cli_arguments", []):
                if isinstance(cli_arg, dict):
                    flags = cli_arg.get("flags", [])
                    if flags:
                        primary_flag = flags[0]
                        break
        if not primary_flag:
            primary_flag = "--request"

        if not resolved_args:
            prompt_text = scenario.user_messages[0] if scenario.user_messages else (scenario.user_input or "Execute default request")
            resolved_args = [primary_flag, prompt_text]
        elif not any(str(a).startswith("-") for a in resolved_args):
            resolved_args = [primary_flag] + resolved_args

        # Auto-ensure agent dependencies are installed
        try:
            from app.core.sandbox.dependency_installer import ensure_agent_dependencies
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

        stdin_data = "\n".join(scenario.user_messages) if scenario.user_messages else (scenario.user_input or "")

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if stdin_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=sandbox_dir,
                env=sanitized_env
            )
            stdout_str, stderr_str = proc.communicate(input=stdin_data if stdin_data else None, timeout=timeout_seconds)
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
                        proc2 = subprocess.Popen(
                            cmd,
                            stdin=subprocess.PIPE if stdin_data else None,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            cwd=sandbox_dir,
                            env=sanitized_env
                        )
                        stdout_str, stderr_str = proc2.communicate(input=stdin_data if stdin_data else None, timeout=timeout_seconds)
                        exit_code = proc2.returncode
                except Exception:
                    pass

            if stdout_str:
                events.append(TraceEvent(
                    timestamp=_now(),
                    role="agent_message",
                    content=f"STDOUT_CHUNK: {stdout_str.strip()}"
                ))

                # Robust JSON stdout parsing for tool call invocations
                for line in stdout_str.strip().splitlines():
                    line_clean = line.strip()
                    if "{" in line_clean and "}" in line_clean:
                        start_idx = line_clean.find("{")
                        end_idx = line_clean.rfind("}")
                        if start_idx != -1 and end_idx > start_idx:
                            jstr = line_clean[start_idx:end_idx + 1]
                            try:
                                parsed_data = json.loads(jstr)
                                if isinstance(parsed_data, dict):
                                    tool_name = parsed_data.get("tool") or parsed_data.get("action") or parsed_data.get("function")
                                    if tool_name:
                                        targs = {k: v for k, v in parsed_data.items() if k not in ["tool", "action", "function", "result"]}
                                        res_data = parsed_data.get("result")
                                        if not targs and isinstance(res_data, dict):
                                            targs = {k: v for k, v in res_data.items()}
                                        tc_record = ToolCallRecord(
                                            id=f"tc-{uuid.uuid4().hex[:6]}",
                                            sequence=len(tool_calls) + 1,
                                            tool_name=str(tool_name),
                                            arguments=targs,
                                            result=res_data,
                                            status="SUCCESS",
                                            latency_ms=12.0
                                        )
                                        tool_calls.append(tc_record)
                                        events.append(TraceEvent(
                                            timestamp=_now(),
                                            role="tool_call",
                                            content=f"{tool_name}({', '.join(f'{k}={v!r}' for k, v in targs.items())})",
                                            tool_call=tc_record
                                        ))
                                        events.append(TraceEvent(
                                            timestamp=_now(),
                                            role="tool_result",
                                            content=str(res_data)
                                        ))
                            except Exception:
                                pass
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
