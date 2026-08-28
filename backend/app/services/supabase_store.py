"""
SupabaseStore — persists agents, scenarios, evaluation jobs, scorecards,
failure clusters, and pipeline runs to Supabase (PostgreSQL).

Drop-in replacement for the in-memory Store.
Falls back transparently to the in-memory Store when Supabase is not configured.
"""
from __future__ import annotations

import logging
import datetime as dt
from typing import Any, Dict, List, Optional

from app.db.supabase_client import get_client
from app.models.agent import AgentRecord, ToolDefinition, ToolRisk, DependencyDefinition, AgentConstitution
from app.models.scenario import Scenario
from app.models.evaluation import EvaluationJob, ReliabilityScorecard
from app.models.failure import RunVerdict, FailureCluster
from app.models.execution import ExecutionTrace
from app.models.pipeline import PipelineRun, PipelineStage

logger = logging.getLogger(__name__)


def _now() -> str:
    return dt.datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Helper: safe Supabase execute — returns data list or []
# ---------------------------------------------------------------------------
def _exec(query) -> List[Dict]:
    try:
        res = query.execute()
        return res.data or []
    except Exception as exc:
        logger.error(f"Supabase query error: {exc}")
        return []


# ---------------------------------------------------------------------------
# Agent helpers
# ---------------------------------------------------------------------------
def _agent_to_row(agent: AgentRecord) -> Dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "status": "active",
        "updated_at": _now(),
    }


def _row_to_agent(row: Dict) -> AgentRecord:
    """Convert a Supabase agents row back into an AgentRecord Pydantic model."""
    spec: Dict = row.get("agent_spec") or {}
    tools_data = spec.get("tools", [])
    tools = [
        ToolDefinition(
            name=t.get("name", ""),
            description=t.get("description", ""),
            canonical_capability=t.get("canonical_capability", ""),
            risk=ToolRisk(t.get("risk", "low")),
        )
        for t in tools_data
    ]
    constitution_data = spec.get("constitution", {})
    constitution = AgentConstitution(
        goals=constitution_data.get("goals", []),
        never_rules=constitution_data.get("never_rules", []),
        always_rules=constitution_data.get("always_rules", []),
        escalation_rules=constitution_data.get("escalation_rules", []),
        data_policies=constitution_data.get("data_policies", []),
    )
    return AgentRecord(
        id=row["id"],
        name=row["name"],
        description=row.get("description", ""),
        domain=spec.get("domain", ""),
        system_prompt=spec.get("system_prompt", ""),
        tools=tools,
        dependencies=[],
        constitution=constitution,
        version_label=spec.get("version_label", "v1.0"),
        created_at=str(row.get("created_at", _now())),
    )


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------
def _scenario_to_row(scenario: Scenario) -> Dict[str, Any]:
    return {
        "id": scenario.id,
        "category": scenario.category.value if hasattr(scenario.category, "value") else str(scenario.category),
        "title": scenario.title,
        "purpose": scenario.purpose,
        "status": "active",
        "updated_at": _now(),
        # Store full scenario as JSONB via a joined scenario_set / scenario_version row
        # For simplicity, we embed content in metadata JSONB
        "current_version_id": None,
    }


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------
def _pipeline_run_to_row(run: PipelineRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "pipeline_type": run.pipeline_type if hasattr(run, "pipeline_type") else "intake",
        "status": run.status,
        "started_at": run.started_at if hasattr(run, "started_at") else None,
        "completed_at": run.completed_at if hasattr(run, "completed_at") else None,
    }


# ---------------------------------------------------------------------------
# Main SupabaseStore class
# ---------------------------------------------------------------------------
class SupabaseStore:
    """
    Persists platform data to Supabase.
    Every method gracefully no-ops if Supabase is not configured,
    so the application can still run against the in-memory fallback.
    """

    def __init__(self):
        self._sb = get_client()
        if self._sb:
            logger.info("SupabaseStore: connected to Supabase.")
        else:
            logger.warning("SupabaseStore: Supabase not configured — all writes skipped.")

    # -------------------------------------------------------------------------
    # AGENTS
    # -------------------------------------------------------------------------
    def upsert_agent(self, agent: AgentRecord) -> None:
        if not self._sb:
            return
        row = _agent_to_row(agent)
        _exec(self._sb.table("agents").upsert(row))
        logger.debug(f"upsert_agent: {agent.id}")

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(self._sb.table("agents").select("*").eq("id", agent_id).limit(1))
        if rows:
            return rows[0]
        return None

    def list_agents(self) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(self._sb.table("agents").select("*").order("created_at", desc=True))

    def delete_agent(self, agent_id: str) -> None:
        if not self._sb:
            return
        _exec(self._sb.table("agents").delete().eq("id", agent_id))

    # -------------------------------------------------------------------------
    # AGENT VERSIONS
    # -------------------------------------------------------------------------
    def upsert_agent_version(self, agent_id: str, version: str, spec: Dict, source_type: str = "upload") -> Optional[Dict]:
        if not self._sb:
            return None
        row = {
            "agent_id": agent_id,
            "version": version,
            "source_type": source_type,
            "artifact_hash": "",
            "agent_spec": spec,
            "analysis_status": "complete",
        }
        rows = _exec(self._sb.table("agent_versions").upsert(row, on_conflict="agent_id,version").select("*"))
        return rows[0] if rows else None

    def get_agent_versions(self, agent_id: str) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(self._sb.table("agent_versions").select("*").eq("agent_id", agent_id))

    # -------------------------------------------------------------------------
    # TOOLS
    # -------------------------------------------------------------------------
    def upsert_tools(self, agent_version_id: str, tools: List[Dict]) -> None:
        if not self._sb or not tools:
            return
        rows = [{"agent_version_id": agent_version_id, **t} for t in tools]
        _exec(self._sb.table("tools").upsert(rows))

    def list_tools(self, agent_version_id: str) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(self._sb.table("tools").select("*").eq("agent_version_id", agent_version_id))

    # -------------------------------------------------------------------------
    # SCENARIOS
    # -------------------------------------------------------------------------
    def upsert_scenario_set(self, agent_id: str, name: str, description: str = "") -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(
            self._sb.table("scenario_sets")
            .upsert({"agent_id": agent_id, "name": name, "description": description})
            .select("*")
        )
        return rows[0] if rows else None

    def upsert_scenario(self, scenario_set_id: str, scenario: Dict) -> Optional[Dict]:
        """scenario dict must contain: id, category, title, purpose"""
        if not self._sb:
            return None
        row = {
            "id": scenario.get("id"),
            "scenario_set_id": scenario_set_id,
            "category": scenario.get("category", "normal"),
            "title": scenario.get("title", "Untitled"),
            "purpose": scenario.get("purpose", ""),
            "status": "active",
        }
        rows = _exec(self._sb.table("scenarios").upsert(row).select("*"))
        return rows[0] if rows else None

    def list_scenarios(self, scenario_set_id: str) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(self._sb.table("scenarios").select("*").eq("scenario_set_id", scenario_set_id))

    def upsert_scenario_version(self, scenario_id: str, version: int, content: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        row = {"scenario_id": scenario_id, "version": version, **content}
        rows = _exec(
            self._sb.table("scenario_versions")
            .upsert(row, on_conflict="scenario_id,version")
            .select("*")
        )
        return rows[0] if rows else None

    # -------------------------------------------------------------------------
    # EVALUATION RUNS & RESULTS
    # -------------------------------------------------------------------------
    def create_evaluation_run(self, agent_version_id: str, mode: str, name: str = "") -> Optional[Dict]:
        if not self._sb:
            return None
        row = {
            "agent_version_id": agent_version_id,
            "mode": mode,
            "name": name,
            "status": "queued",
        }
        rows = _exec(self._sb.table("evaluation_runs").insert(row).select("*"))
        return rows[0] if rows else None

    def update_evaluation_run(self, run_id: str, updates: Dict) -> None:
        if not self._sb:
            return
        _exec(self._sb.table("evaluation_runs").update(updates).eq("id", run_id))

    def get_evaluation_run(self, run_id: str) -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(self._sb.table("evaluation_runs").select("*").eq("id", run_id).limit(1))
        return rows[0] if rows else None

    def list_evaluation_runs(self, agent_version_id: Optional[str] = None) -> List[Dict]:
        if not self._sb:
            return []
        q = self._sb.table("evaluation_runs").select("*").order("created_at", desc=True)
        if agent_version_id:
            q = q.eq("agent_version_id", agent_version_id)
        return _exec(q)

    def insert_evaluation_result(self, result: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        try:
            rows = _exec(self._sb.table("evaluation_verdicts").insert(result).select("*"))
        except Exception:
            rows = _exec(self._sb.table("evaluation_results").insert(result).select("*"))
        return rows[0] if rows else None

    def list_evaluation_results(self, run_id: str) -> List[Dict]:
        if not self._sb:
            return []
        try:
            return _exec(self._sb.table("evaluation_verdicts").select("*").eq("evaluation_run_id", run_id))
        except Exception:
            return _exec(self._sb.table("evaluation_results").select("*").eq("evaluation_run_id", run_id))

    # -------------------------------------------------------------------------
    # REPORTS
    # -------------------------------------------------------------------------
    def create_report(self, evaluation_run_id: str, report_type: str, title: str, summary: str, data: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        row = {
            "evaluation_run_id": evaluation_run_id,
            "report_type": report_type,
            "title": title,
            "summary": summary,
            "report_data": data,
        }
        try:
            rows = _exec(self._sb.table("scorecards").insert(row).select("*"))
            if rows:
                return rows[0]
        except Exception:
            pass
        try:
            rows = _exec(self._sb.table("reports").insert(row).select("*"))
            return rows[0] if rows else None
        except Exception:
            return None

    def list_reports(self, evaluation_run_id: str) -> List[Dict]:
        if not self._sb:
            return []
        try:
            res = _exec(self._sb.table("scorecards").select("*").eq("evaluation_run_id", evaluation_run_id))
            if res:
                return res
        except Exception:
            pass
        return _exec(self._sb.table("reports").select("*").eq("evaluation_run_id", evaluation_run_id))

    # -------------------------------------------------------------------------
    # PIPELINE RUNS / STAGES / EVENTS
    # -------------------------------------------------------------------------
    def create_pipeline_run(self, pipeline_type: str, agent_version_id: Optional[str] = None) -> Optional[Dict]:
        if not self._sb:
            return None
        row = {"pipeline_type": pipeline_type, "status": "queued"}
        if agent_version_id:
            row["agent_version_id"] = agent_version_id
        rows = _exec(self._sb.table("pipeline_runs").insert(row).select("*"))
        return rows[0] if rows else None

    def update_pipeline_run(self, run_id: str, updates: Dict) -> None:
        if not self._sb:
            return
        _exec(self._sb.table("pipeline_runs").update(updates).eq("id", run_id))

    def create_pipeline_stage(self, pipeline_run_id: str, stage_name: str, stage_order: int) -> Optional[Dict]:
        if not self._sb:
            return None
        model_name = __import__("os").getenv("GEMINI_MODEL", "gemini-3.6-flash")
        row = {
            "pipeline_run_id": pipeline_run_id,
            "stage_name": stage_name,
            "stage_order": stage_order,
            "status": "queued",
            "model_provider": "gemini",
            "model_name": model_name,
        }
        rows = _exec(self._sb.table("pipeline_stages").insert(row).select("*"))
        return rows[0] if rows else None

    def update_pipeline_stage(self, stage_id: str, updates: Dict) -> None:
        if not self._sb:
            return
        _exec(self._sb.table("pipeline_stages").update(updates).eq("id", stage_id))

    def emit_pipeline_event(self, stage_id: str, event_type: str, message: str, metadata: Optional[Dict] = None) -> None:
        if not self._sb:
            return
        row = {
            "pipeline_stage_id": stage_id,
            "event_type": event_type,
            "message": message,
            "metadata": metadata or {},
        }
        _exec(self._sb.table("pipeline_events").insert(row))

    def list_pipeline_events(self, stage_id: str) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(
            self._sb.table("pipeline_events")
            .select("*")
            .eq("pipeline_stage_id", stage_id)
            .order("created_at")
        )

    # -------------------------------------------------------------------------
    # RUNTIME — tool calls, security events, side effects
    # -------------------------------------------------------------------------
    def insert_tool_call(self, call: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(self._sb.table("runtime.tool_calls").insert(call).select("*"))
        return rows[0] if rows else None

    def insert_security_event(self, event: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(self._sb.table("runtime.security_events").insert(event).select("*"))
        return rows[0] if rows else None

    def insert_side_effect(self, effect: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(self._sb.table("runtime.side_effect_events").insert(effect).select("*"))
        return rows[0] if rows else None

    def insert_state_change(self, change: Dict) -> Optional[Dict]:
        if not self._sb:
            return None
        rows = _exec(self._sb.table("runtime.state_changes").insert(change).select("*"))
        return rows[0] if rows else None

    def list_tool_calls(self, scenario_instance_id: str) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(
            self._sb.table("runtime.tool_calls")
            .select("*")
            .eq("scenario_instance_id", scenario_instance_id)
            .order("sequence_number")
        )

    def list_security_events(self, scenario_instance_id: str) -> List[Dict]:
        if not self._sb:
            return []
        return _exec(
            self._sb.table("runtime.security_events")
            .select("*")
            .eq("scenario_instance_id", scenario_instance_id)
        )


# Singleton — import this everywhere
supabase_store = SupabaseStore()
