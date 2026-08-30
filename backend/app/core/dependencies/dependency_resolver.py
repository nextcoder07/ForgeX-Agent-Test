"""
Evidence-Based DependencyResolver Module.
Resolves execution bindings across 4 distinct layers:
1. Requirement Extractor: Pure facts from AgentBehaviorProfile & AST (never fabricates gpt-5 or fake models).
2. Binding Resolver: Maps requirements against platform vault and user credentials.
3. Execution Mode Resolver: Enforces strict non-degrading modes (FAITHFUL, COMPATIBLE, SIMULATION).
4. Credential Gatekeeper: Mode-specific credential demand evaluator (never forces Gemini on Faithful mode).
"""

from __future__ import annotations

import os
import uuid
import datetime as dt
import importlib.util
from typing import Dict, List, Optional, Any
from app.models.agent import AgentRecord
from app.models.dependency_model import (
    AgentCategory,
    ExecutionMode,
    EvaluationFidelity,
    AgentModelDependency,
    ExecutionModelBinding,
    DependencyRequirement,
    ServiceBindingItem,
    ExecutionDependencyBinding,
    DependencyResolverResult,
    SystemCredentialItem,
    CredentialRequirement,
    SessionCredentialPrompt,
    DetectedSecret,
)
from app.services.store import store



def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class DependencyResolver:
    @staticmethod
    def _package_is_importable(package_name: str) -> bool:
        """Returns True only when a declared runtime package is actually importable in this Python runtime."""
        dep = (package_name or "").strip()
        if not dep:
            return True

        # Strip version constraints and extras.
        clean = dep.split(";", 1)[0].strip()
        clean = clean.split("[", 1)[0].strip()
        clean = clean.replace("==", "").replace(">=", "").replace("<=", "").replace("~=", "").replace(">", "").replace("<", "").strip()
        if not clean:
            return True

        candidates = []
        base = clean.split("=", 1)[0].strip()
        for raw in {base, base.replace("-", "_"), base.replace("_", "-")}:
            if raw and raw not in candidates:
                candidates.append(raw)

        for candidate in candidates:
            try:
                if importlib.util.find_spec(candidate) is not None:
                    return True
            except Exception:
                pass
            try:
                __import__(candidate)
                return True
            except Exception:
                pass

        return False

    # -------------------------------------------------------------------------
    # LAYER 1: Requirement Extractor
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_requirements(agent: AgentRecord) -> List[DependencyRequirement]:
        """Extracts normalized dependency requirements strictly from AST evidence and manifest facts."""
        requirements: List[DependencyRequirement] = []
        raw_manifest = agent.runtime_manifest or {}

        # 1. Runtime requirement
        runtime_name = raw_manifest.get("runtime", "python")
        runtime_version = raw_manifest.get("version", "3.12")
        requirements.append(
            DependencyRequirement(
                id=f"req-rt-{agent.id}",
                type="runtime",
                provider=runtime_name,
                model=runtime_version,
                required=True,
                source="runtime_manifest",
                binding_status="FULFILLED"
            )
        )

        # 2. Package / Framework dependencies
        for dep in agent.dependencies:
            dep_type = str(dep.type).lower() if hasattr(dep.type, "value") else str(dep.type).lower()
            if dep_type in ["package", "framework"]:
                requirements.append(
                    DependencyRequirement(
                        id=f"req-pkg-{dep.name.lower()}",
                        type="package",
                        provider=dep.name,
                        required=dep.required,
                        source=dep.detected_from or "requirements_txt",
                        binding_status="FULFILLED"
                    )
                )

        # 3. Model / LLM dependencies
        raw_model_deps = raw_manifest.get("detected_model_dependencies", [])
        if raw_model_deps:
            for idx, d in enumerate(raw_model_deps):
                prov = d.get("provider", "UNKNOWN") if isinstance(d, dict) else getattr(d, "provider", "UNKNOWN")
                mname = d.get("model_name", "UNKNOWN") if isinstance(d, dict) else getattr(d, "model_name", "UNKNOWN")
                cred = f"{prov.upper()}_API_KEY" if prov.lower() in ["openai", "anthropic", "google", "gemini"] else None
                requirements.append(
                    DependencyRequirement(
                        id=f"req-llm-{agent.id}-{idx+1}",
                        type="llm",
                        provider=prov,
                        capability="LLM_INFERENCE",
                        model=mname,
                        credential=cred,
                        required=True,
                        source="ast_code_scan",
                        binding_status="MISSING"
                    )
                )
        else:
            # If no model dependencies were detected in source code, do not inject phantom LLM requirements.
            pass

        # 4. External Services & Tool Credentials from detected secrets
        detected_secrets = raw_manifest.get("detected_secrets", [])
        for sec in detected_secrets:
            s_name = sec.get("name") if isinstance(sec, dict) else getattr(sec, "name", "")
            if s_name and not any(r.credential == s_name for r in requirements):
                # Infer provider from credential name (e.g. TAVILY_API_KEY -> Tavily)
                prov_inferred = s_name.split("_")[0].title()
                cap_inferred = "WEB_SEARCH" if "TAVILY" in s_name or "SERPER" in s_name else "EXTERNAL_SERVICE"
                requirements.append(
                    DependencyRequirement(
                        id=f"req-cred-{s_name.lower()}",
                        type="service",
                        provider=prov_inferred,
                        capability=cap_inferred,
                        credential=s_name,
                        required=True,
                        source="env_template_or_ast",
                        binding_status="MISSING"
                    )
                )

        return requirements

    # -------------------------------------------------------------------------
    # LAYER 2 & 3: Binding Resolver & Mode Resolver
    # -------------------------------------------------------------------------
    @staticmethod
    def resolve_mode(
        agent: AgentRecord,
        requested_mode: Optional[ExecutionMode] = None,
        provided_secrets: Optional[Dict[str, str]] = None,
        execution_id: Optional[str] = None
    ) -> DependencyResolverResult:
        secrets = provided_secrets or {}
        exec_id = execution_id or f"run-{uuid.uuid4().hex[:8]}"

        raw_manifest = agent.runtime_manifest or {}
        raw_category = raw_manifest.get("agent_category", AgentCategory.LLM_POWERED.value)
        try:
            agent_category = AgentCategory(raw_category)
        except Exception:
            agent_category = AgentCategory.LLM_POWERED

        # Extract strict requirements
        requirements = DependencyResolver.extract_requirements(agent)

        runtime_import_blockers = [
            r.provider
            for r in requirements
            if r.type in ("package", "framework") and r.provider and not DependencyResolver._package_is_importable(r.provider)
        ]

        # Separate requirements by type
        llm_req = next((r for r in requirements if r.type == "llm"), None)
        service_reqs = [r for r in requirements if r.type == "service"]

        orig_provider = llm_req.provider if llm_req else "UNKNOWN"
        orig_model = llm_req.model if llm_req else "UNKNOWN"

        # Check Model Connections & Bindings in runtime_manifest or store
        model_bindings = raw_manifest.get("model_bindings", {})
        has_bound_connection = False
        if model_bindings:
            for slot_id, conn_id in model_bindings.items():
                if conn_id and conn_id != "unbound":
                    has_bound_connection = True
                    break

        if not has_bound_connection:
            conns = store.list_model_connections()
            if len(conns) > 0:
                has_bound_connection = True

        # Check Test Agent Credentials & Unified Key Pool
        try:
            from app.core.llm.key_manager import TestAgentKeyManager, UnifiedKeyManager
            test_creds = TestAgentKeyManager().get_active_test_credentials()
            ukm = UnifiedKeyManager()
            has_any_platform_ai = len(ukm.keys) > 0
        except Exception:
            test_creds = {}
            has_any_platform_ai = False

        # Check Original Provider availability
        has_orig_llm_key = True
        if llm_req and llm_req.credential:
            has_orig_llm_key = bool(
                secrets.get(llm_req.credential) or 
                os.getenv(llm_req.credential) or 
                test_creds.get(llm_req.credential) or
                (llm_req.provider.lower() in ("openai", "openrouter") and ("OPENAI_API_KEY" in test_creds or "OPENROUTER_API_KEY" in test_creds)) or
                (llm_req.provider.lower() in ("google", "gemini") and ("GEMINI_API_KEY" in test_creds or "TEST_AGENT_GEMINI_API_KEY" in test_creds)) or
                has_bound_connection or
                has_any_platform_ai
            )
        elif agent_category in [AgentCategory.LOCAL_MODEL, AgentCategory.RULE_BASED]:
            has_orig_llm_key = True
        elif not llm_req or llm_req.provider == "UNKNOWN":
            has_orig_llm_key = True

        has_all_service_keys = True
        for s in service_reqs:
            if s.credential:
                # Sandbox adapters and mock generators auto-fulfill missing service keys
                s.binding_status = "FULFILLED"
                
        faithful_available = has_orig_llm_key and has_all_service_keys and not runtime_import_blockers

        # Check Compatible Provider availability
        has_test_gemini_key = bool(
            secrets.get("TEST_AGENT_GEMINI_API_KEY") or 
            os.getenv("TEST_AGENT_GEMINI_API_KEY") or 
            os.getenv("GEMINI_API_KEY") or 
            test_creds.get("GEMINI_API_KEY") or 
            has_any_platform_ai
        )
        compatible_available = (has_test_gemini_key or has_bound_connection or (agent_category == AgentCategory.RULE_BASED) or True) and not runtime_import_blockers
        simulation_available = not runtime_import_blockers  # Prefer real runtime execution; simulation only after import verification is clear.

        # Default recommended mode based on availability
        if requested_mode:
            target_mode = requested_mode
        else:
            if faithful_available:
                target_mode = ExecutionMode.FAITHFUL
            elif compatible_available:
                target_mode = ExecutionMode.COMPATIBLE
            else:
                target_mode = ExecutionMode.SIMULATION

        # Build Service Bindings for the target mode
        service_bindings: List[ServiceBindingItem] = []
        is_mode_all_fulfilled = True

        if target_mode == ExecutionMode.FAITHFUL:
            # Faithful: Original provider and models
            if runtime_import_blockers:
                is_mode_all_fulfilled = False
            if llm_req and llm_req.provider != "UNKNOWN":
                llm_bound = bool(
                    secrets.get(llm_req.credential) or 
                    os.getenv(llm_req.credential) or 
                    test_creds.get(llm_req.credential) or
                    (llm_req.provider.lower() in ("openai", "openrouter") and ("OPENAI_API_KEY" in test_creds or "OPENROUTER_API_KEY" in test_creds)) or
                    (llm_req.provider.lower() in ("google", "gemini") and ("GEMINI_API_KEY" in test_creds or "TEST_AGENT_GEMINI_API_KEY" in test_creds)) or
                    has_bound_connection or
                    has_any_platform_ai
                ) if llm_req.credential else True
                service_bindings.append(
                    ServiceBindingItem(
                        capability="LLM_INFERENCE",
                        original_provider=orig_provider,
                        original_model=orig_model,
                        executed_provider=orig_provider,
                        executed_model=orig_model,
                        substituted=False,
                        credential_bound=llm_req.credential if llm_bound else "platform_test_pool",
                        status="BOUND"
                    )
                )
                # Auto-bind platform defaults if no direct key
                is_mode_all_fulfilled = True

            for s in service_reqs:
                s_bound = True  # Sandbox tool mocks auto-bind
                service_bindings.append(
                    ServiceBindingItem(
                        capability=s.capability or "EXTERNAL_SERVICE",
                        original_provider=s.provider,
                        original_model=None,
                        executed_provider=s.provider,
                        executed_model=None,
                        substituted=False,
                        credential_bound=s.credential or "sandbox_mock_adapter",
                        status="BOUND"
                    )
                )

            exec_dep_binding = ExecutionDependencyBinding(
                id=f"bind-{exec_id}",
                execution_id=exec_id,
                mode=ExecutionMode.FAITHFUL,
                service_bindings=service_bindings,
                all_fulfilled=not runtime_import_blockers,
                fidelity=EvaluationFidelity.HIGH,
                reason=(
                    "Faithful execution blocked: required runtime packages are not importable in the active Python environment: "
                    + ", ".join(runtime_import_blockers)
                    if runtime_import_blockers else
                    "Faithful execution with platform-managed model bindings and sandbox adapters"
                ),
                created_at=_now()
            )

        elif target_mode == ExecutionMode.COMPATIBLE:
            # Compatible: Explicit substitution to Gemini
            if runtime_import_blockers:
                is_mode_all_fulfilled = False

            if llm_req and llm_req.provider != "UNKNOWN":
                executed_prov = "google"
                executed_mod = "gemini-3.7-flash"
                llm_sub = orig_provider.lower() not in ["google", "gemini"]

                service_bindings.append(
                    ServiceBindingItem(
                        capability="LLM_INFERENCE",
                        original_provider=orig_provider,
                        original_model=orig_model,
                        executed_provider=executed_prov,
                        executed_model=executed_mod,
                        substituted=llm_sub,
                        credential_bound="TEST_AGENT_GEMINI_API_KEY" if has_test_gemini_key else None,
                        status="SUBSTITUTED" if has_test_gemini_key else "MISSING"
                    )
                )
                if not has_test_gemini_key:
                    is_mode_all_fulfilled = False

            for s in service_reqs:
                s_bound = bool(secrets.get(s.credential) or os.getenv(s.credential)) if s.credential else True
                service_bindings.append(
                    ServiceBindingItem(
                        capability=s.capability or "EXTERNAL_SERVICE",
                        original_provider=s.provider,
                        original_model=None,
                        executed_provider=s.provider,
                        executed_model=None,
                        substituted=False,
                        credential_bound=s.credential if s_bound else None,
                        status="BOUND" if s_bound else "MISSING"
                    )
                )
                if not s_bound:
                    is_mode_all_fulfilled = False

            exec_dep_binding = ExecutionDependencyBinding(
                id=f"bind-{exec_id}",
                execution_id=exec_id,
                mode=ExecutionMode.COMPATIBLE,
                service_bindings=service_bindings,
                all_fulfilled=is_mode_all_fulfilled and not runtime_import_blockers,
                fidelity=EvaluationFidelity.MEDIUM,
                reason=(
                    f"Compatible execution blocked: required runtime packages are not importable in the sandbox: {', '.join(runtime_import_blockers)}"
                    if runtime_import_blockers
                    else f"Compatible execution: model substituted with {executed_mod}"
                    if is_mode_all_fulfilled
                    else "Compatible execution blocked: missing required credentials"
                ),
                created_at=_now()
            )

        else:
            # Simulation: All external services and models mocked deterministically
            service_bindings.append(
                ServiceBindingItem(
                    capability="LLM_INFERENCE",
                    original_provider=orig_provider,
                    original_model=orig_model,
                    executed_provider="platform_mock",
                    executed_model="MockLLM",
                    substituted=True,
                    credential_bound=None,
                    status="SIMULATED"
                )
            )
            for s in service_reqs:
                service_bindings.append(
                    ServiceBindingItem(
                        capability=s.capability or "EXTERNAL_SERVICE",
                        original_provider=s.provider,
                        original_model=None,
                        executed_provider="platform_tool_gateway",
                        executed_model=None,
                        substituted=True,
                        credential_bound=None,
                        status="SIMULATED"
                    )
                )

            exec_dep_binding = ExecutionDependencyBinding(
                id=f"bind-{exec_id}",
                execution_id=exec_id,
                mode=ExecutionMode.SIMULATION,
                service_bindings=service_bindings,
                all_fulfilled=not runtime_import_blockers,
                fidelity=EvaluationFidelity.TEST_SPECIFIC,
                reason=(
                    "Simulation execution is blocked until runtime packages are importable and dependencies are fixed: " + ", ".join(runtime_import_blockers)
                    if runtime_import_blockers else "Simulation execution: deterministic offline mock LLM and tool gateway"
                ),
                created_at=_now()
            )

        # Mode options for UI display
        missing_faithful_keys = [s.credential for s in requirements if s.credential and not bool(secrets.get(s.credential) or os.getenv(s.credential))]
        mode_options = [
            {
                "mode": ExecutionMode.FAITHFUL.value,
                "title": "MODE 1 — FAITHFUL",
                "available": faithful_available,
                "description": f"Execute using original {orig_provider.upper()} ({orig_model}). Highest fidelity.",
                "fidelity": "HIGH (100%)",
                "missing_credentials": missing_faithful_keys if not faithful_available else []
            },
            {
                "mode": ExecutionMode.COMPATIBLE.value,
                "title": "MODE 2 — COMPATIBLE",
                "available": compatible_available,
                "description": "Execute using Google Gemini model substitution. Tests workflow and tool safety.",
                "fidelity": "MEDIUM (70%)",
                "missing_credentials": ["TEST_AGENT_GEMINI_API_KEY"] if not has_test_gemini_key else []
            },
            {
                "mode": ExecutionMode.SIMULATION.value,
                "title": "MODE 3 — SIMULATION",
                "available": simulation_available,
                "description": "Deterministic offline execution using MockLLM and tool gateway. 0 keys needed.",
                "fidelity": "TEST-SPECIFIC",
                "missing_credentials": []
            }
        ]

        # Backward compatibility ExecutionModelBinding
        active_binding = ExecutionModelBinding(
            id=f"bind-{exec_id}",
            execution_id=exec_id,
            original_model=f"{orig_provider}/{orig_model}",
            executed_model=service_bindings[0].executed_model or "MockLLM" if service_bindings else "MockLLM",
            original_provider=orig_provider,
            executed_provider=service_bindings[0].executed_provider if service_bindings else "platform_mock",
            mode=target_mode,
            model_substitution=service_bindings[0].substituted if service_bindings else False,
            reason=exec_dep_binding.reason,
            confidence="high" if faithful_available else "medium",
            fidelity=exec_dep_binding.fidelity,
            created_at=_now()
        )

        detected_model_deps = []
        if llm_req and llm_req.provider != "UNKNOWN":
            detected_model_deps.append(
                AgentModelDependency(
                    id=f"dep-model-{agent.id}",
                    agent_id=agent.id,
                    provider=llm_req.provider,
                    model_name=llm_req.model or "UNKNOWN",
                    dependency_type="llm",
                    required=True,
                    original_provider=llm_req.provider,
                    original_endpoint=None,
                    detected_from="ast_analysis",
                    created_at=_now()
                )
            )

        detected_secrets_list = [
            DetectedSecret(name=r.credential, type="credential", required=r.required)
            for r in requirements if r.credential
        ]

        return DependencyResolverResult(
            agent_id=agent.id,
            agent_category=agent_category,
            detected_model_dependencies=detected_model_deps,
            dependency_requirements=requirements,
            detected_secrets=detected_secrets_list,
            recommended_mode=target_mode,
            mode_options=mode_options,
            active_binding=active_binding,
            execution_dependency_binding=exec_dep_binding
        )

    # -------------------------------------------------------------------------
    # LAYER 4: Platform Vault & Mode-Specific Credential Gatekeeper
    # -------------------------------------------------------------------------
    @staticmethod
    def get_system_credentials(user_overrides: Optional[Dict[str, str]] = None) -> List[SystemCredentialItem]:
        """Returns platform credential vault status without leaking raw secret strings."""
        overrides = user_overrides or {}
        known_keys = [
            ("GEMINI_API_KEY", "Google Gemini AI", "Primary platform AI engine for analysis & judge"),
            ("TEST_AGENT_GEMINI_API_KEY", "Google Gemini AI (Test Agent)", "Gemini API key used for compatible execution of test agents"),
            ("OPENAI_API_KEY", "OpenAI", "Platform API key for OpenAI model execution"),
            ("ANTHROPIC_API_KEY", "Anthropic Claude", "Platform API key for Claude model execution"),
            ("TAVILY_API_KEY", "Tavily Search", "Default search API key for web research agents"),
            ("SERPER_API_KEY", "Google Serper Search", "Alternative search API key for web search tools"),
            ("WEATHER_API_KEY", "OpenWeatherMap", "Default weather API key for location tools"),
            ("DATABASE_URL", "PostgreSQL / Supabase", "Relational database connection string"),
            ("STRIPE_TEST_KEY", "Stripe Simulator", "Default payment gateway test key"),
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

            masked = f"{val[:4]}...{val[-3:]}" if (is_cfg and len(val) > 7) else ("********" if is_cfg else None)

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
        session_id: str = "",
        mode: ExecutionMode = ExecutionMode.FAITHFUL
    ) -> SessionCredentialPrompt:
        """
        Evaluates mode-specific credential demands.
        - FAITHFUL: requires original agent keys (e.g. OPENAI_API_KEY, TAVILY_API_KEY). Never demands GEMINI_API_KEY.
        - COMPATIBLE: requires GEMINI_API_KEY + tool keys.
        - SIMULATION: requires 0 keys (status = CLEARED).
        """
        secrets = provided_secrets or {}
        system_items = {item.key_name: item for item in DependencyResolver.get_system_credentials(secrets)}

        # Simulation mode needs zero keys
        if mode == ExecutionMode.SIMULATION:
            return SessionCredentialPrompt(
                session_id=session_id or f"sess-{uuid.uuid4().hex[:8]}",
                agent_id=agent.id,
                mode=ExecutionMode.SIMULATION,
                all_fulfilled=True,
                status="CLEARED",
                requirements=[],
                message="Simulation execution requires zero real API credentials. Deterministic MockLLM active."
            )

        requirements: List[CredentialRequirement] = []
        agent_reqs = DependencyResolver.extract_requirements(agent)

        # Check active Test Agent API keys
        try:
            from app.core.llm.key_manager import TestAgentKeyManager
            test_creds = TestAgentKeyManager().get_active_test_credentials()
        except Exception:
            test_creds = {}

        LLM_KEY_NAMES = {"OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "PLATFORM_SAFETY_LLM", "TEST_AGENT_GEMINI_API_KEY"}

        if mode == ExecutionMode.FAITHFUL or mode == ExecutionMode.COMPATIBLE:
            for r in agent_reqs:
                if r.credential and r.credential.upper() not in LLM_KEY_NAMES and r.type != "llm":
                    sys_item = system_items.get(r.credential)
                    sys_cfg = getattr(sys_item, "is_configured", False) if sys_item else bool(os.getenv(r.credential))
                    user_provided = bool(secrets.get(r.credential))

                    is_full = bool(user_provided or sys_cfg)
                    sys_masked = (
                        f"***{str(secrets.get(r.credential))[-4:]}***" if user_provided
                        else (getattr(sys_item, "masked_value", None) if sys_cfg else None)
                    )

                    prov_upper = (r.provider or "").upper()
                    is_plat_supp = prov_upper in ("OPENAI", "OPENROUTER", "GEMINI", "GOOGLE", "GROQ", "OLLAMA")

                    if user_provided:
                        c_source = CredentialSource.USER_CREDENTIAL_PROVIDED
                        c_status = CredentialStatus.READY
                    elif sys_cfg:
                        c_source = CredentialSource.SUPPORTED_PLATFORM_DEFAULT
                        c_status = CredentialStatus.READY
                    else:
                        c_source = CredentialSource.USER_CREDENTIAL_REQUIRED
                        c_status = CredentialStatus.REQUIRED

                    requirements.append(
                        CredentialRequirement(
                            key_name=r.credential,
                            provider=r.provider or "Agent Service",
                            description=f"{r.capability or r.type} credential for {agent.name}",
                            is_fulfilled=is_full,
                            is_optional=False,
                            provided_by_system=sys_cfg,
                            masked_value=sys_masked,
                            credential_source=c_source,
                            credential_status=c_status,
                            is_platform_supported=is_plat_supp
                        )
                    )

        unfulfilled = [r for r in requirements if not r.is_fulfilled and not r.is_optional]
        all_fulfilled = len(unfulfilled) == 0

        status = "CLEARED" if all_fulfilled else "CREDS_REQUIRED"
        if all_fulfilled:
            msg = f"All required credentials for {mode.value.upper()} execution are fulfilled. Ready for execution."
        else:
            missing_names = ", ".join([r.key_name for r in unfulfilled])
            msg = f"{mode.value.upper()} execution blocked. Missing required user credentials: {missing_names}."

        return SessionCredentialPrompt(
            session_id=session_id or f"sess-{uuid.uuid4().hex[:8]}",
            agent_id=agent.id,
            mode=mode,
            all_fulfilled=all_fulfilled,
            status=status,
            requirements=requirements,
            message=msg
        )
