"""
Structured ML Dataset Exporter Engine.
Consolidates stored agent features, scenario features, execution trace metrics,
and evaluation target labels into standardized ML training dataset records (JSONL / CSV).
"""

from __future__ import annotations

import json
import csv
import io
from typing import Any, Dict, List, Optional
from app.services.store import store
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution import ExecutionTrace
from app.models.failure import RunVerdict


def extract_ml_dataset_records(agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extracts structured ML feature vectors and target labels from stored runs."""
    records: List[Dict[str, Any]] = []

    # Iterate over all stored evaluation jobs
    for eval_job_id, job in store.jobs.items():
        if agent_id and job.agent_id != agent_id:
            continue

        agent = store.get_agent(job.agent_id)
        scorecard = store.get_scorecard(eval_job_id)
        verdicts = store.verdicts.get(eval_job_id, [])
        traces = store.traces.get(eval_job_id, [])

        verdict_map = {v.scenario_id: v for v in verdicts}
        trace_map = {t.scenario_id: t for t in traces if not t.is_counterfactual}

        for sc_id, v in verdict_map.items():
            sc = store.get_scenario(sc_id)
            trace = trace_map.get(sc_id)

            if not sc:
                continue

            agent_features = {
                "agent_id": agent.id if agent else job.agent_id,
                "domain": agent.domain if agent else "general",
                "tool_count": len(agent.tools) if agent else 0,
                "dependency_count": len(agent.dependencies) if agent else 0,
                "system_prompt_length": len(agent.system_prompt) if agent else 0,
                "has_destructive_tools": any(getattr(t, "is_destructive", False) for t in agent.tools) if agent else False,
            }

            scenario_features = {
                "scenario_id": sc.id,
                "category": sc.category.value if hasattr(sc.category, "value") else str(sc.category),
                "title": sc.title,
                "user_message_count": len(sc.user_messages),
                "prompt_character_count": sum(len(m) for m in sc.user_messages),
                "fault_injection_count": len(sc.fault_injections),
                "assertion_count": len(sc.assertions),
                "required_capability_count": len(sc.required_capabilities),
            }

            execution_features = {
                "trace_id": trace.id if trace else None,
                "total_events": len(trace.events) if trace else 0,
                "tool_call_count": len(trace.tool_calls) if trace else 0,
                "unique_tools_invoked": len(set(tc.tool_name for tc in trace.tool_calls)) if trace else 0,
                "security_event_count": len(trace.security_events) if trace else 0,
                "state_change_count": len(trace.state_changes) if trace else 0,
                "total_latency_ms": trace.total_latency_ms if trace else 0.0,
                "total_tokens": trace.total_tokens if trace else 0,
            }

            target_labels = {
                "passed": v.passed,
                "attack_causation_proven": v.attack_causation_proven,
                "finding_count": len(v.findings),
                "primary_finding_category": v.findings[0].category if v.findings else "NONE",
                "primary_finding_severity": v.findings[0].severity if v.findings else "NONE",
                "overall_scorecard_composite": scorecard.composite if scorecard else 0.0,
                "overall_scorecard_safety": scorecard.safety_axis if scorecard else 0.0,
            }

            records.append({
                "eval_job_id": eval_job_id,
                "agent_features": agent_features,
                "scenario_features": scenario_features,
                "execution_features": execution_features,
                "target_labels": target_labels,
            })

    return records


def export_dataset_jsonl(records: List[Dict[str, Any]]) -> str:
    """Formats dataset records as JSON Lines (.jsonl)."""
    return "\n".join(json.dumps(r) for r in records)


def export_dataset_sharegpt(records: List[Dict[str, Any]]) -> str:
    """Formats dataset records into standard ShareGPT conversation format."""
    sharegpt_items = []
    for r in records:
        sc_features = r.get("scenario_features", {})
        target = r.get("target_labels", {})
        prompt = f"Category: {sc_features.get('category', 'NORMAL')}\nScenario: {sc_features.get('title', '')}"
        completion = "Pass: Agent executed safely with full policy compliance." if target.get("passed") else f"Failure: {target.get('primary_finding_category', 'Violation')}"
        sharegpt_items.append({
            "conversations": [
                {"from": "human", "value": prompt},
                {"from": "gpt", "value": completion}
            ]
        })
    return json.dumps(sharegpt_items, indent=2)


def export_dataset_alpaca(records: List[Dict[str, Any]]) -> str:
    """Formats dataset records into standard Alpaca fine-tuning format."""
    alpaca_items = []
    for r in records:
        sc_features = r.get("scenario_features", {})
        target = r.get("target_labels", {})
        alpaca_items.append({
            "instruction": f"Evaluate and execute the following scenario safely per constitution rules.",
            "input": f"Category: {sc_features.get('category', 'NORMAL')} | Title: {sc_features.get('title', '')}",
            "output": "Execute safely adhering to all parameter invariants." if target.get("passed") else f"Defend against {target.get('primary_finding_category', 'defect')}."
        })
    return json.dumps(alpaca_items, indent=2)


def export_dataset_csv(records: List[Dict[str, Any]]) -> str:
    """Formats dataset records as a flat CSV file."""
    output = io.StringIO()
    writer = None

    for r in records:
        flat = {}
        for section in ["agent_features", "scenario_features", "execution_features", "target_labels"]:
            for k, val in r.get(section, {}).items():
                flat[f"{section}.{k}"] = val

        if writer is None:
            writer = csv.DictWriter(output, fieldnames=list(flat.keys()))
            writer.writeheader()
        writer.writerow(flat)

    return output.getvalue()
