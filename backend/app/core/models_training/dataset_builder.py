"""
Training Dataset Builder.
Extracts factual execution trajectories, failure verdicts, and human/repair corrections
to generate high-quality SFT, DPO/Preference, and Failure-Recovery datasets.
"""

from __future__ import annotations

import json
import uuid
import logging
from typing import Dict, Any, List, Optional

from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution import ExecutionTrace, ExecutionSession, ExecutionStep
from app.models.failure import RunVerdict, FailureFinding
from app.models.training import (
    TrainingDataset, SFTExample, SFTMessage, PreferencePair, FailureRecoveryExample
)

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """Builds structured datasets for supervised fine-tuning and preference optimization."""

    def build_dataset_from_runs(
        self,
        agent: AgentRecord,
        dataset_name: str,
        scenarios: List[Scenario],
        verdicts: List[RunVerdict],
        traces: Optional[List[ExecutionTrace]] = None,
        dataset_type: str = "HYBRID"
    ) -> TrainingDataset:
        sft_examples: List[SFTExample] = []
        preference_pairs: List[PreferencePair] = []
        recovery_examples: List[FailureRecoveryExample] = []
        source_scenarios: List[str] = [s.id for s in scenarios]
        source_execs: List[str] = [v.trace_id for v in verdicts if v.trace_id]

        scenario_map = {s.id: s for s in scenarios}
        trace_map = {t.id: t for t in (traces or [])}

        for verdict in verdicts:
            sc = scenario_map.get(verdict.scenario_id)
            if not sc:
                continue

            user_input = ""
            if sc.input_artifacts:
                user_input = sc.input_artifacts.get("user_input") or sc.input_artifacts.get("prompt") or str(sc.input_artifacts)
            elif sc.invocation:
                user_input = sc.invocation.get("payload", {}).get("message") or str(sc.invocation)

            if not user_input:
                user_input = sc.purpose or sc.title

            trace = trace_map.get(verdict.trace_id)
            trace_events = trace.events if trace else []
            tool_calls = trace.tool_calls if trace else []

            # -------------------------------------------------------------
            # 1. SFT Example (From Successful or Corrected Runs)
            # -------------------------------------------------------------
            if verdict.passed:
                assistant_response = "Action completed successfully according to policy."
                if trace_events:
                    agent_msgs = [e.content for e in trace_events if e.role == "agent_message"]
                    if agent_msgs:
                        assistant_response = agent_msgs[-1]

                sft_msgs = [
                    SFTMessage(role="system", content=agent.system_prompt or "You are a reliable AI assistant."),
                    SFTMessage(role="user", content=user_input),
                    SFTMessage(
                        role="assistant",
                        content=assistant_response,
                        tool_calls=[{"name": tc.tool_name, "arguments": tc.arguments} for tc in tool_calls] if tool_calls else None
                    )
                ]
                sft_examples.append(SFTExample(
                    agent_id=agent.id,
                    scenario_id=sc.id,
                    scenario_title=sc.title,
                    category=sc.category.value if hasattr(sc.category, "value") else str(sc.category),
                    messages=sft_msgs
                ))

            # -------------------------------------------------------------
            # 2. Preference Pairs (DPO) (From Failed Runs with Evidence)
            # -------------------------------------------------------------
            else:
                for finding in verdict.findings:
                    rejected_action = finding.observed or (f"Invoked tool without authorization" if finding.actual_side_effect else "Failed assertion")
                    chosen_action = finding.expected or (finding.remediation or "Refuse unsafe action or ask for confirmation.")

                    preference_pairs.append(PreferencePair(
                        agent_id=agent.id,
                        scenario_id=sc.id,
                        prompt=f"System: {agent.system_prompt[:200]}...\nUser: {user_input}",
                        chosen=chosen_action,
                        rejected=str(rejected_action),
                        reason=finding.explanation or finding.description,
                        category=sc.category.value if hasattr(sc.category, "value") else str(sc.category),
                        margin=1.5 if finding.severity in ("critical", "high") else 1.0
                    ))

                    # ---------------------------------------------------------
                    # 3. Failure Recovery Example
                    # ---------------------------------------------------------
                    recovery_examples.append(FailureRecoveryExample(
                        agent_id=agent.id,
                        scenario_id=sc.id,
                        error_state=finding.title or finding.category,
                        attempted_action=str(rejected_action),
                        corrected_action=str(chosen_action),
                        recovery_strategy="programmatic_guard_and_confirmation" if "POLICY" in finding.category else "retry_backoff"
                    ))

        total_examples = len(sft_examples) + len(preference_pairs) + len(recovery_examples)

        dataset = TrainingDataset(
            agent_id=agent.id,
            agent_name=agent.name,
            name=dataset_name,
            description=f"Generated from {len(verdicts)} evaluation runs across {len(scenarios)} scenarios for agent {agent.name}.",
            dataset_type=dataset_type,
            format="JSONL",
            example_count=total_examples,
            sft_examples=sft_examples,
            preference_pairs=preference_pairs,
            recovery_examples=recovery_examples,
            source_scenarios=source_scenarios,
            source_execution_runs=source_execs
        )
        return dataset

    def export_as_jsonl(self, dataset: TrainingDataset, export_type: str = "ALL") -> str:
        """Exports dataset records as JSONL lines for HuggingFace / Axolotl / Llama-Factory."""
        lines: List[str] = []

        if export_type in ("ALL", "SFT"):
            for ex in dataset.sft_examples:
                lines.append(json.dumps({
                    "type": "sft",
                    "messages": [m.model_dump() for m in ex.messages],
                    "metadata": {"agent_id": ex.agent_id, "scenario_id": ex.scenario_id, "category": ex.category}
                }))

        if export_type in ("ALL", "DPO", "PREFERENCE"):
            for pair in dataset.preference_pairs:
                lines.append(json.dumps({
                    "type": "dpo",
                    "prompt": pair.prompt,
                    "chosen": pair.chosen,
                    "rejected": pair.rejected,
                    "reason": pair.reason,
                    "margin": pair.margin,
                    "category": pair.category
                }))

        if export_type in ("ALL", "RECOVERY"):
            for rec in dataset.recovery_examples:
                lines.append(json.dumps({
                    "type": "failure_recovery",
                    "error_state": rec.error_state,
                    "attempted_action": rec.attempted_action,
                    "corrected_action": rec.corrected_action,
                    "recovery_strategy": rec.recovery_strategy
                }))

        return "\n".join(lines)
