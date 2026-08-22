-- Preserve agent ownership for scenarios created before the top-level
-- scenarios.agent_id column was populated by the application.
UPDATE public.scenarios
SET agent_id = NULLIF(scenario_spec->>'agent_id', '')
WHERE agent_id IS NULL
  AND scenario_spec IS NOT NULL
  AND NULLIF(scenario_spec->>'agent_id', '') IS NOT NULL
  AND EXISTS (
      SELECT 1
      FROM public.agents
      WHERE public.agents.id = NULLIF(public.scenarios.scenario_spec->>'agent_id', '')
  );

CREATE INDEX IF NOT EXISTS idx_scenarios_agent_id ON public.scenarios(agent_id);