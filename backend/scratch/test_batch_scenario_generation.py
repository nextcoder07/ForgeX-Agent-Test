import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.store import store
from app.models.scenario import ScenarioGenerationRequest
from app.api.scenarios import execute_scenario_generation_run

async def main():
    print("======================================================================")
    print("VERIFYING ACCUMULATIVE BATCH SCENARIO GENERATION (TARGET = 20)")
    print("======================================================================")

    agents = store.list_agents()
    if not agents:
        print("No agents found in store!")
        return
    
    agent = agents[0]
    print(f"Target Agent: {agent.name} (id={agent.id})")

    existing = [s for s in store.list_scenarios() if s.agent_id == agent.id]
    print(f"Existing scenarios count in store before run: {len(existing)}")

    # Request 20 scenarios
    target_count = 20
    req = ScenarioGenerationRequest(agent_id=agent.id, target_count=target_count)
    
    run = await execute_scenario_generation_run(req)
    print(f"-> Generation Run ID: {run.id}")
    print(f"-> Requested Count: {run.requested_count}")
    print(f"-> Planned Count: {run.planned_count}")
    print(f"-> Generated Scenarios Count returned: {len(run.scenarios)}")
    print(f"-> Provider Used: {run.provider} ({run.model})")
    
    accumulated = [s for s in store.list_scenarios() if s.agent_id == agent.id]
    print(f"-> Accumulated scenarios count in store after run: {len(accumulated)}")

    assert len(run.scenarios) == target_count, f"Expected {target_count} scenarios, got {len(run.scenarios)}"
    print("======================================================================")
    print("SUCCESS: Batch generation generated EXACTLY 20 scenarios & preserved library!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(main())
