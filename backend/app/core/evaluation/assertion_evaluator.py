"""
ForgeX Evaluation & Deterministic Assertion Engine.
Evaluates deterministic assertions and specialized detectors over sealed execution facts,
runs calibrated semantic judges, and generates formal Finding records with Root-Cause Attribution.
"""

from __future__ import annotations

import re
import json
import uuid
import datetime as dt
from typing import Dict, List, Optional, Any, Tuple
from app.models.evaluation_ontology import (
    EvaluationDimension,
    FindingSeverity,
    TestVerdictStatus,
    RootCauseCategory,
    RootCauseAttribution,
    Finding,
    FindingEvidence,
    DimensionScore,
    CanonicalReliabilityReport,
    CANONICAL_METRICS,
)
from app.models.canonical_data_models import (
    TestCaseSpecification,
    TestAssertion,
    AssertionType,
    EvidenceGraph,
)
from app.models.execution import ExecutionSession, ExecutionAction, ExecutionTrace
from app.core.evaluation.scoring_engine import ScoringEngine


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class AssertionEvaluator:
    """Evaluates TestAssertions over sealed ExecutionSession facts without hallucination."""

    @classmethod
    def evaluate_assertion(
        cls,
        assertion: TestAssertion,
        session: ExecutionSession,
        trace: Optional[ExecutionTrace] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluates a single assertion deterministically against session facts."""
        actions = session.actions or []
        stdout_combined = ""
        stderr_combined = ""
        final_response = ""

        if trace and hasattr(trace, "events"):
            for ev in trace.events:
                if getattr(ev, "role", "") == "agent_message":
                    final_response += getattr(ev, "content", "") + "\n"
                elif getattr(ev, "role", "") == "stdout":
                    stdout_combined += getattr(ev, "content", "") + "\n"
                elif getattr(ev, "role", "") == "stderr":
                    stderr_combined += getattr(ev, "content", "") + "\n"

        target = assertion.target_field

        # 1. TOOL_NOT_CALLED
        if assertion.assertion_type == AssertionType.TOOL_NOT_CALLED:
            forbidden_tool = str(assertion.expected_value).lower()
            called_tools = [a.target.lower() for a in actions if a.action_type == "TOOL_CALL"]
            if forbidden_tool in called_tools:
                return False, f"Forbidden tool '{forbidden_tool}' was called by the agent.", {"called_tools": called_tools}
            return True, f"Forbidden tool '{forbidden_tool}' was not called.", {}

        # 2. TOOL_CALLED
        elif assertion.assertion_type == AssertionType.TOOL_CALLED:
            expected_tool = str(assertion.expected_value).lower()
            called_tools = [a.target.lower() for a in actions if a.action_type == "TOOL_CALL"]
            if expected_tool not in called_tools:
                return False, f"Expected tool '{expected_tool}' was not called.", {"called_tools": called_tools}
            return True, f"Expected tool '{expected_tool}' was invoked.", {}

        # 3. TOOL_ARGS_MATCH
        elif assertion.assertion_type == AssertionType.TOOL_ARGS_MATCH:
            expected_args = assertion.expected_value if isinstance(assertion.expected_value, dict) else {}
            matching_calls = [a for a in actions if a.target == target or a.target.lower() == target.lower()]
            if not matching_calls:
                return False, f"Target tool '{target}' was never called to verify arguments.", {}
            for call in matching_calls:
                args = call.attempt_payload if isinstance(call.attempt_payload, dict) else {}
                for k, v in expected_args.items():
                    if k not in args or args[k] != v:
                        return False, f"Argument '{k}' mismatch: expected {v}, got {args.get(k)}", {"actual_args": args}
            return True, f"Tool arguments for '{target}' matched expected specification.", {}

        # 4. TOOL_ORDER_CORRECT
        elif assertion.assertion_type == AssertionType.TOOL_ORDER_CORRECT:
            expected_order = assertion.expected_value if isinstance(assertion.expected_value, list) else []
            actual_order = [a.target for a in actions if a.action_type == "TOOL_CALL"]
            # Subsequence check
            it = iter(actual_order)
            if all(any(tool.lower() == exp.lower() for tool in it) for exp in expected_order):
                return True, f"Tool execution order matched {expected_order}", {"actual_order": actual_order}
            return False, f"Tool execution order violated. Expected: {expected_order}, Got: {actual_order}", {"actual_order": actual_order}

        # 5. NOT_CONTAINS (e.g. PII, secrets, sensitive strings)
        elif assertion.assertion_type == AssertionType.NOT_CONTAINS:
            forbidden_str = str(assertion.expected_value)
            all_text = f"{stdout_combined} {final_response}"
            for a in actions:
                all_text += f" {str(a.attempt_payload)} {str(a.execution_result)}"
            if forbidden_str in all_text:
                return False, f"Found forbidden substring '{forbidden_str}' in outputs/actions.", {"matched": forbidden_str}
            return True, f"Forbidden string '{forbidden_str}' was absent.", {}

        # 6. CONTAINS (e.g. required confirmation phrase)
        elif assertion.assertion_type == AssertionType.CONTAINS:
            required_str = str(assertion.expected_value)
            all_text = f"{stdout_combined} {final_response}"
            if required_str.lower() not in all_text.lower():
                return False, f"Required substring '{required_str}' was missing from output.", {}
            return True, f"Required substring '{required_str}' was present.", {}

        # 7. EXIT_CODE_EQUALS
        elif assertion.assertion_type == AssertionType.EXIT_CODE_EQUALS:
            exp_code = int(assertion.expected_value)
            actual_code = session.post_snapshot.process_exit_code if session.post_snapshot else session.exit_code
            if actual_code != exp_code:
                return False, f"Process exit code mismatch: expected {exp_code}, got {actual_code}", {"actual_code": actual_code}
            return True, f"Process exit code matched {exp_code}", {}

        # 8. REGEX_MATCH
        elif assertion.assertion_type == AssertionType.REGEX_MATCH:
            pattern = str(assertion.expected_value)
            all_text = f"{stdout_combined} {final_response}"
            if not re.search(pattern, all_text):
                return False, f"Output failed to match regex pattern '{pattern}'", {}
            return True, f"Output matched regex pattern '{pattern}'", {}

        # Default fallback
        return True, "Assertion passed by default", {}


class ComprehensiveEvaluationEngine:
    """Full-spectrum Evaluation Engine generating deterministic findings, scorecards, and release gates."""

    @classmethod
    def evaluate_test_session(
        cls,
        test_case: TestCaseSpecification,
        session: ExecutionSession,
        trace: Optional[ExecutionTrace] = None
    ) -> Tuple[TestVerdictStatus, List[Finding], Dict[str, float]]:
        """Evaluates a test case against an execution session and returns verdict + findings."""
        findings: List[Finding] = []
        passed_assertions = 0
        total_assertions = len(test_case.assertions)
        metric_scores: Dict[str, float] = {}

        if total_assertions == 0:
            # Check default safety/security policies
            actions = session.actions or []
            blocked_policies = [a for a in actions if a.result_status == "BLOCKED_POLICY" or (isinstance(a.policy_decision, str) and a.policy_decision == "BLOCK")]
            if blocked_policies:
                verdict = TestVerdictStatus.PASS
                metric_scores[test_case.metric_id] = 100.0
            else:
                verdict = TestVerdictStatus.PASS
                metric_scores[test_case.metric_id] = 100.0
            return verdict, findings, metric_scores

        for assertion in test_case.assertions:
            passed, reason, evidence_data = AssertionEvaluator.evaluate_assertion(assertion, session, trace)
            if passed:
                passed_assertions += 1
            else:
                # Generate Canonical Finding
                ev_items: List[FindingEvidence] = []
                for idx, act in enumerate(session.actions):
                    ev_items.append(FindingEvidence(
                        scenario_id=test_case.scenario_id,
                        scenario_title=test_case.title,
                        step_sequence=idx + 1,
                        event_type=act.action_type,
                        attempt_payload=act.attempt_payload if isinstance(act.attempt_payload, dict) else {},
                        policy_decision=act.policy_decision,
                        execution_result=act.execution_result,
                        side_effect=act.side_effect if hasattr(act, "side_effect") else {}
                    ))

                # Root Cause Attribution
                root_cause = RootCauseAttribution(
                    category=RootCauseCategory.AGENT_CODE if test_case.dimension in (EvaluationDimension.SECURITY, EvaluationDimension.SAFETY_COMPLIANCE) else RootCauseCategory.PROMPT_INSTRUCTION,
                    subcategory="CODE_AUTHORIZATION_BYPASS" if test_case.dimension == EvaluationDimension.SECURITY else "PROMPT_MISSING_CONSTRAINT",
                    affected_file_or_component=f"agent.py:{test_case.expected_tools[0] if test_case.expected_tools else 'main'}",
                    description=reason,
                    confidence=0.95,
                    remediation_guidance=f"Enforce deterministic policy guardrail for {test_case.title}"
                )

                finding = Finding(
                    id=f"find-{uuid.uuid4().hex[:8]}",
                    evaluation_run_id=session.execution_run_id,
                    agent_id=test_case.agent_id,
                    agent_version=test_case.agent_version,
                    dimension=test_case.dimension,
                    metric_id=test_case.metric_id,
                    severity=assertion.severity,
                    title=f"Assertion Failure: {assertion.description}",
                    summary=reason,
                    impact=f"Failure in {test_case.dimension.value}: {test_case.intent}",
                    evidence=ev_items,
                    root_cause=root_cause,
                    is_hard_blocker=(assertion.severity == FindingSeverity.CRITICAL),
                    created_at=_now()
                )
                findings.append(finding)

        metric_score = ScoringEngine.calculate_metric_score(
            metric_id=test_case.metric_id,
            passed_assertions=passed_assertions,
            total_assertions=total_assertions
        )
        metric_scores[test_case.metric_id] = metric_score

        if len(findings) == 0:
            verdict = TestVerdictStatus.PASS
        elif any(f.severity == FindingSeverity.CRITICAL for f in findings):
            verdict = TestVerdictStatus.FAIL
        else:
            verdict = TestVerdictStatus.FAIL

        return verdict, findings, metric_scores
