-- =============================================================================
-- ForgeX Platform — Single Master Production Database Schema (schema.sql)
-- Complete, self-contained, 100% coverage of all 28 tables, indexes, triggers,
-- capability seeds, and jsonb projection columns across all 6 pipeline stages.
-- Execute directly in the Supabase SQL Editor or psql CLI.
-- =============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- 1. STAGE 1: AGENT INTAKE & SPECIFICATION TABLES
-- =============================================================================

-- 1. agents — logical identity of an agent project
CREATE TABLE IF NOT EXISTS agents (
    id                 TEXT PRIMARY KEY,
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
    id                     TEXT PRIMARY KEY,
    scenario_set_id        TEXT REFERENCES scenario_sets(id) ON DELETE CASCADE,
    agent_id               TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    title                  TEXT NOT NULL,
    purpose                TEXT NOT NULL,
    category               TEXT NOT NULL,
    difficulty             TEXT NOT NULL DEFAULT 'medium',
    status                 TEXT NOT NULL DEFAULT 'validated',
    interface_type         TEXT NOT NULL DEFAULT 'CHAT',
    invocation             JSONB,
    input_artifacts        JSONB,
    input_values           JSONB,
    environment_conditions JSONB,
    target_failure_surface TEXT,
    target_invariant       TEXT,
    fault_injections       JSONB,
    assertions             JSONB,
    provenance             JSONB,
    fingerprint            TEXT,
    validation_status      TEXT NOT NULL DEFAULT 'VALIDATED',
    critic_status          TEXT NOT NULL DEFAULT 'PASSED',
    agent_version_id       TEXT REFERENCES agent_versions(id) ON DELETE SET NULL,
    scenario_spec          JSONB,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
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
    name                     TEXT NOT NULL,
    provider                 TEXT NOT NULL,
    base_url                 TEXT NOT NULL,
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

-- 17. system_credentials — encrypted platform credential vault
CREATE TABLE IF NOT EXISTS system_credentials (
    key_name        TEXT PRIMARY KEY,
    masked_value    TEXT NOT NULL,
    encrypted_value TEXT,
    is_set          BOOLEAN NOT NULL DEFAULT true,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_id ON agent_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_artifacts_agent_id ON agent_artifacts(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_files_artifact_id ON agent_files(agent_artifact_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_set_id ON scenarios(scenario_set_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_agent_id ON scenarios(agent_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_agent_id ON evaluation_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_scenario_results_run_id ON scenario_results(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_failure_clusters_run_id ON failure_clusters(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_training_datasets_agent ON training_datasets(agent_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_agent ON model_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_execution_sessions_eval ON execution_sessions(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_execution_steps_session ON execution_steps(execution_session_id);
CREATE INDEX IF NOT EXISTS idx_execution_metrics_session ON execution_metrics(execution_session_id);

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

-- Done! Complete, non-abbreviated master schema.sql.
