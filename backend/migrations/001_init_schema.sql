-- =============================================================================
-- Agent Evaluation & Reliability Platform — V1 Schema (Robust String-ID Version)
-- Two-layer architecture: permanent (public schema) + runtime (runtime schema)
-- Run this once against your Supabase project via the SQL editor.
-- =============================================================================

-- Enable extension for uuid helper functions just in case
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- PERMANENT SCHEMA (public)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- agents — logical identity of an agent project
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,  -- e.g. "agent-cust-v1" or uuid
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    agent_spec      JSONB, -- normalized spec used by the current control-plane store
    current_version_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- agent_versions — immutable snapshots of an agent build
-- ---------------------------------------------------------------------------
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
    agent_spec      JSONB, -- contains full metadata
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(agent_id, version)
);

-- ---------------------------------------------------------------------------
-- agent_components — files / modules that make up a version
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- agent_artifacts / agent_files — immutable uploaded source manifests
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_artifacts (
    id                  TEXT PRIMARY KEY,
    agent_id            TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS agent_files (
    id                  TEXT PRIMARY KEY,
    agent_artifact_id   TEXT NOT NULL,
    path                TEXT NOT NULL,
    file_type           TEXT,
    language            TEXT,
    size_bytes          BIGINT NOT NULL DEFAULT 0,
    content_hash        TEXT NOT NULL,
    storage_path        TEXT NOT NULL,
    is_entrypoint       BOOLEAN NOT NULL DEFAULT false,
    is_config           BOOLEAN NOT NULL DEFAULT false,
    is_prompt           BOOLEAN NOT NULL DEFAULT false,
    is_tool_definition   BOOLEAN NOT NULL DEFAULT false,
    content             TEXT,
    metadata             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- capabilities — platform canonical capability registry
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- tools
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- dependencies
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- scenario_sets
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scenario_sets (
    id                TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    description       TEXT,
    generation_status TEXT DEFAULT 'manual',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- scenarios — flexible to support stand-alone or group scenarios
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scenarios (
    id                 TEXT PRIMARY KEY,
    agent_id           TEXT,
    scenario_set_id    TEXT REFERENCES scenario_sets(id) ON DELETE CASCADE,
    category           TEXT NOT NULL,
    title              TEXT NOT NULL,
    purpose            TEXT,
    current_version_id TEXT,
    status             TEXT NOT NULL DEFAULT 'draft',
    scenario_spec      JSONB, -- Full deserialization backup
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- evaluation_runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                       TEXT PRIMARY KEY,
    agent_version_id         TEXT REFERENCES agent_versions(id) ON DELETE SET NULL,
    name                     TEXT,
    mode                     TEXT NOT NULL,
    status                   TEXT NOT NULL DEFAULT 'queued',
    total_scenarios          INTEGER DEFAULT 0,
    completed_scenarios      INTEGER DEFAULT 0,
    passed_scenarios         INTEGER DEFAULT 0,
    failed_scenarios         INTEGER DEFAULT 0,
    blocked_scenarios        INTEGER DEFAULT 0,
    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- evaluation_results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluation_results (
    id                  TEXT PRIMARY KEY,
    evaluation_run_id   TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    scenario_id         TEXT REFERENCES scenarios(id) ON DELETE SET NULL,
    status              TEXT NOT NULL,
    task_score          NUMERIC,
    tool_score          NUMERIC,
    safety_score        NUMERIC,
    reliability_score   NUMERIC,
    recovery_score      NUMERIC,
    efficiency_score    NUMERIC,
    overall_score       NUMERIC,
    fidelity_level      TEXT,
    evidence            JSONB,
    summary             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- scorecards — stores evaluation aggregate scorecards
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scorecards (
    evaluation_id           TEXT PRIMARY KEY,
    agent_id                TEXT,
    agent_name              TEXT,
    agent_version           TEXT,
    correctness             NUMERIC,
    safety                  NUMERIC,
    robustness              NUMERIC,
    tool_discipline         NUMERIC,
    goal_adherence          NUMERIC,
    composite               NUMERIC,
    safety_axis             NUMERIC,
    capability_axis         NUMERIC,
    total_scenarios         INTEGER,
    passed                  INTEGER,
    failed                  INTEGER,
    critical_failures       INTEGER,
    judge_agreement_rate    NUMERIC,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- failure_clusters
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failure_clusters (
    id                      TEXT PRIMARY KEY,
    evaluation_id           TEXT NOT NULL,
    label                   TEXT,
    category                TEXT,
    member_verdict_ids      JSONB,
    representative_evidence TEXT,
    count                   INTEGER,
    severity                TEXT,
    recommended_fix         TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- reports
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reports (
    id                TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    report_type       TEXT NOT NULL,
    title             TEXT,
    summary           TEXT,
    report_data       JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- pipeline_runs / pipeline_stages / pipeline_events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               TEXT PRIMARY KEY,
    agent_version_id TEXT REFERENCES agent_versions(id) ON DELETE SET NULL,
    pipeline_type    TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'queued',
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pipeline_stages (
    id              TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage_name      TEXT NOT NULL,
    stage_order     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    model_provider  TEXT,
    model_name      TEXT,
    input_count     INTEGER,
    output_count    INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    retry_count     INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pipeline_events (
    id                TEXT PRIMARY KEY,
    pipeline_stage_id TEXT NOT NULL REFERENCES pipeline_stages(id) ON DELETE CASCADE,
    event_type        TEXT NOT NULL,
    message           TEXT,
    metadata          JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =============================================================================
-- RUNTIME SCHEMA — temporary / disposable execution data
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS runtime;

CREATE TABLE IF NOT EXISTS runtime.sandboxes (
    id                   TEXT PRIMARY KEY,
    evaluation_run_id    TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    scenario_instance_id TEXT,
    runtime_type         TEXT NOT NULL,
    container_reference  TEXT,
    image_reference      TEXT,
    cpu_limit            NUMERIC,
    memory_limit_mb      INTEGER,
    disk_limit_mb        INTEGER,
    network_policy       JSONB,
    filesystem_policy    JSONB,
    status               TEXT NOT NULL DEFAULT 'creating',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    destroyed_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS runtime.scenario_instances (
    id                  TEXT PRIMARY KEY,
    evaluation_run_id   TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    scenario_id         TEXT REFERENCES scenarios(id) ON DELETE SET NULL,
    scenario_version_id TEXT,
    sandbox_id          TEXT REFERENCES runtime.sandboxes(id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'queued',
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.agent_actions (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    sequence_number      INTEGER NOT NULL,
    action_type          TEXT NOT NULL,
    description          TEXT,
    tool_call_id         TEXT,
    status               TEXT,
    metadata             JSONB,
    timestamp            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.tool_calls (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    sequence_number      INTEGER NOT NULL,
    tool_id              TEXT,
    original_tool_name   TEXT NOT NULL,
    input                JSONB,
    output               JSONB,
    status               TEXT NOT NULL,
    routing_decision     TEXT,
    target_environment   TEXT,
    latency_ms           INTEGER,
    error_code           TEXT,
    error_message        TEXT,
    started_at           TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS runtime.side_effect_events (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    tool_call_id         TEXT,
    effect_type          TEXT NOT NULL,
    target               TEXT,
    risk_level           TEXT NOT NULL,
    decision             TEXT NOT NULL,
    actual_execution     BOOLEAN NOT NULL DEFAULT false,
    sandbox_execution    BOOLEAN NOT NULL DEFAULT false,
    details              JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.network_events (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    domain               TEXT,
    url                  TEXT,
    method               TEXT,
    action               TEXT NOT NULL,
    status_code          INTEGER,
    blocked_reason       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.security_events (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    event_type           TEXT NOT NULL,
    severity             TEXT NOT NULL,
    target               TEXT,
    action               TEXT,
    evidence             JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.state_snapshots (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    snapshot_type        TEXT NOT NULL,
    state_reference      TEXT,
    state_hash           TEXT,
    metadata             JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.state_changes (
    id                   TEXT PRIMARY KEY,
    scenario_instance_id TEXT NOT NULL REFERENCES runtime.scenario_instances(id) ON DELETE CASCADE,
    resource_type        TEXT NOT NULL,
    resource_id          TEXT,
    field_name           TEXT,
    before_value         JSONB,
    after_value          JSONB,
    source_tool_call_id  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_id       ON agent_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_tools_agent_version_id        ON tools(agent_version_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_agent_version_id ON dependencies(agent_version_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_scenario_set_id     ON scenarios(scenario_set_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_results_run_id     ON evaluation_results(evaluation_run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_stages_run_id        ON pipeline_stages(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_stage_id      ON pipeline_events(pipeline_stage_id);

CREATE INDEX IF NOT EXISTS idx_rt_tool_calls_instance     ON runtime.tool_calls(scenario_instance_id);
CREATE INDEX IF NOT EXISTS idx_rt_agent_actions_instance  ON runtime.agent_actions(scenario_instance_id);
CREATE INDEX IF NOT EXISTS idx_rt_security_events_instance ON runtime.security_events(scenario_instance_id);
CREATE INDEX IF NOT EXISTS idx_rt_side_effects_instance   ON runtime.side_effect_events(scenario_instance_id);
CREATE INDEX IF NOT EXISTS idx_rt_state_changes_instance  ON runtime.state_changes(scenario_instance_id);
