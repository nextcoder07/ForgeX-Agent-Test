-- Migration for Dependency Setup Flow and Sandbox Execution Console
-- Safe to run against your Supabase PostgreSQL project.

-- 1. Dependency Flow Tables
CREATE TABLE IF NOT EXISTS public.agent_dependencies (
    id                TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    dependency_name   TEXT NOT NULL,
    dependency_type   TEXT NOT NULL,
    required          BOOLEAN NOT NULL DEFAULT true,
    detected_from     TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.platform_resources (
    id                TEXT PRIMARY KEY,
    capability        TEXT NOT NULL,
    provider          TEXT NOT NULL,
    mode              TEXT NOT NULL DEFAULT 'sandbox',
    status            TEXT NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.dependency_bindings (
    id                TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    dependency_name   TEXT NOT NULL,
    resolution_type   TEXT NOT NULL,
    status            TEXT NOT NULL,
    user_value        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Sandbox Execution Jobs Table
CREATE TABLE IF NOT EXISTS public.execution_jobs (
    id                  TEXT PRIMARY KEY,
    agent_id            TEXT NOT NULL,
    agent_name          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    total_scenarios     INTEGER NOT NULL DEFAULT 0,
    completed_scenarios INTEGER NOT NULL DEFAULT 0,
    scenario_ids        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ
);
