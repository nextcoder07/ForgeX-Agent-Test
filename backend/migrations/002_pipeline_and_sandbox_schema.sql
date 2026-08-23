-- =============================================================================
-- Migration 002: Pipeline Runs and Sandbox Specifications (Exact Match to store.py)
-- Run this in your Supabase SQL Editor.
-- =============================================================================

-- 1. pipeline_runs
CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    id            TEXT PRIMARY KEY,
    agent_id      TEXT,
    agent_name    TEXT,
    pipeline_type TEXT NOT NULL DEFAULT 'agent_intake',
    status        TEXT NOT NULL DEFAULT 'running',
    stages        JSONB NOT NULL DEFAULT '[]'::jsonb,
    events        JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- If pipeline_runs already exists without completed_at or pipeline_type, add them:
ALTER TABLE public.pipeline_runs ADD COLUMN IF NOT EXISTS pipeline_type TEXT DEFAULT 'agent_intake';
ALTER TABLE public.pipeline_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE public.pipeline_runs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_agent_id ON public.pipeline_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON public.pipeline_runs(status);

-- 2. sandbox_specifications
CREATE TABLE IF NOT EXISTS public.sandbox_specifications (
    id            TEXT PRIMARY KEY,
    agent_id      TEXT REFERENCES public.agents(id) ON DELETE CASCADE,
    runtime       JSONB NOT NULL DEFAULT '{}'::jsonb,
    dependencies  JSONB NOT NULL DEFAULT '[]'::jsonb,
    filesystem    JSONB NOT NULL DEFAULT '{}'::jsonb,
    network       JSONB NOT NULL DEFAULT '{}'::jsonb,
    tools         JSONB NOT NULL DEFAULT '[]'::jsonb,
    credentials   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- If sandbox_specifications already exists without columns, add them:
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS runtime JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS dependencies JSONB DEFAULT '[]'::jsonb;
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS filesystem JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS network JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS tools JSONB DEFAULT '[]'::jsonb;
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS credentials JSONB DEFAULT '[]'::jsonb;
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'READY';
ALTER TABLE public.sandbox_specifications ADD COLUMN IF NOT EXISTS blockers JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_sandbox_specifications_agent_id ON public.sandbox_specifications(agent_id);
