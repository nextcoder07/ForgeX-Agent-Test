-- =============================================================================
-- ForgeX Platform — Single Master Production Database Schema (schema.sql)
-- Complete, self-contained, 100% coverage of all 37 tables, indexes, triggers,
-- capability seeds, and jsonb projection columns across all 6 pipeline stages
-- plus the independent Platform-AI Meta-Evaluation Quality Lab.
-- Execute directly in the Supabase SQL Editor or psql CLI.
-- =============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- 0. IDENTITY, MULTI-TENANCY & WORKSPACE ACCESS CONTROL
-- =============================================================================

-- 1. user_profiles — authenticated users synchronized with Firebase Auth UID
CREATE TABLE IF NOT EXISTS user_profiles (
    id                 TEXT PRIMARY KEY,  -- Firebase UID
    email              TEXT NOT NULL,
    display_name       TEXT,
    avatar_url         TEXT,
    role               TEXT NOT NULL DEFAULT 'USER', -- Platform Role: 'USER', 'PLATFORM_ADMIN'
    status             TEXT NOT NULL DEFAULT 'PENDING_EMAIL_VERIFICATION', -- 'PENDING_EMAIL_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'DELETED'
    email_verified_at  TIMESTAMPTZ,
    is_platform_admin  BOOLEAN NOT NULL DEFAULT FALSE,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. workspaces — tenant isolation boundary
CREATE TABLE IF NOT EXISTS workspaces (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    slug               TEXT UNIQUE NOT NULL,
    owner_id           TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    tier               TEXT NOT NULL DEFAULT 'free',
    settings           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. workspace_members — RBAC mapping (OWNER, ADMIN, DEVELOPER, VIEWER)
CREATE TABLE IF NOT EXISTS workspace_members (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    workspace_id       TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id            TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    role               TEXT NOT NULL DEFAULT 'DEVELOPER',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, user_id)
);

-- 4. audit_logs — security and operational audit trail
CREATE TABLE IF NOT EXISTS audit_logs (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    workspace_id       TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id            TEXT REFERENCES user_profiles(id) ON DELETE CASCADE,
    action             TEXT NOT NULL,
    resource_type      TEXT NOT NULL,
    resource_id        TEXT,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_ws ON workspace_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ws ON audit_logs(workspace_id, created_at DESC);

-- =============================================================================
-- 1. STAGE 1: AGENT INTAKE & SPECIFICATION TABLES
-- =============================================================================

-- 5. agents — logical identity of an agent project
CREATE TABLE IF NOT EXISTS agents (
    id                 TEXT PRIMARY KEY,
    workspace_id       TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    owner_id           TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    description        TEXT,
    status             TEXT NOT NULL DEFAULT 'active',
    agent_spec         JSONB,
    current_version_id TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. agent_versions — immutable snapshots of an agent build
CREATE TABLE IF NOT EXISTS agent_versions (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version         TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    artifact_path   TEXT,
    artifact_hash   TEXT NOT NULL DEFAULT '',
    framework       TEXT,
    language        TEXT,
    entrypoint      TEXT,
    agent_spec      JSONB,
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(agent_id, version)
);

-- 3. agent_components — files / modules that make up a version
CREATE TABLE IF NOT EXISTS agent_components (
    id                  TEXT PRIMARY KEY,
    agent_version_id    TEXT NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
    path                TEXT NOT NULL,
    component_type      TEXT,
    language            TEXT,
    content_hash        TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. agent_artifacts — immutable uploaded source manifests
CREATE TABLE IF NOT EXISTS agent_artifacts (
    id                  TEXT PRIMARY KEY,
    agent_id            TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    artifact_type       TEXT NOT NULL DEFAULT 'package',
    storage_provider    TEXT NOT NULL DEFAULT 'supabase_database',
    storage_path        TEXT NOT NULL,
    original_filename   TEXT,
    content_hash        TEXT NOT NULL,
    size_bytes          BIGINT NOT NULL DEFAULT 0,
    mime_type           TEXT,
    file_count          INTEGER NOT NULL DEFAULT 0,
    input_type          TEXT NOT NULL DEFAULT 'package',
    upload_metadata     JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. agent_files — source file contents linked to artifacts
CREATE TABLE IF NOT EXISTS agent_files (
    id                  TEXT PRIMARY KEY,
    agent_artifact_id   TEXT NOT NULL REFERENCES agent_artifacts(id) ON DELETE CASCADE,
    path                TEXT NOT NULL,
    file_type           TEXT,
    language            TEXT,
    size_bytes          BIGINT NOT NULL DEFAULT 0,
    content_hash        TEXT NOT NULL,
    storage_path        TEXT NOT NULL,
    is_entrypoint       BOOLEAN NOT NULL DEFAULT false,
    is_config           BOOLEAN NOT NULL DEFAULT false,
    is_prompt           BOOLEAN NOT NULL DEFAULT false,
    is_tool_definition  BOOLEAN NOT NULL DEFAULT false,
    content             TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. agent_test_specifications — normalized agent test specification
CREATE TABLE IF NOT EXISTS agent_test_specifications (
    id         TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    goal       TEXT,
    inputs     JSONB,
    tools      JSONB,
    workflow   JSONB,
    risks      JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. capabilities — platform canonical capability registry
CREATE TABLE IF NOT EXISTS capabilities (
    id                       TEXT PRIMARY KEY,
    name                     TEXT NOT NULL UNIQUE,
    category                 TEXT NOT NULL,
    description              TEXT,
    default_risk_level       TEXT NOT NULL DEFAULT 'low',
    default_side_effect_type TEXT NOT NULL DEFAULT 'read'
);

INSERT INTO capabilities (id, name, category, description, default_risk_level, default_side_effect_type) VALUES
    ('cap-01', 'CUSTOMER_LOOKUP',    'crm',      'Look up a customer record',           'low',      'read'),
    ('cap-02', 'CUSTOMER_UPDATE',    'crm',      'Modify a customer record',            'medium',   'write'),
    ('cap-03', 'ORDER_LOOKUP',       'commerce', 'Look up an order',                    'low',      'read'),
    ('cap-04', 'ORDER_CANCELLATION', 'commerce', 'Cancel an order',                     'high',     'destructive'),
    ('cap-05', 'REFUND_TRANSACTION', 'finance',  'Issue a monetary refund',             'critical', 'destructive'),
    ('cap-06', 'ADDRESS_UPDATE',     'commerce', 'Update a shipping address',           'medium',   'write'),
    ('cap-07', 'EMAIL_NOTIFICATION', 'comms',    'Send an email to a customer',         'low',      'external'),
    ('cap-08', 'EMAIL_SEND',         'comms',    'Generic email send',                  'low',      'external'),
    ('cap-09', 'DATABASE_READ',      'data',     'Read from a database',                'low',      'read'),
    ('cap-10', 'DATABASE_WRITE',     'data',     'Write to a database',                 'medium',   'write'),
    ('cap-11', 'BROWSER_NAVIGATION', 'web',      'Navigate a web browser',              'medium',   'external'),
    ('cap-12', 'FILE_WRITE',         'storage',  'Write to the filesystem',             'medium',   'write'),
    ('cap-13', 'PAYMENT_EXECUTION',  'finance',  'Execute a payment transaction',       'critical', 'destructive'),
    ('cap-14', 'CODE_EXECUTION',     'compute',  'Execute arbitrary code',              'critical', 'destructive')
ON CONFLICT (name) DO NOTHING;

-- 8. tools
CREATE TABLE IF NOT EXISTS tools (
    id                   TEXT PRIMARY KEY,
    agent_version_id     TEXT NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
    original_name        TEXT NOT NULL,
    description          TEXT,
    tool_type            TEXT NOT NULL,
    canonical_capability TEXT REFERENCES capabilities(name),
    input_schema         JSONB,
    output_schema        JSONB,
    source_type          TEXT NOT NULL DEFAULT 'inferred',
    risk_level           TEXT NOT NULL DEFAULT 'low',
    side_effect_type     TEXT NOT NULL DEFAULT 'read',
    sandbox_available    BOOLEAN NOT NULL DEFAULT false,
    adapter_available    BOOLEAN NOT NULL DEFAULT false,
    status               TEXT NOT NULL DEFAULT 'discovered',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. dependencies
CREATE TABLE IF NOT EXISTS dependencies (
    id                TEXT PRIMARY KEY,
    agent_version_id  TEXT NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    dependency_type   TEXT NOT NULL,
    required          BOOLEAN NOT NULL DEFAULT true,
    detected_from     TEXT,
    configuration     JSONB,
    status            TEXT NOT NULL DEFAULT 'unknown',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 2. STAGE 2: SCENARIO INTELLIGENCE & EVALUATION SUITE
-- =============================================================================

-- 10. scenario_sets — evaluation scenario suites
CREATE TABLE IF NOT EXISTS scenario_sets (
    id               TEXT PRIMARY KEY,
    agent_id         TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_version_id TEXT REFERENCES agent_versions(id) ON DELETE SET NULL,
    name             TEXT NOT NULL,
    description      TEXT,
    generation_type  TEXT NOT NULL DEFAULT 'synthetic',
    total_scenarios  INTEGER NOT NULL DEFAULT 0,
    category_counts  JSONB,
    status           TEXT NOT NULL DEFAULT 'ready',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. scenarios — individual test cases with complete query projection
CREATE TABLE IF NOT EXISTS scenarios (
    id                             TEXT PRIMARY KEY,
    scenario_set_id                TEXT REFERENCES scenario_sets(id) ON DELETE CASCADE,
    agent_id                       TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    title                          TEXT NOT NULL,
    purpose                        TEXT NOT NULL,
    category                       TEXT NOT NULL,
    target_subsystem               TEXT NOT NULL DEFAULT 'reasoning_planning',
    subsystem_evaluation_criteria  JSONB DEFAULT '[]'::jsonb,
    context_preconditions          JSONB DEFAULT '{}'::jsonb,
    expected_subsystem_transitions JSONB DEFAULT '[]'::jsonb,
    difficulty                     TEXT NOT NULL DEFAULT 'medium',
    status                         TEXT NOT NULL DEFAULT 'validated',
    interface_type                 TEXT NOT NULL DEFAULT 'CHAT',
    invocation                     JSONB,
    input_artifacts                JSONB,
    input_values                   JSONB,
    environment_conditions         JSONB,
    target_failure_surface         TEXT,
    target_invariant               TEXT,
    fault_injections               JSONB,
    assertions                     JSONB,
    provenance                     JSONB,
    fingerprint                    TEXT,
    validation_status              TEXT NOT NULL DEFAULT 'VALIDATED',
    critic_status                  TEXT NOT NULL DEFAULT 'PASSED',
    agent_version_id               TEXT REFERENCES agent_versions(id) ON DELETE SET NULL,
    scenario_spec                  JSONB,

    -- Broad Agent Coverage & Behavioral Contracts
    agent_type                     TEXT DEFAULT 'tool_agent',
    interaction_mode               TEXT DEFAULT 'single_turn',
    input_type                     TEXT DEFAULT 'text',
    statefulness                   TEXT DEFAULT 'stateless',
    behavioral_objective          TEXT DEFAULT 'COMPLETE_USER_GOAL',
    required_tools                 JSONB DEFAULT '[]'::jsonb,
    forbidden_tools                JSONB DEFAULT '[]'::jsonb,
    expected_call_sequence         JSONB DEFAULT '[]'::jsonb,
    side_effect_policy             TEXT DEFAULT 'none',
    confirmation_required          BOOLEAN DEFAULT false,
    external_services              JSONB DEFAULT '[]'::jsonb,
    expected_output_constraints    JSONB DEFAULT '{}'::jsonb,
    security_constraints           JSONB DEFAULT '[]'::jsonb,
    state_invariants               JSONB DEFAULT '[]'::jsonb,
    max_actions                    INTEGER DEFAULT 10,
    evaluation_dimensions          JSONB DEFAULT '[]'::jsonb,
    severity_if_violated           TEXT DEFAULT 'HIGH',
    evidence_requirements          JSONB DEFAULT '[]'::jsonb,
    execution_mode                 TEXT DEFAULT 'faithful',

    created_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 3. STAGE 3: SETUP & GATEWAY RESOLUTION TABLES
-- =============================================================================

-- 12. sandbox_specifications — execution environment manifests
CREATE TABLE IF NOT EXISTS sandbox_specifications (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    language        TEXT NOT NULL DEFAULT 'python',
    runtime_version TEXT NOT NULL DEFAULT '3.12',
    base_image      TEXT NOT NULL DEFAULT 'python:3.12-slim',
    entrypoint      TEXT NOT NULL DEFAULT 'agent.py',
    runtime         JSONB,
    dependencies    JSONB,
    filesystem      JSONB,
    network         JSONB,
    tools           JSONB,
    credentials     JSONB,
    status          TEXT NOT NULL DEFAULT 'READY',
    blockers        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. agent_dependencies — intake discovered requirement list
CREATE TABLE IF NOT EXISTS agent_dependencies (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    dependency_name TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'runtime',
    required        BOOLEAN NOT NULL DEFAULT true,
    detected_from   TEXT NOT NULL DEFAULT 'source_code',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 14. platform_resources — mock & external sandbox infrastructure
CREATE TABLE IF NOT EXISTS platform_resources (
    id         TEXT PRIMARY KEY,
    capability TEXT NOT NULL,
    provider   TEXT NOT NULL,
    mode       TEXT NOT NULL DEFAULT 'sandbox',
    status     TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 15. dependency_bindings — resolution status mapping
CREATE TABLE IF NOT EXISTS dependency_bindings (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    dependency_name TEXT NOT NULL,
    resolution_type TEXT NOT NULL DEFAULT 'block',
    status          TEXT NOT NULL DEFAULT 'unsupported',
    user_value      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 16. model_connections — registered cloud API keys & local ML servers
CREATE TABLE IF NOT EXISTS model_connections (
    id                       TEXT PRIMARY KEY,
    workspace_id             TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id                  TEXT REFERENCES user_profiles(id) ON DELETE CASCADE,
    name                     TEXT NOT NULL,
    provider                 TEXT NOT NULL,
    base_url                 TEXT NOT NULL DEFAULT '',
    model_identifier         TEXT NOT NULL,
    api_key                  TEXT,
    role                     TEXT NOT NULL DEFAULT 'general',
    is_local                 BOOLEAN NOT NULL DEFAULT false,
    health_status            TEXT NOT NULL DEFAULT 'healthy',
    latency_ms               FLOAT NOT NULL DEFAULT 0.0,
    supports_structured_json BOOLEAN NOT NULL DEFAULT true,
    metadata                 JSONB,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_connections_user ON model_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_model_connections_ws ON model_connections(workspace_id);

-- 17. system_credentials — platform credential vault
CREATE TABLE IF NOT EXISTS system_credentials (
    key_name        TEXT PRIMARY KEY,
    masked_value    TEXT NOT NULL,
    encrypted_value TEXT,
    is_set          BOOLEAN NOT NULL DEFAULT true,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 18. user_credentials — multi-tenant user API keys and secrets vault
CREATE TABLE IF NOT EXISTS user_credentials (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id            TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    workspace_id       TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
    key_name           TEXT NOT NULL,
    provider           TEXT NOT NULL DEFAULT 'custom',
    masked_value       TEXT NOT NULL,
    raw_value          TEXT NOT NULL,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, key_name)
);

CREATE INDEX IF NOT EXISTS idx_user_credentials_user ON user_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_user_credentials_ws ON user_credentials(workspace_id);

-- 19. agent_model_bindings — slot-to-model configuration mapping
CREATE TABLE IF NOT EXISTS agent_model_bindings (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    agent_id           TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    slot_id            TEXT NOT NULL,
    connection_id      TEXT REFERENCES model_connections(id) ON DELETE SET NULL,
    provider           TEXT NOT NULL DEFAULT 'openai',
    model_identifier   TEXT NOT NULL DEFAULT 'default',
    api_key_override   TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(agent_id, slot_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_model_bindings_agent ON agent_model_bindings(agent_id);

-- 20. agent_configurations — user-scoped persistent configuration for each agent
CREATE TABLE IF NOT EXISTS agent_configurations (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id            TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    agent_id           TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    execution_mode     TEXT NOT NULL DEFAULT 'faithful',
    selected_provider  TEXT NOT NULL DEFAULT 'openai',
    selected_model     TEXT NOT NULL DEFAULT 'default',
    configuration_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_configurations_user_agent ON agent_configurations(user_id, agent_id);

-- 21. agent_credentials — encrypted user API keys and secrets per agent
CREATE TABLE IF NOT EXISTS agent_credentials (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id            TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    agent_id           TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    credential_name    TEXT NOT NULL,
    credential_type    TEXT NOT NULL DEFAULT 'api_key',
    provider           TEXT NOT NULL DEFAULT 'custom',
    encrypted_value    TEXT NOT NULL,
    masked_value       TEXT NOT NULL,
    validation_status  TEXT NOT NULL DEFAULT 'SAVED',
    last_validated_at  TIMESTAMPTZ,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, agent_id, credential_name)
);

CREATE INDEX IF NOT EXISTS idx_agent_credentials_lookup ON agent_credentials(user_id, agent_id, credential_name);

-- 22. agent_setup_states — persisted setup readiness and preflight blockers per agent
CREATE TABLE IF NOT EXISTS agent_setup_states (
    id                         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id                    TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    agent_id                   TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    setup_status               TEXT NOT NULL DEFAULT 'NOT_READY',
    preflight_status           TEXT NOT NULL DEFAULT 'NOT_READY',
    requirements_json          JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolved_dependencies_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    blockers_json              JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_checked_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_setup_states_lookup ON agent_setup_states(user_id, agent_id);

-- =============================================================================
-- 4. STAGE 4: EXECUTION & RUNTIME TRACING TABLES
-- =============================================================================

-- 18. pipeline_runs — intake and evaluation pipeline jobs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            TEXT PRIMARY KEY,
    agent_id      TEXT REFERENCES agents(id) ON DELETE CASCADE,
    pipeline_type TEXT NOT NULL DEFAULT 'agent_intake',
    status        TEXT NOT NULL DEFAULT 'queued',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ
);

-- 19. execution_jobs — batch execution queue jobs
CREATE TABLE IF NOT EXISTS execution_jobs (
    id                  TEXT PRIMARY KEY,
    agent_id            TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_name          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    total_scenarios     INTEGER NOT NULL DEFAULT 0,
    completed_scenarios INTEGER NOT NULL DEFAULT 0,
    scenario_ids        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ
);

-- 20. evaluation_runs — execution test runs with full projection
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                       TEXT PRIMARY KEY,
    scenario_set_id          TEXT REFERENCES scenario_sets(id) ON DELETE SET NULL,
    agent_id                 TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_version_id         TEXT REFERENCES agent_versions(id) ON DELETE SET NULL,
    run_type                 TEXT NOT NULL DEFAULT 'evaluation',
    execution_mode           TEXT NOT NULL DEFAULT 'faithful',
    status                   TEXT NOT NULL DEFAULT 'pending',
    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,
    total_scenarios          INTEGER NOT NULL DEFAULT 0,
    passed_scenarios         INTEGER NOT NULL DEFAULT 0,
    failed_scenarios         INTEGER NOT NULL DEFAULT 0,
    errored_scenarios        INTEGER NOT NULL DEFAULT 0,
    total_verdicts           INTEGER NOT NULL DEFAULT 0,
    execution_run_id         TEXT,
    sandbox_specification_id TEXT,
    behavior_profile_id      TEXT,
    original_model           TEXT DEFAULT 'openai/gpt-4o',
    executed_model           TEXT DEFAULT 'openai/gpt-4o',
    model_substitution       BOOLEAN DEFAULT false,
    confidence               TEXT DEFAULT 'HIGH',
    fidelity                 FLOAT DEFAULT 1.0,
    evaluator_version        TEXT DEFAULT 'v2.0',
    rule_set_version         TEXT DEFAULT 'reliability-rules-v2',
    scorecard                JSONB,
    config                   JSONB,
    job_spec                 JSONB,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 21. execution_sessions — scenario execution sandbox sessions
CREATE TABLE IF NOT EXISTS execution_sessions (
    id                 TEXT PRIMARY KEY,
    evaluation_run_id  TEXT REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    agent_version_id   TEXT,
    scenario_id        TEXT REFERENCES scenarios(id) ON DELETE CASCADE,
    sandbox_session_id TEXT,
    status             TEXT NOT NULL DEFAULT 'active',
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ
);

-- 22. execution_steps — granular step-by-step trace events
CREATE TABLE IF NOT EXISTS execution_steps (
    id                   TEXT PRIMARY KEY,
    execution_session_id TEXT NOT NULL REFERENCES execution_sessions(id) ON DELETE CASCADE,
    step_number          INTEGER NOT NULL DEFAULT 0,
    event_type           TEXT NOT NULL DEFAULT 'OBSERVATION',
    actor                TEXT NOT NULL DEFAULT 'agent',
    input_data           JSONB,
    output_data          JSONB,
    metadata             JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 23. execution_metrics — token, latency, and cost telemetry
CREATE TABLE IF NOT EXISTS execution_metrics (
    id                   TEXT PRIMARY KEY,
    execution_session_id TEXT NOT NULL REFERENCES execution_sessions(id) ON DELETE CASCADE,
    steps_count          INTEGER NOT NULL DEFAULT 0,
    tool_calls_count     INTEGER NOT NULL DEFAULT 0,
    failed_tools         INTEGER NOT NULL DEFAULT 0,
    tokens_used          INTEGER NOT NULL DEFAULT 0,
    latency_ms           FLOAT NOT NULL DEFAULT 0.0,
    cost                 FLOAT NOT NULL DEFAULT 0.0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 24. scenario_results — detailed assertion & trace result per scenario
CREATE TABLE IF NOT EXISTS scenario_results (
    id                   TEXT PRIMARY KEY,
    evaluation_run_id    TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    scenario_id          TEXT NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    status               TEXT NOT NULL DEFAULT 'pending',
    execution_time_ms    FLOAT NOT NULL DEFAULT 0.0,
    tokens_used          INTEGER NOT NULL DEFAULT 0,
    output_text          TEXT,
    structured_output    JSONB,
    error_message        TEXT,
    error_type           TEXT,
    tool_calls           JSONB,
    executed_path        JSONB,
    assertions_evaluated JSONB,
    assertion_pass_rate  FLOAT NOT NULL DEFAULT 0.0,
    evaluation_metadata  JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 25. ai_generation_runs — LLM usage audit log
CREATE TABLE IF NOT EXISTS ai_generation_runs (
    id               TEXT PRIMARY KEY,
    stage            TEXT NOT NULL,
    provider         TEXT NOT NULL DEFAULT 'gemini',
    model            TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'SUCCESS',
    input_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT,
    prompt_version   TEXT NOT NULL DEFAULT 'v1',
    input_reference  TEXT,
    output_reference TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 5. STAGE 5 & 6: RESULTS & IMPROVE (TRAINING DATASETS & ADAPTERS)
-- =============================================================================

-- 26. failure_clusters — grouped root-cause vulnerability analyses
CREATE TABLE IF NOT EXISTS failure_clusters (
    id                     TEXT PRIMARY KEY,
    evaluation_run_id      TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    title                  TEXT NOT NULL,
    category               TEXT NOT NULL,
    failure_surface        TEXT,
    severity               TEXT NOT NULL DEFAULT 'medium',
    affected_scenario_ids  JSONB,
    root_cause_explanation TEXT,
    recommended_fix        TEXT,
    suggested_patch        TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 27. training_datasets — SFT & DPO training data exports
CREATE TABLE IF NOT EXISTS training_datasets (
    id                     TEXT PRIMARY KEY,
    agent_id               TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_name             TEXT,
    name                   TEXT NOT NULL,
    description            TEXT,
    dataset_type           TEXT NOT NULL DEFAULT 'HYBRID',
    format                 TEXT NOT NULL DEFAULT 'jsonl',
    example_count          INTEGER NOT NULL DEFAULT 0,
    sft_examples           JSONB,
    preference_pairs       JSONB,
    recovery_examples      JSONB,
    source_scenarios       JSONB,
    source_execution_runs  JSONB,
    export_ready           BOOLEAN NOT NULL DEFAULT true,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 28. model_versions — trained model checkpoints & LoRA adapters
CREATE TABLE IF NOT EXISTS model_versions (
    id                     TEXT PRIMARY KEY,
    agent_id               TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    adapter_name           TEXT NOT NULL,
    base_model             TEXT NOT NULL,
    dataset_id             TEXT REFERENCES training_datasets(id) ON DELETE SET NULL,
    status                 TEXT NOT NULL DEFAULT 'ready',
    metrics                JSONB,
    checkpoint_path        TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 6. PERFORMANCE INDEXES
-- =============================================================================

CREATE TABLE IF NOT EXISTS stage_judge_audits (
    id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    tester_session_id TEXT NOT NULL,
    model_used TEXT NOT NULL,
    provider_used TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER NOT NULL,
    fidelity_score DOUBLE PRECISION NOT NULL,
    summary TEXT NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    strengths JSONB DEFAULT '[]'::jsonb,
    findings_and_discrepancies JSONB DEFAULT '[]'::jsonb,
    hallucination_detected BOOLEAN DEFAULT FALSE,
    recommendations JSONB DEFAULT '[]'::jsonb,
    latency_ms DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 29. multi_agent_stage_audits — cross-agent meta verdicts & training data synthesis
CREATE TABLE IF NOT EXISTS multi_agent_stage_audits (
    id TEXT PRIMARY KEY,
    stage_name TEXT NOT NULL,
    agent_count INTEGER NOT NULL DEFAULT 0,
    overall_status TEXT NOT NULL,
    overall_score INTEGER NOT NULL,
    overall_improvement_needed TEXT NOT NULL,
    system_prompt_recommendations JSONB DEFAULT '[]'::jsonb,
    code_remediation_recommendations JSONB DEFAULT '[]'::jsonb,
    agent_results JSONB DEFAULT '[]'::jsonb,
    training_dataset JSONB DEFAULT '[]'::jsonb,
    local_fallback_model TEXT NOT NULL,
    tester_fallback_model TEXT NOT NULL,
    latency_ms DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 30. stage_fallback_models — registry of dedicated local fallback LLMs for fine-tuning
CREATE TABLE IF NOT EXISTS stage_fallback_models (
    stage_name TEXT PRIMARY KEY,
    model_slot TEXT NOT NULL,
    local_model_name TEXT NOT NULL,
    is_trainable BOOLEAN NOT NULL DEFAULT true,
    dataset_record_count INTEGER NOT NULL DEFAULT 0,
    last_trained_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 31. stage_model_bindings — stage-specific primary and fallback bindings
CREATE TABLE IF NOT EXISTS stage_model_bindings (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    primary_connection_id TEXT NOT NULL DEFAULT 'cloud_rotation_pool',
    fallback_connection_id TEXT NOT NULL,
    active_connection_id TEXT NOT NULL DEFAULT 'primary',
    fallback_enabled BOOLEAN NOT NULL DEFAULT true,
    primary_model TEXT NOT NULL DEFAULT 'gemini-3.6-flash',
    fallback_model TEXT NOT NULL DEFAULT 'qwen2.5-coder:7b',
    adapter_reference TEXT,
    health_status TEXT NOT NULL DEFAULT 'HEALTHY',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 32. platform_model_versions — trainable fallback adapter checkpoints
CREATE TABLE IF NOT EXISTS platform_model_versions (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    base_model TEXT NOT NULL DEFAULT 'qwen2.5-coder:7b',
    adapter_name TEXT NOT NULL,
    version_label TEXT NOT NULL,
    training_job_id TEXT,
    parent_version_id TEXT,
    status TEXT NOT NULL DEFAULT 'PROMOTED',
    benchmark_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    held_out_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 33. stage_performance_reports — meta-evaluation benchmark history
CREATE TABLE IF NOT EXISTS stage_performance_reports (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    model_connection_id TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    agents_tested INTEGER NOT NULL DEFAULT 0,
    cases_evaluated INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    missed_count INTEGER NOT NULL DEFAULT 0,
    false_positive_count INTEGER NOT NULL DEFAULT 0,
    accuracy_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    precision_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    recall_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    coverage_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    quality_score INTEGER NOT NULL DEFAULT 0,
    failure_categories JSONB DEFAULT '[]'::jsonb,
    system_prompt_improvements JSONB DEFAULT '[]'::jsonb,
    code_remediation_rules JSONB DEFAULT '[]'::jsonb,
    training_candidates_count INTEGER NOT NULL DEFAULT 0,
    evidence_references JSONB DEFAULT '[]'::jsonb,
    latency_ms DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 34. scorecards — evaluation scorecard store
CREATE TABLE IF NOT EXISTS scorecards (
    evaluation_id TEXT PRIMARY KEY,
    agent_id TEXT,
    agent_name TEXT,
    agent_version TEXT,
    correctness DOUBLE PRECISION DEFAULT 0.0,
    safety DOUBLE PRECISION DEFAULT 0.0,
    robustness DOUBLE PRECISION DEFAULT 0.0,
    tool_discipline DOUBLE PRECISION DEFAULT 0.0,
    goal_adherence DOUBLE PRECISION DEFAULT 0.0,
    composite DOUBLE PRECISION DEFAULT 0.0,
    safety_axis DOUBLE PRECISION DEFAULT 0.0,
    capability_axis DOUBLE PRECISION DEFAULT 0.0,
    total_scenarios INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0,
    inconclusive INTEGER DEFAULT 0,
    critical_failures INTEGER DEFAULT 0,
    judge_agreement_rate DOUBLE PRECISION,
    score_formula_version TEXT DEFAULT 'v2.0-weighted',
    scorecard_spec JSONB,

    -- Behavioral Reliability & Positive Confirmation
    overall_result TEXT DEFAULT 'PASS',
    status_title TEXT,
    status_summary TEXT,
    is_healthy_agent BOOLEAN DEFAULT false,
    behavioral_summary JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 35. agent_behavior_profiles — extracted behavioral contracts & invariants
CREATE TABLE IF NOT EXISTS agent_behavior_profiles (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_version_id TEXT,
    schema_version TEXT NOT NULL DEFAULT 'v1',
    identity JSONB DEFAULT '{}'::jsonb,
    goal TEXT DEFAULT '',
    interface_contract JSONB DEFAULT '{}'::jsonb,
    output_contract JSONB DEFAULT '{}'::jsonb,
    dependency_requirements JSONB DEFAULT '[]'::jsonb,
    workflow_graph JSONB DEFAULT '{}'::jsonb,
    inputs JSONB DEFAULT '[]'::jsonb,
    outputs JSONB DEFAULT '[]'::jsonb,
    state_model JSONB DEFAULT '{}'::jsonb,
    external_calls JSONB DEFAULT '[]'::jsonb,
    capabilities JSONB DEFAULT '[]'::jsonb,
    data_transformations JSONB DEFAULT '[]'::jsonb,
    invariants JSONB DEFAULT '[]'::jsonb,
    failure_surfaces JSONB DEFAULT '[]'::jsonb,
    security_surfaces JSONB DEFAULT '[]'::jsonb,
    side_effects JSONB DEFAULT '[]'::jsonb,
    declared_behaviors JSONB DEFAULT '[]'::jsonb,
    observed_behaviors JSONB DEFAULT '[]'::jsonb,
    conflicts JSONB DEFAULT '[]'::jsonb,
    readiness JSONB DEFAULT '{}'::jsonb,
    confidence_score DOUBLE PRECISION DEFAULT 1.0,
    analysis_run_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 36. evaluation_verdicts & evaluation_traces — execution evidence payloads
CREATE TABLE IF NOT EXISTS evaluation_verdicts (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    scenario_id TEXT,
    trace_id TEXT,
    execution_session_id TEXT,
    passed BOOLEAN DEFAULT true,
    status TEXT NOT NULL DEFAULT 'PASS',
    deterministic_score DOUBLE PRECISION DEFAULT 100.0,
    semantic_score DOUBLE PRECISION,
    final_score DOUBLE PRECISION DEFAULT 100.0,
    findings JSONB DEFAULT '[]'::jsonb,
    record_type TEXT NOT NULL DEFAULT 'verdicts',
    evidence JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluation_traces (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    scenario_id TEXT,
    agent_id TEXT,
    agent_version TEXT,
    execution_id TEXT,
    session_id TEXT,
    raw_stdout TEXT,
    raw_stderr TEXT,
    exit_code INTEGER DEFAULT 0,
    runtime_status TEXT DEFAULT 'COMPLETED',
    fault_injections JSONB DEFAULT '[]'::jsonb,
    artifacts JSONB DEFAULT '[]'::jsonb,
    record_type TEXT NOT NULL DEFAULT 'traces',
    status TEXT NOT NULL DEFAULT 'completed',
    evidence JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 37. execution_preflights, runs, artifacts & repair sessions
CREATE TABLE IF NOT EXISTS execution_preflights (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    environment_check TEXT,
    dependency_check TEXT,
    tool_check TEXT,
    status TEXT NOT NULL DEFAULT 'PASSED',
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_runs (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    scenario_id TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    raw_logs TEXT,
    structured_events JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_artifacts (
    id TEXT PRIMARY KEY,
    execution_run_id TEXT NOT NULL,
    artifact_name TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    mime_type TEXT,
    size_bytes BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_actions (
    id TEXT PRIMARY KEY,
    execution_session_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repair_sessions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    evaluation_run_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    iteration_count INTEGER DEFAULT 0,
    patches JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS regression_tests (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    scenario_id TEXT,
    baseline_run_id TEXT,
    post_repair_run_id TEXT,
    regression_status TEXT NOT NULL DEFAULT 'PASS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS diagnosis_reports (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    findings JSONB DEFAULT '[]'::jsonb,
    recommendations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS training_jobs (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    dataset_id TEXT,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    loss_curve JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS benchmark_records (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    model_v1 TEXT NOT NULL,
    model_v2 TEXT NOT NULL,
    accuracy_delta DOUBLE PRECISION DEFAULT 0.0,
    verdict TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 38. findings — discrete evaluation findings & invariant failure records
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT,
    scenario_id TEXT,
    dimension TEXT,
    severity TEXT NOT NULL DEFAULT 'medium',
    category TEXT,
    title TEXT NOT NULL,
    description TEXT,
    evidence JSONB DEFAULT '{}'::jsonb,
    root_cause JSONB DEFAULT '{}'::jsonb,
    remediation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 39. patch_artifacts — autonomous code AST patches & prompt repair artifacts
CREATE TABLE IF NOT EXISTS patch_artifacts (
    id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
    evaluation_run_id TEXT,
    status TEXT NOT NULL DEFAULT 'PROPOSED',
    file_patches JSONB DEFAULT '[]'::jsonb,
    system_prompt_patch TEXT,
    target_findings JSONB DEFAULT '[]'::jsonb,
    risk_assessment JSONB DEFAULT '{}'::jsonb,
    verification_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 40. canonical_test_cases — normalized executable test specifications
CREATE TABLE IF NOT EXISTS canonical_test_cases (
    id TEXT PRIMARY KEY,
    scenario_id TEXT,
    agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
    agent_version TEXT NOT NULL DEFAULT 'v1.0',
    dimension TEXT,
    metric_id TEXT,
    title TEXT NOT NULL,
    intent TEXT,
    preconditions JSONB DEFAULT '{}'::jsonb,
    input_payload JSONB DEFAULT '{}'::jsonb,
    expected_behavior JSONB DEFAULT '[]'::jsonb,
    forbidden_behavior JSONB DEFAULT '[]'::jsonb,
    expected_tools JSONB DEFAULT '[]'::jsonb,
    assertions JSONB DEFAULT '[]'::jsonb,
    severity TEXT NOT NULL DEFAULT 'HIGH',
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 41. evidence_graphs — execution trajectory dependency and violation graphs
CREATE TABLE IF NOT EXISTS evidence_graphs (
    id TEXT PRIMARY KEY,
    scenario_id TEXT,
    execution_session_id TEXT,
    nodes JSONB DEFAULT '[]'::jsonb,
    edges JSONB DEFAULT '[]'::jsonb,
    sealed_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 6. PERFORMANCE INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_id ON agent_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_artifacts_agent_id ON agent_artifacts(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_files_artifact_id ON agent_files(agent_artifact_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_set_id ON scenarios(scenario_set_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_agent_id ON scenarios(agent_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_target_subsystem ON scenarios(target_subsystem);
CREATE INDEX IF NOT EXISTS idx_eval_runs_agent_id ON evaluation_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_scenario_results_run_id ON scenario_results(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_failure_clusters_run_id ON failure_clusters(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_training_datasets_agent ON training_datasets(agent_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_agent ON model_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_execution_sessions_eval ON execution_sessions(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_execution_steps_session ON execution_steps(execution_session_id);
CREATE INDEX IF NOT EXISTS idx_execution_metrics_session ON execution_metrics(execution_session_id);
CREATE INDEX IF NOT EXISTS idx_stage_audits_agent ON stage_judge_audits(agent_id);
CREATE INDEX IF NOT EXISTS idx_multi_audits_stage ON multi_agent_stage_audits(stage_name);
CREATE INDEX IF NOT EXISTS idx_behavior_profiles_agent ON agent_behavior_profiles(agent_id);
CREATE INDEX IF NOT EXISTS idx_scorecards_agent ON scorecards(agent_id);
CREATE INDEX IF NOT EXISTS idx_stage_perf_stage ON stage_performance_reports(stage);
CREATE INDEX IF NOT EXISTS idx_findings_eval_run ON findings(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_patch_artifacts_agent ON patch_artifacts(agent_id);
CREATE INDEX IF NOT EXISTS idx_canonical_tests_agent ON canonical_test_cases(agent_id);
CREATE INDEX IF NOT EXISTS idx_evidence_graphs_scenario ON evidence_graphs(scenario_id);

-- =============================================================================
-- 6. ADMIN TELEMETRY & WORKSPACE PERFORMANCE INDEXES
-- =============================================================================

-- 38. admin_telemetry_submissions — user-shared evaluation & training telemetry
CREATE TABLE IF NOT EXISTS admin_telemetry_submissions (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
    user_id      TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    user_email   TEXT,
    agent_id     TEXT REFERENCES agents(id) ON DELETE SET NULL,
    eval_job_id  TEXT,
    status       TEXT NOT NULL DEFAULT 'submitted', -- submitted, approved_for_training, archived
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Primary multi-tenant workspace indexes
CREATE INDEX IF NOT EXISTS idx_agents_workspace_id ON agents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_agents_owner_id ON agents(owner_id);
CREATE INDEX IF NOT EXISTS idx_admin_telemetry_user ON admin_telemetry_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_telemetry_status ON admin_telemetry_submissions(status);

-- =============================================================================
-- 7. AUTOMATED TIMESTAMP UPDATER TRIGGER
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_model_connections_updated_at
    BEFORE UPDATE ON model_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_stage_fallback_models_updated_at
    BEFORE UPDATE ON stage_fallback_models
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Done! Complete master schema.sql with multi-tenancy & admin telemetry.

