-- Compatibility migration for the current FastAPI control-plane store.
-- Safe to run against an existing Supabase project.

ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS agent_spec JSONB;

ALTER TABLE scenarios
    ADD COLUMN IF NOT EXISTS agent_id TEXT;

CREATE TABLE IF NOT EXISTS agent_artifacts (
    id                TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    artifact_type     TEXT NOT NULL DEFAULT 'package',
    storage_provider  TEXT NOT NULL DEFAULT 'supabase_database',
    storage_path      TEXT NOT NULL,
    original_filename TEXT,
    content_hash      TEXT NOT NULL,
    size_bytes        BIGINT NOT NULL DEFAULT 0,
    mime_type         TEXT,
    file_count        INTEGER NOT NULL DEFAULT 0,
    input_type        TEXT NOT NULL DEFAULT 'package',
    upload_metadata   JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_files (
    id                TEXT PRIMARY KEY,
    agent_artifact_id TEXT NOT NULL,
    path              TEXT NOT NULL,
    file_type         TEXT,
    language          TEXT,
    size_bytes        BIGINT NOT NULL DEFAULT 0,
    content_hash      TEXT NOT NULL,
    storage_path      TEXT NOT NULL,
    is_entrypoint     BOOLEAN NOT NULL DEFAULT false,
    is_config         BOOLEAN NOT NULL DEFAULT false,
    is_prompt         BOOLEAN NOT NULL DEFAULT false,
    is_tool_definition BOOLEAN NOT NULL DEFAULT false,
    content           TEXT,
    metadata          JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE agent_artifacts
    ADD COLUMN IF NOT EXISTS input_type TEXT NOT NULL DEFAULT 'package';

CREATE TABLE IF NOT EXISTS scorecards (
    -- The application currently uses string IDs such as eval-abc123.
    -- Keep this as TEXT until evaluation_runs is migrated to the same ID strategy.
    evaluation_id        TEXT PRIMARY KEY,
    agent_id             TEXT,
    agent_name           TEXT,
    agent_version        TEXT,
    correctness          NUMERIC,
    safety               NUMERIC,
    robustness           NUMERIC,
    tool_discipline      NUMERIC,
    goal_adherence       NUMERIC,
    composite            NUMERIC,
    safety_axis          NUMERIC,
    capability_axis      NUMERIC,
    total_scenarios      INTEGER,
    passed               INTEGER,
    failed               INTEGER,
    critical_failures    INTEGER,
    judge_agreement_rate NUMERIC,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
