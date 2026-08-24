"""Run the real six-stage pipeline for an already registered agent.

Usage:
    python run_full_6stage_pipeline.py --agent-id agent-1234 --mode simulation
"""

from __future__ import annotations

import argparse
import asyncio

from app.api.pipeline import _new_run, run_full_6stage_pipeline
from app.services.store import store


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ForgeX six-stage reliability pipeline")
    parser.add_argument("--agent-id", required=True, help="Agent already registered through intake")
    parser.add_argument("--mode", default="simulation", choices=("simulation", "compatible", "faithful"))
    parser.add_argument("--scenario-count", type=int, default=20)
    args = parser.parse_args()

    agent = store.get_agent(args.agent_id)
    if not agent:
        raise SystemExit(f"Registered agent not found: {args.agent_id}")

    run = _new_run(agent.id, agent.name)
    store.save_pipeline_run(run)
    completed = asyncio.run(run_full_6stage_pipeline(
        run.id, agent.id, {}, args.mode, args.scenario_count
    ))
    print(f"Pipeline {completed.id}: {completed.status}")
    for stage in completed.stages:
        print(f"{stage.stage_name}: {stage.status} ({stage.duration_ms}ms)")


if __name__ == "__main__":
    main()
