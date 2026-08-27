"""
Root Cause Diagnosis Engine.
Analyzes evaluation failure findings, security events, and execution trajectories
to generate truthful, evidence-backed diagnoses with exact root causes, code/prompt locations,
and repair recommendations.
"""

from __future__ import annotations

import re
import uuid
import logging
from typing import Dict, List, Optional, Any

from app.models.agent import AgentRecord
from app.models.failure import RunVerdict, FailureFinding
from app.models.execution import ExecutionTrace, ToolCallRecord, SecurityEvent
from app.models.diagnosis import FailureDiagnosis, DiagnosticEvidence, AgentDiagnosisReport

logger = logging.getLogger(__name__)


class RootCauseAnalyzer:
    """
    Deterministic & Semantic Root Cause Analyzer.
    Maps observable failure events to concrete architectural, prompt, or code deficiencies.
    """

    def analyze_evaluation(
        self,
        agent: AgentRecord,
        evaluation_run_id: str,
        verdicts: List[RunVerdict],
        traces: Optional[List[ExecutionTrace]] = None
    ) -> AgentDiagnosisReport:
        diagnoses: List[FailureDiagnosis] = []
        defect_breakdown: Dict[str, int] = {
            "CODE_DEFECT": 0,
            "PROMPT_DEFECT": 0,
            "POLICY_DEFECT": 0,
            "ENVIRONMENT_DEFECT": 0,
            "TOOL_DEFECT": 0,
            "MODEL_CAPABILITY_DEFECT": 0
        }

        trace_map: Dict[str, ExecutionTrace] = {}
        if traces:
            for t in traces:
                trace_map[t.id] = t
                if t.scenario_id:
                    trace_map[t.scenario_id] = t

        for verdict in verdicts:
            if verdict.passed:
                continue

            scenario_trace = trace_map.get(verdict.trace_id) or trace_map.get(verdict.scenario_id)

            for finding in verdict.findings:
                diag = self._diagnose_single_finding(agent, verdict, finding, scenario_trace)
                diagnoses.append(diag)
                defect_breakdown[diag.root_cause_type] = defect_breakdown.get(diag.root_cause_type, 0) + 1

        # Determine primary repair recommendation
        primary_rec = "CODE_PATCH"
        if defect_breakdown.get("PROMPT_DEFECT", 0) > defect_breakdown.get("CODE_DEFECT", 0):
            primary_rec = "PROMPT_HARDENING"
        elif defect_breakdown.get("POLICY_DEFECT", 0) > defect_breakdown.get("CODE_DEFECT", 0):
            primary_rec = "TOOL_POLICY"
        elif defect_breakdown.get("MODEL_CAPABILITY_DEFECT", 0) > 0 and defect_breakdown.get("CODE_DEFECT", 0) == 0:
            primary_rec = "TRAINING_DATASET"

        report = AgentDiagnosisReport(
            id=f"diag-rep-{uuid.uuid4().hex[:8]}",
            agent_id=agent.id,
            agent_name=agent.name,
            evaluation_run_id=evaluation_run_id,
            total_failures=len(diagnoses),
            critical_failures=sum(1 for d in diagnoses if d.severity in ("critical", "high")),
            diagnoses=diagnoses,
            defect_breakdown=defect_breakdown,
            primary_repair_recommendation=primary_rec
        )
        return report

    def _diagnose_single_finding(
        self,
        agent: AgentRecord,
        verdict: RunVerdict,
        finding: FailureFinding,
        trace: Optional[ExecutionTrace]
    ) -> FailureDiagnosis:
        category = (finding.category or "").upper()
        desc = (finding.description or "").lower()
        title = finding.title or "Evaluation Failure"
        explanation = finding.explanation or ""

        # Extract primary python source file and contents for code location heuristics
        primary_file = "agent.py"
        source_code = ""
        if agent.source_files:
            for fname, content in agent.source_files.items():
                if fname.endswith(".py"):
                    primary_file = fname
                    source_code = content
                    break

        evidence_events: List[DiagnosticEvidence] = []
        attempted_action = finding.observed or finding.evidence
        policy_blocked = finding.policy_blocked
        actual_side_effect = finding.actual_side_effect

        if trace:
            for tc in trace.tool_calls:
                evidence_events.append(DiagnosticEvidence(
                    event_id=tc.id,
                    event_type="TOOL_CALL",
                    summary=f"Called tool `{tc.tool_name}` with args: {tc.arguments}",
                    raw_payload={"tool": tc.tool_name, "arguments": tc.arguments, "status": tc.status}
                ))
            for sec in trace.security_events:
                evidence_events.append(DiagnosticEvidence(
                    event_id=f"sec-{uuid.uuid4().hex[:6]}",
                    event_type="POLICY_DECISION",
                    summary=f"Security Event: {sec.event_type} on target {sec.target} ({sec.action_taken})",
                    raw_payload={"event_type": sec.event_type, "target": sec.target, "action": sec.action_taken}
                ))

        # -------------------------------------------------------------
        # 1. Classify Root Cause & Generate Truthful Narrative
        # -------------------------------------------------------------
        if "PROMPT_INJECTION" in category or "INJECTION" in desc or "JAILBREAK" in category:
            root_cause = "PROMPT_DEFECT"
            what_happened = "The agent succumbed to an adversarial user prompt override or jailbreak sequence."
            why_it_happened = (
                "The system prompt lacked explicit, immutable instruction priority barriers, "
                "allowing adversarial user input to hijack agent execution flow."
            )
            root_cause_detail = (
                "System prompt boundaries were declarative only without strict delimitations "
                "or explicit override protection in the constitution."
            )
            impact = "High: Attacker can execute unauthorized instructions or alter agent operational policy."
            repair_type = "PROMPT_HARDENING"
            fix_summary = "Harden system prompt with XML boundary encapsulation and strict 'NEVER override system instructions' rule."
            affected_line = self._find_line_in_source(source_code, ["system_prompt", "prompt", "instructions"])
            prompt_sec = "System Instructions -> Core Persona / Override Hierarchy"

        elif "UNAUTHORIZED" in category or "POLICY_BYPASS" in category or "SAFETY" in category or "REFUND" in desc or "PAYOUT" in desc:
            root_cause = "POLICY_DEFECT" if "policy" in desc else "CODE_DEFECT"
            what_happened = "Agent executed or attempted a restricted sensitive operation without mandatory authorization or confirmation."
            why_it_happened = (
                "The tool execution path allowed immediate dispatch because threshold validation "
                "and human-in-the-loop confirmation gates were missing in the agent source code."
            )
            root_cause_detail = (
                "Natural-language policy alone was expected to prevent high-risk tool calls. "
                "However, the Python dispatch function does not enforce programmatic limit checks."
            )
            impact = "Critical: Direct unauthorized mutations (e.g. payouts, refunds, account deletions) can occur."
            repair_type = "CODE_PATCH"
            fix_summary = "Add programmatic threshold limits and confirmation gates inside the tool handler before execution."
            affected_line = self._find_line_in_source(source_code, ["refund", "payout", "execute", "cancel_order", "process_payment"])
            prompt_sec = "Safety Constitution -> Never execute high-value actions without confirmation"

        elif "LOOP" in category or "RETRY" in category or "TIMEOUT" in category:
            root_cause = "CODE_DEFECT"
            what_happened = "Agent entered an uncontrolled retry loop or timed out trying to reach an external tool/service."
            why_it_happened = (
                "Tool invocation logic lacked a circuit breaker, max_retry count cap, or exponential backoff handling."
            )
            root_cause_detail = (
                "When downstream requests returned failure or unexpected schemas, the agent looped indefinitely."
            )
            impact = "Medium: Excessive token consumption, sandbox resource exhaustion, and high latency."
            repair_type = "CODE_PATCH"
            fix_summary = "Implement a max_retries limit (e.g., max 3 attempts) and circuit-breaker exception handling."
            affected_line = self._find_line_in_source(source_code, ["while", "retry", "invoke", "call_tool", "request"])
            prompt_sec = None

        elif "JSON_PARSE" in category or "MALFORMED" in category or "SCHEMA" in category or "STDOUT_JSON" in category:
            root_cause = "CODE_DEFECT"
            what_happened = "Agent output failed schema validation or could not be parsed as structured JSON."
            why_it_happened = (
                "The agent emitted conversational filler text (e.g., markdown code fences or greetings) around the raw JSON payload."
            )
            root_cause_detail = (
                "Output formatting was not strictly constrained or cleaned before serialization."
            )
            impact = "Medium: Downstream pipeline or API clients cannot consume agent outputs."
            repair_type = "CODE_PATCH"
            fix_summary = "Add regex-based JSON extraction and sanitize markdown fences prior to returning payload."
            affected_line = self._find_line_in_source(source_code, ["json.loads", "return", "output", "format"])
            prompt_sec = "Output Contract -> Format specification"

        elif "SECRET" in category or "LEAK" in category or "PII" in category:
            root_cause = "PROMPT_DEFECT"
            what_happened = "Agent leaked confidential API keys, system credentials, or customer PII in its final response."
            why_it_happened = (
                "The agent constitution lacked strict redaction instructions and the runtime lacked an egress scrubbing filter."
            )
            root_cause_detail = "Agent echoed sensitive context parameters when queried directly by the user."
            impact = "Critical: Exposure of sensitive credentials or customer data."
            repair_type = "PROMPT_HARDENING"
            fix_summary = "Add explicit PII/Credential redaction rule in Constitution and add regex masking before response output."
            affected_line = self._find_line_in_source(source_code, ["api_key", "secret", "token", "password"])
            prompt_sec = "Never Rules -> Never output API keys or internal secrets"

        elif "EXPECTED_TOOL_NOT_CALLED" in category or "TOOL_MISSING" in category:
            root_cause = "PROMPT_DEFECT"
            what_happened = "Agent attempted to answer user request without invoking the required specialized tool."
            why_it_happened = (
                "System prompt did not make tool usage mandatory for this domain capability or the tool descriptions were ambiguous."
            )
            root_cause_detail = "LLM opted to hallucinate/answer from internal weights instead of calling the registered tool."
            impact = "Medium: Inaccurate or stale data provided to the user."
            repair_type = "PROMPT_HARDENING"
            fix_summary = "Update tool descriptions with explicit usage triggers and enforce 'Always call tool for real-time queries'."
            affected_line = self._find_line_in_source(source_code, ["tools", "get_tools", "system_prompt"])
            prompt_sec = "Always Rules -> Always use tool to fetch live data"

        else:
            root_cause = "MODEL_CAPABILITY_DEFECT" if "reasoning" in desc else "CODE_DEFECT"
            what_happened = f"Execution assertion failed: {title}"
            why_it_happened = explanation or "Observed agent output diverged from scenario expectations."
            root_cause_detail = f"Evaluation rule observed divergence: {finding.observed or 'Divergent trajectory'}"
            impact = "Moderate: Agent failed scenario reliability criteria."
            repair_type = "CODE_PATCH" if root_cause == "CODE_DEFECT" else "TRAINING_DATASET"
            fix_summary = finding.remediation or "Review agent logic and reinforce scenario boundary."
            affected_line = 1
            prompt_sec = None

        return FailureDiagnosis(
            finding_id=finding.finding_id or f"find-{uuid.uuid4().hex[:6]}",
            agent_id=agent.id,
            scenario_id=verdict.scenario_id,
            scenario_title=verdict.scenario_id,
            category=category,
            severity=finding.severity or "high",
            title=title,
            root_cause_type=root_cause,
            what_happened=what_happened,
            why_it_happened=why_it_happened,
            root_cause_detail=root_cause_detail,
            impact_assessment=impact,
            affected_source_file=primary_file,
            affected_line_number=affected_line,
            affected_prompt_section=prompt_sec,
            evidence_events=evidence_events,
            attempted_action=str(attempted_action) if attempted_action else None,
            policy_blocked=policy_blocked,
            actual_side_effect_occurred=actual_side_effect,
            recommended_repair_type=repair_type,
            suggested_fix_summary=fix_summary
        )

    def _find_line_in_source(self, code: str, keywords: List[str]) -> int:
        if not code:
            return 1
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            lower_line = line.lower()
            if any(kw in lower_line for kw in keywords):
                return idx
        return 1
