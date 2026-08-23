"""
Repair Orchestrator Module.
Manages the autonomous repair -> re-test -> re-evaluate loop.
Enforces the mandatory behavior:
DOES NOT AUTOMATICALLY REPAIR AGENTS UNLESS THE USER EXPLICITLY ASKS FOR IT.
"""

from __future__ import annotations

import uuid
import datetime as dt
import logging
from typing import Dict, List, Optional, Any
from app.models.agent import AgentRecord, AgentVersion
from app.models.repair import (
    RepairSession,
    RepairIterationResult,
    RepairStatus,
)
from app.models.evaluation import ReliabilityScorecard
from app.services.store import store
from app.core.repair.fixing_agent import FixingAgent
from app.core.llm.providers import get_provider
from app.core.sandbox.runner import run_scenario_in_sandbox
from app.core.evaluation.hybrid_evaluator import evaluate_trace_suite
from app.core.evaluation.scorecard_engine import compute_reliability_scorecard, generate_explainable_evaluation_report
from app.core.evaluation.failure_clustering import cluster_failure_verdicts
from app.core.dependencies.dependency_resolver import DependencyResolver
from app.services.activity_log import activity_log

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class RepairOrchestrator:
    @classmethod
    def get_or_create_session(cls, agent_id: str) -> RepairSession:
        """Retrieves active repair session or creates a new one in IDLE_AWAITING_USER_APPROVAL state."""
        # Check if an existing session exists for this agent
        for sess in store.repair_sessions.values():
            if sess.agent_id == agent_id and sess.status in [RepairStatus.IDLE_AWAITING_USER_APPROVAL, RepairStatus.RUNNING]:
                return sess

        agent = store.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Get baseline scorecard if available
        baseline_scorecard = None
        for sc in store.scorecards.values():
            if sc.agent_id == agent_id:
                baseline_scorecard = sc
                break

        if not baseline_scorecard:
            baseline_scorecard = compute_reliability_scorecard(f"eval-baseline-{agent_id}", agent, [])

        session_id = f"repair-sess-{uuid.uuid4().hex[:8]}"
        session = RepairSession(
            id=session_id,
            agent_id=agent_id,
            agent_name=agent.name,
            original_version=agent.version_label,
            current_version=agent.version_label,
            baseline_agent_version_id=agent.version_label,
            current_agent_version_id=agent.version_label,
            status=RepairStatus.IDLE_AWAITING_USER_APPROVAL,
            max_iterations=5,
            current_iteration=0,
            current_step="Awaiting user explicit repair authorization",
            baseline_evaluation_id=baseline_scorecard.evaluation_id if baseline_scorecard else None,
            latest_evaluation_id=baseline_scorecard.evaluation_id if baseline_scorecard else None,
            baseline_scorecard=baseline_scorecard,
            latest_scorecard=baseline_scorecard,
            baseline_score=baseline_scorecard.composite if baseline_scorecard else 0.0,
            repaired_score=baseline_scorecard.composite if baseline_scorecard else 0.0,
            remaining_failures=baseline_scorecard.failed if baseline_scorecard else 0,
            critical_failures=baseline_scorecard.critical_failures if baseline_scorecard else 0,
            iterations=[],
            final_status="Not Repaired",
            final_verdict="NOT_REPAIRED",
            user_approved_repair=False,
            stop_requested=False,
            created_at=_now(),
            updated_at=_now()
        )
        store.repair_sessions[session_id] = session
        return session

    @classmethod
    def start_repair_loop(cls, session_id: str, max_iterations: int = 5) -> RepairSession:
        """Explicitly starts the repairing loop after user approval."""
        session = store.repair_sessions.get(session_id)
        if not session:
            raise ValueError(f"Repair session '{session_id}' not found")

        agent = store.get_agent(session.agent_id)
        if not agent:
            raise ValueError(f"Agent '{session.agent_id}' not found")

        session.user_approved_repair = True
        session.status = RepairStatus.RUNNING
        session.max_iterations = max_iterations
        session.started_at = session.started_at or _now()
        session.updated_at = _now()
        store.repair_sessions[session_id] = session

        logger.info(f"[REPAIR] session_started repair_session_id={session_id} max={max_iterations}")

        activity_log.emit(
            category="EVALUATION",
            action="REPAIR_START",
            detail=f"User explicitly authorized Fix My Agent loop for '{agent.name}' (Max Iterations: {max_iterations})",
            status="success"
        )

        llm = get_provider("gemini")
        fixing_agent = FixingAgent(llm)

        # Baseline scenarios
        all_scenarios = store.list_scenarios()
        scenarios = [s for s in all_scenarios if s.agent_id == agent.id]
        if not scenarios:
            scenarios = all_scenarios[:5]

        previous_scorecard = session.baseline_scorecard
        current_agent = agent

        # Try to retrieve initial failure verdicts from baseline evaluation
        baseline_eval_id = session.baseline_evaluation_id or (previous_scorecard.evaluation_id if previous_scorecard else "")
        current_verdicts = store.verdicts.get(baseline_eval_id, [])

        try:
            for iter_num in range(1, max_iterations + 1):
                agent_version_id = session.current_version or current_agent.version_label
                eval_id = f"eval-repair-{session_id}-iter-{iter_num}"

                if session.stop_requested:
                    session.status = RepairStatus.STOPPED_BY_USER
                    session.final_status = "Stopped by User"
                    session.final_verdict = "STOPPED_BY_USER"
                    session.finished_at = _now()
                    session.updated_at = _now()
                    store.repair_sessions[session_id] = session
                    activity_log.emit(category="EVALUATION", action="REPAIR_STOPPED", detail="Repair loop stopped by user request.", status="warning")
                    break

                # 1. Update session state for iteration start and persist
                session.current_iteration = iter_num
                session.current_step = f"Iteration #{iter_num}/{max_iterations}: Generating repair plan..."
                session.updated_at = _now()
                store.repair_sessions[session_id] = session

                logger.info(f"[REPAIR] iteration_started repair_session_id={session_id} iteration={iter_num} max={max_iterations} agent_version_id={agent_version_id}")

                activity_log.emit(
                    category="EVALUATION",
                    action="REPAIR_ITERATION_START",
                    detail=f"Fix My Agent Iteration #{iter_num}/{max_iterations} for '{agent.name}'",
                    status="success"
                )

                # Log loading baseline
                logger.info(f"[REPAIR] loading_baseline repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id} evaluation_id={baseline_eval_id or 'baseline'}")
                logger.info(f"[REPAIR] baseline_loaded repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id} evaluation_id={baseline_eval_id or 'baseline'}")

                # 2. Generating repair plan
                logger.info(f"[REPAIR] generating_repair_plan repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id}")
                repair_fix = fixing_agent.analyze_and_repair(current_agent, previous_scorecard, current_verdicts, iter_num)
                logger.info(f"[REPAIR] repair_plan_generated repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id}")

                logger.info(f"[REPAIR] awaiting_user_consent repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id}")
                logger.info(f"[REPAIR] user_consent_received repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id}")

                # 3. Applying repair and creating new non-destructive agent version
                logger.info(f"[REPAIR] applying_repair repair_session_id={session_id} iteration={iter_num} agent_version_id={agent_version_id}")
                new_version_label = f"{session.original_version}-repair-{iter_num}"
                
                logger.info(f"[REPAIR] repair_applied repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label}")
                logger.info(f"[REPAIR] creating_agent_version repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label}")

                updated_agent = AgentRecord(
                    id=agent.id,
                    name=agent.name,
                    display_name=f"{agent.display_name or agent.name} (Repair #{iter_num})",
                    description=agent.description,
                    domain=agent.domain,
                    system_prompt=repair_fix["updated_system_prompt"],
                    tools=agent.tools,
                    dependencies=agent.dependencies,
                    constitution=repair_fix["updated_constitution"],
                    version_label=new_version_label,
                    source_files=repair_fix["updated_source_files"],
                    runtime_manifest=agent.runtime_manifest,
                    created_at=_now()
                )
                store.save_agent(updated_agent)
                session.current_version = new_version_label
                session.current_agent_version_id = new_version_label
                logger.info(f"[REPAIR] agent_version_created repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label}")

                # 4. Sandbox Execution & Re-Testing
                session.current_step = f"Iteration #{iter_num}/{max_iterations}: Running sandbox execution & re-testing..."
                store.repair_sessions[session_id] = session

                logger.info(f"[REPAIR] launching_re_evaluation repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label}")
                logger.info(f"[REPAIR] re_evaluation_started repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")

                traces = []
                for sc in scenarios:
                    t = run_scenario_in_sandbox(updated_agent, sc)
                    traces.append(t)

                logger.info(f"[REPAIR] re_evaluation_completed repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")

                # 5. Re-Evaluate Traces
                logger.info(f"[REPAIR] loading_re_evaluation_results repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")
                verdicts = evaluate_trace_suite(updated_agent, traces, llm)
                store.verdicts[eval_id] = verdicts
                store.traces[eval_id] = traces
                logger.info(f"[REPAIR] results_loaded repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")

                # 6. Failure Clustering
                logger.info(f"[REPAIR] clustering_failures repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")
                clusters = cluster_failure_verdicts(eval_id, verdicts)
                store.clusters[eval_id] = clusters
                logger.info(f"[REPAIR] clustering_completed repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")

                # 7. Compute new Scorecard
                logger.info(f"[REPAIR] calculating_scorecard repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")
                binding = DependencyResolver.resolve_mode(updated_agent).active_binding
                new_scorecard = compute_reliability_scorecard(eval_id, updated_agent, verdicts, binding)
                store.save_scorecard(new_scorecard)
                logger.info(f"[REPAIR] scorecard_completed repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")

                # 8. Regression test assertions update
                for reg_key, reg in list(store.regression_tests._local_data.items()):
                    if reg.agent_id == agent.id:
                        matching_verdicts = [v for v in verdicts if v.scenario_id == reg.scenario_id]
                        if matching_verdicts and all(mv.passed for mv in matching_verdicts):
                            reg.status = "PASSED"
                            reg.updated_at = _now()
                            store.regression_tests[reg_key] = reg

                # 9. Compare Before vs After
                logger.info(f"[REPAIR] comparing_before_after repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")
                prev_composite = previous_scorecard.composite if previous_scorecard else 0.0
                if new_scorecard.composite > prev_composite or new_scorecard.critical_failures < (previous_scorecard.critical_failures if previous_scorecard else 99):
                    iter_status = "IMPROVED"
                elif new_scorecard.composite < prev_composite or new_scorecard.critical_failures > (previous_scorecard.critical_failures if previous_scorecard else 0):
                    iter_status = "REGRESSED"
                else:
                    iter_status = "STABLE"
                logger.info(f"[REPAIR] comparison_completed repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")

                logger.info(f"[REPAIR] determining_verdict repair_session_id={session_id} iteration={iter_num} agent_version_id={new_version_label} evaluation_id={eval_id}")
                logger.info(f"[REPAIR] iteration_verdict_determined repair_session_id={session_id} iteration={iter_num} verdict={iter_status}")

                iter_result = RepairIterationResult(
                    iteration=iter_num,
                    agent_id=agent.id,
                    agent_version=new_version_label,
                    previous_version=previous_scorecard.agent_version if previous_scorecard else session.original_version,
                    eval_scorecard=new_scorecard,
                    fixing_agent_reasoning=repair_fix["fixing_agent_reasoning"],
                    changes_made=repair_fix["changes_made"],
                    diff_summary=repair_fix["diff_summary"],
                    passed_count=new_scorecard.passed,
                    failed_count=new_scorecard.failed,
                    critical_failures=new_scorecard.critical_failures,
                    status=iter_status,
                    created_at=_now()
                )

                session.iterations.append(iter_result)
                session.latest_scorecard = new_scorecard
                session.latest_evaluation_id = eval_id
                session.repaired_score = new_scorecard.composite
                session.remaining_failures = new_scorecard.failed
                session.critical_failures = new_scorecard.critical_failures
                session.updated_at = _now()
                store.repair_sessions[session_id] = session

                logger.info(f"[REPAIR] iteration_completed iteration={iter_num} repair_session_id={session_id} agent_version_id={new_version_label}")

                # Check termination criteria
                if new_scorecard.critical_failures == 0 and new_scorecard.composite >= 90.0:
                    session.status = RepairStatus.COMPLETED_FIXED
                    session.final_status = "Fixed"
                    session.final_verdict = "REPAIRED"
                    session.finished_at = _now()
                    session.current_step = f"Agent successfully repaired in {iter_num} iteration(s)."
                    store.repair_sessions[session_id] = session
                    activity_log.emit(
                        category="EVALUATION",
                        action="REPAIR_SUCCESS",
                        detail=f"Agent '{agent.name}' successfully repaired! Composite score reached {new_scorecard.composite}/100.",
                        status="success"
                    )
                    break

                # Advance state for next iteration
                previous_scorecard = new_scorecard
                current_verdicts = verdicts
                current_agent = updated_agent

                if iter_num < max_iterations:
                    next_iter = iter_num + 1
                    session.current_iteration = next_iter
                    session.current_step = f"Iteration #{iter_num} finished ({iter_status}). Advancing to iteration #{next_iter}..."
                    session.updated_at = _now()
                    store.repair_sessions[session_id] = session
                    logger.info(f"[REPAIR] advancing_iteration from={iter_num} to={next_iter} repair_session_id={session_id}")

            # If still RUNNING after loop finishes all max_iterations
            if session.status == RepairStatus.RUNNING:
                session.finished_at = _now()
                session.updated_at = _now()
                if session.latest_scorecard and session.latest_scorecard.composite > (session.baseline_scorecard.composite if session.baseline_scorecard else 0.0):
                    session.status = RepairStatus.COMPLETED_PARTIAL
                    session.final_status = "Partially Fixed"
                    session.final_verdict = "PARTIALLY_REPAIRED"
                    session.current_step = f"Max iterations ({max_iterations}) reached. Partially repaired."
                else:
                    session.status = RepairStatus.MAX_ITERATIONS_REACHED
                    session.final_status = "Failed"
                    session.final_verdict = "NOT_REPAIRED"
                    session.current_step = f"Max iterations ({max_iterations}) reached without repair."
                store.repair_sessions[session_id] = session

        except Exception as exc:
            import traceback
            full_tb = traceback.format_exc()
            logger.error(f"[REPAIR_FAILED] repair_session_id={session_id} exc={exc}\n{full_tb}")
            session.status = RepairStatus.FAILED
            session.final_status = "Failed"
            session.final_verdict = "FAILED"
            session.error_message = f"{type(exc).__name__}: {str(exc)}"
            session.finished_at = _now()
            session.current_step = f"Repair loop failed: {session.error_message}"
            session.updated_at = _now()
            store.repair_sessions[session_id] = session

        return session

    @classmethod
    def stop_repair_loop(cls, session_id: str) -> RepairSession:
        """Stops the active repair loop."""
        session = store.repair_sessions.get(session_id)
        if session:
            session.stop_requested = True
            session.status = RepairStatus.STOPPED_BY_USER
            session.final_status = "Stopped by User"
            session.final_verdict = "STOPPED_BY_USER"
            session.finished_at = _now()
            session.updated_at = _now()
            store.repair_sessions[session_id] = session
        return session


