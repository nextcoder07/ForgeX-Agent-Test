"""
DependencyResolver Module.
Resolves agent execution mode (Faithful, Compatible, Simulation) based on detected model dependencies
and available system credentials or local servers.
Enforces the critical principle:
NEVER silently replace LLM model, API provider, tool, dependency, or environment without recording it!
"""

from __future__ import annotations

import os
import uuid
import datetime as dt
from typing import Dict, List, Optional, Any
from app.models.agent import AgentRecord
from app.models.dependency_model import (
    AgentCategory,
    ExecutionMode,
    EvaluationFidelity,
    AgentModelDependency,
    ExecutionModelBinding,
    DependencyResolverResult,
    SystemCredentialItem,
    CredentialRequirement,
    SessionCredentialPrompt,
)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class DependencyResolver:
    @staticmethod
    def resolve_mode(
        agent: AgentRecord,
        requested_mode: Optional[ExecutionMode] = None,
        provided_secrets: Optional[Dict[str, str]] = None,
        execution_id: Optional[str] = None
    ) -> DependencyResolverResult:
        secrets = provided_secrets or {}
        exec_id = execution_id or f"run-{uuid.uuid4().hex[:8]}"

        # Extract detected model dependencies from runtime manifest or build defaults
        raw_manifest = agent.runtime_manifest or {}
        raw_category = raw_manifest.get("agent_category", AgentCategory.LLM_POWERED.value)
        try:
            agent_category = AgentCategory(raw_category)
        except Exception:
            agent_category = AgentCategory.LLM_POWERED

        raw_deps = raw_manifest.get("detected_model_dependencies", [])
        model_deps: List[AgentModelDependency] = []
        for d in raw_deps:
            if isinstance(d, dict):
                model_deps.append(AgentModelDependency(**d))
            elif isinstance(d, AgentModelDependency):
                model_deps.append(d)

        # Fallback default model dependency if none detected
        if not model_deps:
            model_deps.append(
                AgentModelDependency(
                    id=f"dep-def-{agent.id}",
                    agent_id=agent.id,
                    provider="openai",
                    model_name="gpt-5",
                    dependency_type="llm",
                    required=True,
                    original_provider="openai",
                    original_endpoint="https://api.openai.com/v1",
                    detected_from="system_default",
                    created_at=_now()
                )
            )

        orig_dep = model_deps[0]
        orig_provider = orig_dep.original_provider or orig_dep.provider
        orig_model = f"{orig_provider}/{orig_dep.model_name}"

        # 1. Check if original credential / provider is available
        has_openai_key = bool(secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))
        has_anthropic_key = bool(secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        has_gemini_key = bool(secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"))

        original_available = False
        if orig_provider == "openai" and has_openai_key:
            original_available = True
        elif orig_provider in ["google", "gemini"] and has_gemini_key:
            original_available = True
        elif orig_provider == "anthropic" and has_anthropic_key:
            original_available = True
        elif orig_provider in ["ollama", "huggingface", "vllm"] or agent_category in [AgentCategory.LOCAL_MODEL, AgentCategory.RULE_BASED]:
            # Local model or rule-based agent does not require cloud API key
            original_available = True

        # 2. Check if platform substitute (Gemini) is available
        substitute_available = has_gemini_key or True # Platform supports MockLLM as substitute if key missing

        # Determine active execution mode
        if requested_mode == ExecutionMode.SIMULATION:
            mode = ExecutionMode.SIMULATION
            executed_provider = "mock"
            executed_model = "mock/deterministic-llm"
            model_sub = False
            reason = "User requested deterministic simulation mode via MockLLM."
            confidence = "test-specific"
            fidelity = EvaluationFidelity.TEST_SPECIFIC

        elif requested_mode == ExecutionMode.FAITHFUL and original_available:
            mode = ExecutionMode.FAITHFUL
            executed_provider = orig_provider
            executed_model = orig_model
            model_sub = False
            reason = "Original credentials and model configuration available."
            confidence = "high"
            fidelity = EvaluationFidelity.HIGH

        elif requested_mode == ExecutionMode.FAITHFUL and not original_available:
            # Fallback to Compatible because original key is missing
            mode = ExecutionMode.COMPATIBLE
            executed_provider = "google"
            executed_model = "google/gemini-2.5-flash"
            model_sub = True
            reason = f"Original {orig_provider.upper()} API credential unavailable. Auto-routed to Compatible mode."
            confidence = "medium"
            fidelity = EvaluationFidelity.MEDIUM

        elif original_available and (not requested_mode or requested_mode == ExecutionMode.FAITHFUL):
            mode = ExecutionMode.FAITHFUL
            executed_provider = orig_provider
            executed_model = orig_model
            model_sub = False
            reason = f"Executed using original {orig_provider.upper()} configuration."
            confidence = "high"
            fidelity = EvaluationFidelity.HIGH

        else:
            # Compatible mode with substitution
            mode = ExecutionMode.COMPATIBLE
            executed_provider = "google"
            executed_model = "google/gemini-2.5-flash"
            model_sub = True
            reason = f"Original {orig_provider.upper()} credential unavailable. Executing in Compatible mode using Google Gemini."
            confidence = "medium"
            fidelity = EvaluationFidelity.MEDIUM

        binding = ExecutionModelBinding(
            id=f"bind-{exec_id}",
            execution_id=exec_id,
            original_model=orig_model,
            executed_model=executed_model,
            original_provider=orig_provider,
            executed_provider=executed_provider,
            mode=mode,
            model_substitution=model_sub,
            reason=reason,
            confidence=confidence,
            fidelity=fidelity,
            created_at=_now()
        )

        mode_options = [
            {
                "mode": ExecutionMode.FAITHFUL.value,
                "title": "MODE 1 — FAITHFUL",
                "available": original_available,
                "description": f"Execute using original {orig_provider.upper()} ({orig_dep.model_name}). Requires original API key.",
                "fidelity": "HIGH (100%)",
                "requires_secret": f"{orig_provider.upper()}_API_KEY" if orig_provider != "ollama" else None
            },
            {
                "mode": ExecutionMode.COMPATIBLE.value,
                "title": "MODE 2 — COMPATIBLE",
                "available": substitute_available,
                "description": "Test workflow, tool-use, safety, and failure recovery under Google Gemini substitute.",
                "fidelity": "MEDIUM (70%)",
                "requires_secret": None
            },
            {
                "mode": ExecutionMode.SIMULATION.value,
                "title": "MODE 3 — SIMULATION",
                "available": True,
                "description": "Deterministic offline execution using MockLLM for controlled tool & fault testing.",
                "fidelity": "TEST-SPECIFIC",
                "requires_secret": None
            }
        ]

        return DependencyResolverResult(
            agent_id=agent.id,
            agent_category=agent_category,
            detected_model_dependencies=model_deps,
            recommended_mode=mode,
            mode_options=mode_options,
            active_binding=binding
        )

    @staticmethod
    def get_system_credentials(user_overrides: Optional[Dict[str, str]] = None) -> List[SystemCredentialItem]:
        """Returns default platform system API keys and their active configuration status."""
        overrides = user_overrides or {}
        known_keys = [
            ("GEMINI_API_KEY", "Google Gemini AI", "Primary LLM engine for multi-stage analysis & judge"),
            ("OPENAI_API_KEY", "OpenAI", "Alternative LLM engine for Faithful execution mode"),
            ("ANTHROPIC_API_KEY", "Anthropic Claude", "Alternative LLM engine for Claude model testing"),
            ("SERPER_API_KEY", "Google Serper Search", "Default search API key for web search tools"),
            ("WEATHER_API_KEY", "OpenWeatherMap", "Default weather API key for location/environment tools"),
            ("DATABASE_URL", "PostgreSQL / Supabase", "Primary relational database connection URL"),
            ("STRIPE_TEST_KEY", "Stripe Simulator", "Default payment gateway test key for transaction tools"),
        ]

        items: List[SystemCredentialItem] = []
        for key_name, provider, desc in known_keys:
            val = overrides.get(key_name) or os.getenv(key_name, "")
            is_cfg = bool(val and not val.startswith("your_") and not val.endswith("_here"))
            
            if overrides.get(key_name):
                source = "user_custom"
            elif os.getenv(key_name):
                source = "system_env"
            else:
                source = "missing"

            masked = f"{val[:6]}...{val[-4:]}" if (is_cfg and len(val) > 10) else ("********" if is_cfg else None)

            items.append(
                SystemCredentialItem(
                    key_name=key_name,
                    provider=provider,
                    description=desc,
                    is_configured=is_cfg,
                    source=source,
                    masked_value=masked
                )
            )

        return items

    @staticmethod
    def evaluate_execution_credential_demands(
        agent: AgentRecord,
        provided_secrets: Optional[Dict[str, str]] = None,
        session_id: str = ""
    ) -> SessionCredentialPrompt:
        """Evaluates whether all required API keys are fulfilled before execution can proceed."""
        secrets = provided_secrets or {}
        system_items = {item.key_name: item for item in DependencyResolver.get_system_credentials(secrets)}

        requirements: List[CredentialRequirement] = []

        # 1. Model LLM Key Demand
        model_req = CredentialRequirement(
            key_name="GEMINI_API_KEY",
            provider="Google Gemini",
            description="Required for AI analysis, scenario generation, and execution evaluation",
            is_fulfilled=bool(secrets.get("GEMINI_API_KEY") or system_items.get("GEMINI_API_KEY", {}).is_configured),
            provided_by_system=bool(os.getenv("GEMINI_API_KEY")),
            masked_value=system_items.get("GEMINI_API_KEY", {}).masked_value
        )
        requirements.append(model_req)

        # 2. Tool Credential Demands (ONLY for external API keys / secrets, NEVER packages or frameworks)
        for dep in agent.dependencies:
            dep_type_str = str(dep.type).lower() if hasattr(dep.type, "value") else str(dep.type).lower()
            if dep_type_str in ["credential", "api_key", "secret", "environment_variable"]:
                key_name = dep.name.upper()
                is_full = bool(secrets.get(key_name) or os.getenv(key_name))
                requirements.append(
                    CredentialRequirement(
                        key_name=key_name,
                        provider=dep.name,
                        description=f"Tool dependency required by {agent.name}",
                        is_fulfilled=is_full,
                        is_optional=not dep.required,
                        provided_by_system=bool(os.getenv(key_name)),
                        masked_value=f"{secrets.get(key_name, '')[:4]}***" if is_full else None
                    )
                )

        # Also check tools for explicit required credentials
        for t in agent.tools:
            if "database" in t.name.lower() or "db" in t.name.lower():
                if not any(r.key_name == "DB_API_KEY" for r in requirements):
                    is_full = bool(secrets.get("DB_API_KEY") or os.getenv("DB_API_KEY"))
                    requirements.append(
                        CredentialRequirement(
                            key_name="DB_API_KEY",
                            provider="Database Service",
                            description="API key for database inventory/customer tool access",
                            is_fulfilled=is_full,
                            provided_by_system=bool(os.getenv("DB_API_KEY")),
                            masked_value="DB_***" if is_full else None
                        )
                    )

        # Determine overall fulfillment
        unfulfilled = [r for r in requirements if not r.is_fulfilled and not r.is_optional]
        all_fulfilled = len(unfulfilled) == 0

        status = "CLEARED" if all_fulfilled else "CREDS_REQUIRED"
        if all_fulfilled:
            msg = "All required system and tool API keys are satisfied. Ready for execution."
        else:
            missing_names = ", ".join([r.key_name for r in unfulfilled])
            msg = f"Execution blocked. Missing required API keys: {missing_names}. Please provide them to proceed."

        return SessionCredentialPrompt(
            session_id=session_id or f"sess-{uuid.uuid4().hex[:8]}",
            agent_id=agent.id,
            all_fulfilled=all_fulfilled,
            status=status,
            requirements=requirements,
            message=msg
        )
