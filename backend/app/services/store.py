"""
Permanent and Ephemeral Store Service.
Adapts transparently to Supabase database backend if configured,
otherwise falls back to in-memory storage.
"""
from __future__ import annotations

import os
import json
import uuid
import hashlib
import logging
import datetime as dt
from typing import Dict, List, Optional, Any

from app.db.supabase_client import get_client
from app.models.agent import AgentRecord, ToolDefinition, ToolRisk, DependencyDefinition, AgentConstitution
from app.models.scenario import Scenario, ScenarioCategory
from app.models.evaluation import EvaluationJob, ReliabilityScorecard, RegressionTest
from app.models.failure import RunVerdict, FailureCluster, FailureFinding
from app.models.execution import (
    ExecutionTrace, ExecutionJob, ExecutionSession, ExecutionStep, ExecutionMetrics, 
    BenchmarkRecord, ExecutionPreflight, ExecutionRun, ExecutionAction, ExecutionArtifact,
    PreExecutionSnapshot, PostExecutionSnapshot, EvidencePackage
)
from app.models.repair import RepairSession
from app.models.pipeline import PipelineRun, PipelineStage, AIGenerationRun
from app.models.intake import AgentTestSpecification, SandboxSpecification, AgentDependency, PlatformResource, DependencyBinding
from app.models.agent_behavior import AgentBehaviorProfile
from app.models.model_connection import ModelConnection
from app.models.training import TrainingDataset, SFTExample, PreferencePair, FailureRecoveryExample
from app.models.diagnosis import FailureDiagnosis, AgentDiagnosisReport
from app.models.model_training_job import TrainingJob, ModelVersionRecord
from app.models.evaluation_ontology import Finding, CanonicalReliabilityReport
from app.models.canonical_data_models import (
    TestCaseSpecification, EvidenceGraph, PatchArtifact, AgentVersionRecord
)


logger = logging.getLogger(__name__)

def _now() -> str:
    return dt.datetime.utcnow().isoformat()

# ---------------------------------------------------------------------------
# Synced Dictionary Base Class
# ---------------------------------------------------------------------------
class SyncedDict:
    def __init__(self, table_name: str, serialize_fn: Any, deserialize_fn: Any, key_col: str = "id"):
        self.table_name = table_name
        self.serialize_fn = serialize_fn
        self.deserialize_fn = deserialize_fn
        self.key_col = key_col
        self._local_data: Dict[str, Any] = {}
        self._sb = get_client()
        self._load_local_snapshot()

    def _snapshot_file(self) -> str:
        return os.path.join(os.path.dirname(__file__), f"__snapshot_{self.table_name}.json")

    def _save_local_snapshot(self):
        if self._sb:
            return  # When Supabase is active, never write local JSON snapshot files
        try:
            snapshot = {}
            for k, val in self._local_data.items():
                snapshot[k] = self.serialize_fn(k, val)
            target_file = self._snapshot_file()
            temp_file = f"{target_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f)
            os.replace(temp_file, target_file)
        except Exception as e:
            logger.debug(f"Could not save disk snapshot for {self.table_name}: {e}")

    def _load_local_snapshot(self):
        if self._sb:
            return  # When Supabase is active, do not load local JSON files
        sf = self._snapshot_file()
        if os.path.exists(sf):
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    snapshot = json.load(f)
                    for k, row in snapshot.items():
                        self._local_data[k] = self.deserialize_fn(row)
            except Exception as e:
                logger.debug(f"Could not load disk snapshot for {self.table_name}: {e}")

    def __getitem__(self, key: str) -> Any:
        # Fast path: instant in-memory read (0.01ms)
        if key in self._local_data:
            return self._local_data[key]

        # Slow fallback: fetch from Supabase if not in memory
        if self._sb:
            try:
                res = self._sb.table(self.table_name).select("*").eq(self.key_col, key).execute()
                if not res.data and self.key_col != "id":
                    res = self._sb.table(self.table_name).select("*").eq("id", key).execute()
                if res.data and len(res.data) > 0:
                    val = self.deserialize_fn(res.data[0])
                    self._local_data[key] = val
                    return val
            except Exception as e:
                logger.debug(f"Supabase fetch error for {self.table_name}[{key}]: {e}")

        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self._local_data[key] = value
        self._save_local_snapshot()
        if self._sb:
            try:
                row = self.serialize_fn(key, value)
                conflict_col = "id" if "id" in row else self.key_col
                self._sb.table(self.table_name).upsert(row, on_conflict=conflict_col).execute()
            except Exception as e:
                err_msg = str(e)
                if "409" in err_msg or "Conflict" in err_msg or "duplicate key" in err_msg:
                    try:
                        row = self.serialize_fn(key, value)
                        conflict_col = "id" if "id" in row else self.key_col
                        self._sb.table(self.table_name).update(row).eq(conflict_col, key).execute()
                        return
                    except Exception:
                        pass
                if self.table_name == "sandbox_specifications" and ("PGRST204" in err_msg or "schema cache" in err_msg):
                    try:
                        row = self.serialize_fn(key, value)
                        for field in ["status", "blockers", "runtime_version"]:
                            row.pop(field, None)
                        self._sb.table(self.table_name).upsert(row, on_conflict="id").execute()
                        return
                    except Exception:
                        pass
                logger.debug(f"Supabase sync note for {self.table_name}: {e}")

    def __delitem__(self, key: str) -> None:
        if key in self._local_data:
            del self._local_data[key]
        self._save_local_snapshot()
        if self._sb:
            try:
                self._sb.table(self.table_name).delete().eq(self.key_col, key).execute()
            except Exception as e:
                logger.debug(f"Supabase delete note for {self.table_name}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        if key in self._local_data:
            return True
        if self._sb:
            try:
                res = self._sb.table(self.table_name).select(self.key_col).eq(self.key_col, key).execute()
                if res.data and len(res.data) > 0:
                    return True
            except Exception:
                pass
        return False

    def _ensure_loaded(self):
        if not getattr(self, "_is_fully_loaded", False) and self._sb:
            try:
                res = self._sb.table(self.table_name).select("*").execute()
                if res.data:
                    for r in res.data:
                        try:
                            k = r.get(self.key_col) or r.get("id")
                            if k and k not in self._local_data:
                                self._local_data[k] = self.deserialize_fn(r)
                        except Exception:
                            pass
                self._is_fully_loaded = True
            except Exception as e:
                logger.debug(f"Supabase warm error for {self.table_name}: {e}")

    def values(self) -> List[Any]:
        self._ensure_loaded()
        return list(self._local_data.values())

    def keys(self) -> List[str]:
        self._ensure_loaded()
        return list(self._local_data.keys())

    def items(self) -> List[tuple[str, Any]]:
        self._ensure_loaded()
        return list(self._local_data.items())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._local_data)
        return len(self._local_data)


# ---------------------------------------------------------------------------
# Serializer / Deserializer Functions
# ---------------------------------------------------------------------------
def _serialize_agent(key: str, agent: AgentRecord) -> Dict[str, Any]:
    ws_id = getattr(agent, "workspace_id", None)
    owner_id = getattr(agent, "owner_id", None) or getattr(agent, "user_id", None)
    if owner_id == "default_user":
        owner_id = None

    from app.db.supabase_client import get_client
    sb = get_client()
    if sb:
        try:
            # Validate owner_id exists in user_profiles
            if owner_id:
                res_u = sb.table("user_profiles").select("id").eq("id", owner_id).execute()
                if not res_u.data or len(res_u.data) == 0:
                    owner_id = None
            if not owner_id:
                res_u_first = sb.table("user_profiles").select("id").limit(1).execute()
                if res_u_first.data and len(res_u_first.data) > 0:
                    owner_id = res_u_first.data[0]["id"]

            # Validate ws_id exists in workspaces
            if ws_id:
                res_w = sb.table("workspaces").select("id").eq("id", ws_id).execute()
                if not res_w.data or len(res_w.data) == 0:
                    ws_id = None
            if not ws_id and owner_id:
                res_m = sb.table("workspace_members").select("workspace_id").eq("user_id", owner_id).limit(1).execute()
                if res_m.data and len(res_m.data) > 0:
                    ws_id = res_m.data[0].get("workspace_id")
            if not ws_id:
                res_w_first = sb.table("workspaces").select("id, owner_id").limit(1).execute()
                if res_w_first.data and len(res_w_first.data) > 0:
                    ws_id = res_w_first.data[0]["id"]
                    if not owner_id:
                        owner_id = res_w_first.data[0].get("owner_id")
        except Exception as e:
            logger.debug(f"FK validation note in serialize_agent: {e}")
    spec = {
        "domain": agent.domain,
        "display_name": agent.display_name,
        "source_name": agent.source_name,
        "artifact_id": agent.artifact_id,
        "artifact_hash": agent.artifact_hash,
        "source_files": agent.source_files,
        "runtime_manifest": agent.runtime_manifest,
        "execution_status": agent.execution_status,
        "configuration_status": getattr(agent, "configuration_status", "READY"),
        "blocking_reason": getattr(agent, "blocking_reason", None),
        "input_type": agent.input_type,
        "endpoint": agent.endpoint,
        "system_prompt": agent.system_prompt,
        "tools": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in agent.tools],
        "dependencies": [d.model_dump() if hasattr(d, "model_dump") else d.dict() for d in agent.dependencies],
        "constitution": agent.constitution.model_dump() if hasattr(agent.constitution, "model_dump") else agent.constitution.dict(),
        "capabilities": getattr(agent, "capabilities", []),
        "inputs": getattr(agent, "inputs", []),
        "outputs": getattr(agent, "outputs", []),
        "workflow": getattr(agent, "workflow", []),
        "data_surfaces": getattr(agent, "data_surfaces", {}),
        "decision_surfaces": getattr(agent, "decision_surfaces", []),
        "security_surfaces": getattr(agent, "security_surfaces", []),
        "side_effects": getattr(agent, "side_effects", []),
        "evidence_packet": getattr(agent, "evidence_packet", {}),
        "audit_report": getattr(agent, "audit_report", {}),
        "confidence_score": getattr(agent, "confidence_score", 98.0),
        "version_label": agent.version_label,
        "user_id": owner_id or "default_user",
        "owner_id": owner_id,
        "workspace_id": ws_id,
        "created_at": agent.created_at,
        "current_version_id": agent.current_version_id
    }
    return {
        "id": agent.id,
        "workspace_id": ws_id,
        "owner_id": owner_id,
        "name": agent.name,
        "description": agent.description,
        "status": "active",
        "current_version_id": agent.current_version_id or agent.id,
        "agent_spec": spec
    }

def _deserialize_agent(row: Dict[str, Any]) -> AgentRecord:
    spec = row.get("agent_spec") or {}
    tools = [ToolDefinition(**t) for t in spec.get("tools", [])]
    deps = [DependencyDefinition(**d) for d in spec.get("dependencies", [])]
    const_data = spec.get("constitution") or {}
    constitution = AgentConstitution(**const_data) if isinstance(const_data, dict) else AgentConstitution()
    return AgentRecord(
        id=row.get("id", ""),
        name=row.get("name", ""),
        description=row.get("description", ""),
        display_name=spec.get("display_name"),
        source_name=spec.get("source_name"),
        domain=spec.get("domain", "general"),
        system_prompt=spec.get("system_prompt", ""),
        tools=tools,
        dependencies=deps,
        constitution=constitution,
        capabilities=spec.get("capabilities", []),
        inputs=spec.get("inputs", []),
        outputs=spec.get("outputs", []),
        workflow=spec.get("workflow", []),
        data_surfaces=spec.get("data_surfaces", {}),
        decision_surfaces=spec.get("decision_surfaces", []),
        security_surfaces=spec.get("security_surfaces", []),
        side_effects=spec.get("side_effects", []),
        evidence_packet=spec.get("evidence_packet", {}),
        audit_report=spec.get("audit_report", {}),
        confidence_score=spec.get("confidence_score", 98.0),
        configuration_status=spec.get("configuration_status", "READY"),
        blocking_reason=spec.get("blocking_reason"),
        endpoint=spec.get("endpoint"),
        version_label=spec.get("version_label", "v1.0"),
        current_version_id=row.get("current_version_id") or spec.get("current_version_id"),
        artifact_id=spec.get("artifact_id"),
        artifact_hash=spec.get("artifact_hash"),
        source_files=spec.get("source_files", {}),
        runtime_manifest=spec.get("runtime_manifest", {}),
        execution_status=spec.get("execution_status", "READY"),
        input_type=spec.get("input_type", "package"),
        user_id=row.get("owner_id") or spec.get("user_id"),
        owner_id=row.get("owner_id"),
        workspace_id=row.get("workspace_id"),
        created_at=str(row.get("created_at") or spec.get("created_at") or _now())
    )


def _serialize_scenario(key: str, sc: Scenario) -> Dict[str, Any]:
    scenario_data = sc.model_dump() if hasattr(sc, "model_dump") else sc.dict()
    av_id = getattr(sc, "agent_version_id", None)
    from app.db.supabase_client import get_client
    sb = get_client()
    if sb and av_id:
        try:
            res_v = sb.table("agent_versions").select("id").eq("id", av_id).execute()
            if not res_v.data or len(res_v.data) == 0:
                av_id = None
        except Exception:
            av_id = None
    elif av_id and not (str(av_id).startswith("ver-") or "-v" in str(av_id)):
        av_id = None

    return {
        "id": sc.id,
        "agent_id": sc.agent_id,
        "category": sc.category.value if hasattr(sc.category, "value") else str(sc.category),
        "title": sc.title,
        "purpose": sc.purpose,
        "status": sc.status,
        "interface_type": sc.interface_type,
        "invocation": sc.invocation,
        "input_artifacts": sc.input_artifacts,
        "assertions": [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in sc.assertions],
        "provenance": sc.provenance,
        "fingerprint": sc.fingerprint,
        "target_failure_surface": sc.target_failure_surface,
        "target_invariant": sc.target_invariant,
        "validation_status": sc.validation_status,
        "critic_status": sc.critic_status,
        "agent_version_id": av_id,
        "scenario_spec": scenario_data
    }

def _deserialize_scenario(row: Dict[str, Any]) -> Scenario:
    spec = row.get("scenario_spec") or {}
    if not isinstance(spec, dict):
        spec = {}
    spec = dict(spec)

    # Ensure required scenario fields exist
    if not spec.get("id"):
        spec["id"] = row.get("id") or f"sc-{uuid.uuid4().hex[:8]}"
    if not spec.get("agent_id"):
        spec["agent_id"] = row.get("agent_id") or ""
    if not spec.get("title"):
        spec["title"] = row.get("title") or "Test Scenario"
    if not spec.get("purpose"):
        spec["purpose"] = row.get("purpose") or "Evaluate agent behavior."
    if not spec.get("category"):
        spec["category"] = row.get("category") or "normal"
    if not spec.get("status"):
        spec["status"] = row.get("status") or "READY"

    projected_fields = (
        "agent_id", "interface_type", "invocation", "input_artifacts", "assertions",
        "provenance", "fingerprint", "target_failure_surface", "target_invariant",
        "validation_status", "critic_status", "status", "agent_version_id",
    )
    projected = {field: row[field] for field in projected_fields if row.get(field) is not None}
    for field, value in projected.items():
        if field not in spec or spec[field] in (None, {}, [], ""):
            spec[field] = value
    return Scenario(**spec)

def _serialize_job(key: str, job: EvaluationJob) -> Dict[str, Any]:
    spec = {
        "agent_id": job.agent_id,
        "agent_version_id": job.agent_version_id,
        "agent_name": job.agent_name,
        "agent_version": job.agent_version,
        "execution_run_id": job.execution_run_id,
        "sandbox_specification_id": job.sandbox_specification_id,
        "behavior_profile_id": job.behavior_profile_id,
        "scenario_set_id": job.scenario_set_id,
        "current_step": job.current_step,
        "error_message": job.error_message,
        "total_scenarios": job.total_scenarios,
        "completed_scenarios": job.completed_scenarios,
        "total_verdicts": job.total_verdicts,
        "execution_mode": job.execution_mode,
        "original_model": job.original_model,
        "executed_model": job.executed_model,
        "model_substitution": job.model_substitution,
        "confidence": job.confidence,
        "fidelity": job.fidelity,
        "evaluator_version": job.evaluator_version,
        "rule_set_version": job.rule_set_version,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at
    }
    return {
        "id": job.id,
        "agent_id": job.agent_id,
        "agent_version_id": job.agent_version_id if (job.agent_version_id and "-v" in str(job.agent_version_id)) else None,
        "run_type": "evaluation",
        "execution_mode": job.execution_mode,
        "status": job.status,
        "total_scenarios": job.total_scenarios,
        "passed_scenarios": job.completed_scenarios,
        "total_verdicts": job.total_verdicts,
        "original_model": job.original_model,
        "executed_model": job.executed_model,
        "model_substitution": job.model_substitution,
        "confidence": job.confidence,
        "fidelity": job.fidelity,
        "evaluator_version": job.evaluator_version,
        "rule_set_version": job.rule_set_version,
        "started_at": job.started_at or job.created_at,
        "completed_at": job.finished_at,
        "job_spec": spec
    }

def _deserialize_job(row: Dict[str, Any]) -> EvaluationJob:
    spec = row.get("job_spec") or {}
    status = row.get("status") or spec.get("status") or "completed"
    current_step = spec.get("current_step") or row.get("current_step") or "Evaluation job processed."
    error_msg = spec.get("error_message") or row.get("error_message")

    total_sc = int(spec.get("total_scenarios") or row.get("total_scenarios") or 0)
    passed_sc = int(spec.get("completed_scenarios") or row.get("passed_scenarios") or row.get("completed_scenarios") or 0)
    total_vd = int(spec.get("total_verdicts") or row.get("total_verdicts") or passed_sc)

    return EvaluationJob(
        id=row["id"],
        agent_id=spec.get("agent_id") or row.get("agent_id", ""),
        agent_version_id=spec.get("agent_version_id") or row.get("agent_version_id"),
        agent_name=spec.get("agent_name") or row.get("name") or row.get("agent_name", ""),
        agent_version=spec.get("agent_version") or row.get("agent_version", "v1.0"),
        execution_run_id=spec.get("execution_run_id") or row.get("execution_run_id"),
        sandbox_specification_id=spec.get("sandbox_specification_id"),
        behavior_profile_id=spec.get("behavior_profile_id"),
        scenario_set_id=spec.get("scenario_set_id"),
        status=status,
        current_step=current_step,
        error_message=error_msg,
        total_scenarios=total_sc,
        completed_scenarios=passed_sc,
        total_verdicts=total_vd,
        execution_mode=spec.get("execution_mode") or row.get("execution_mode") or row.get("mode") or "faithful",
        original_model=spec.get("original_model") or row.get("original_model", "openai/gpt-4o"),
        executed_model=spec.get("executed_model") or row.get("executed_model", "openai/gpt-4o"),
        model_substitution=bool(spec.get("model_substitution") if "model_substitution" in spec else row.get("model_substitution", False)),
        confidence=spec.get("confidence") or row.get("confidence", "HIGH"),
        fidelity=float(spec.get("fidelity") or row.get("fidelity") or 1.0),
        evaluator_version=spec.get("evaluator_version") or row.get("evaluator_version") or "v2.0",
        rule_set_version=spec.get("rule_set_version") or row.get("rule_set_version") or "reliability-rules-v2",
        created_at=str(spec.get("created_at") or row.get("created_at") or row.get("started_at") or _now()),
        started_at=spec.get("started_at") or row.get("started_at"),
        finished_at=spec.get("finished_at") or row.get("completed_at")
    )


def _serialize_scorecard(key: str, sc: ReliabilityScorecard) -> Dict[str, Any]:
    return {
        "evaluation_id": sc.evaluation_id,
        "agent_id": sc.agent_id,
        "agent_name": sc.agent_name,
        "agent_version": sc.agent_version,
        "correctness": sc.correctness,
        "safety": sc.safety,
        "robustness": sc.robustness,
        "tool_discipline": sc.tool_discipline,
        "goal_adherence": sc.goal_adherence,
        "composite": sc.composite,
        "safety_axis": sc.safety_axis,
        "capability_axis": sc.capability_axis,
        "total_scenarios": sc.total_scenarios,
        "passed": sc.passed,
        "failed": sc.failed,
        "blocked": sc.blocked,
        "inconclusive": sc.inconclusive,
        "critical_failures": sc.critical_failures,
        "judge_agreement_rate": sc.judge_agreement_rate,
        "score_formula_version": sc.score_formula_version,
        "scorecard_spec": sc.model_dump() if hasattr(sc, "model_dump") else sc.dict()
    }

def _deserialize_scorecard(row: Dict[str, Any]) -> ReliabilityScorecard:
    spec = row.get("scorecard_spec") or {}
    if spec:
        return ReliabilityScorecard(**spec)
    return ReliabilityScorecard(
        evaluation_id=row["evaluation_id"],
        agent_id=row.get("agent_id", ""),
        agent_name=row.get("agent_name", ""),
        agent_version=row.get("agent_version", "v1.0"),
        correctness=float(row.get("correctness", 0)),
        safety=float(row.get("safety", 0)),
        robustness=float(row.get("robustness", 0)),
        tool_discipline=float(row.get("tool_discipline", 0)),
        goal_adherence=float(row.get("goal_adherence", 0)),
        composite=float(row.get("composite", 0)),
        safety_axis=float(row.get("safety_axis", 0)),
        capability_axis=float(row.get("capability_axis", 0)),
        total_scenarios=int(row.get("total_scenarios", 0)),
        passed=int(row.get("passed", 0)),
        failed=int(row.get("failed", 0)),
        blocked=int(row.get("blocked", 0)),
        inconclusive=int(row.get("inconclusive", 0)),
        critical_failures=int(row.get("critical_failures", 0)),
        judge_agreement_rate=row.get("judge_agreement_rate"),
        score_formula_version=row.get("score_formula_version", "v2.0-weighted")
    )

def _serialize_verdicts(key: str, verdicts: List[RunVerdict]) -> Dict[str, Any]:
    return {
        "id": f"verd-list-{key}",
        "evaluation_run_id": key,
        "record_type": "verdicts",
        "status": "completed",
        "evidence": {"verdicts": [v.model_dump() if hasattr(v, "model_dump") else v.dict() for v in verdicts]}
    }

def _deserialize_verdicts(row: Dict[str, Any]) -> List[RunVerdict]:
    evidence = row.get("evidence") or {}
    verdicts_data = evidence.get("verdicts", [])
    return [RunVerdict(**v) for v in verdicts_data]

def _serialize_traces(key: str, traces: List[ExecutionTrace]) -> Dict[str, Any]:
    return {
        "id": f"trace-list-{key}",
        "evaluation_run_id": key,
        "record_type": "traces",
        "status": "completed",
        "evidence": {"traces": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in traces]}
    }

def _deserialize_traces(row: Dict[str, Any]) -> List[ExecutionTrace]:
    evidence = row.get("evidence") or {}
    traces_data = evidence.get("traces", [])
    return [ExecutionTrace(**t) for t in traces_data]

def _serialize_clusters(key: str, clusters: List[FailureCluster]) -> Dict[str, Any]:
    # We can write each cluster to failure_clusters table!
    # But since it's a list, let's write the first one or upsert them.
    # For bulk dictionary compatibility, we save as a single JSONB container or mapping.
    # Let's save to failure_clusters table by upserting all.
    return {
        "id": f"cluster-list-{key}",
        "evaluation_id": key,
        "member_verdict_ids": {"clusters": [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in clusters]}
    }

def _deserialize_clusters(row: Dict[str, Any]) -> List[FailureCluster]:
    data = row.get("member_verdict_ids") or {}
    clusters_data = data.get("clusters", [])
    return [FailureCluster(**c) for c in clusters_data]

def _serialize_pipeline_run(key: str, run: PipelineRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "pipeline_type": "agent_intake",
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at
    }

def _deserialize_pipeline_run(row: Dict[str, Any]) -> PipelineRun:
    return PipelineRun(
        id=row["id"],
        agent_id=row.get("agent_id") or "",
        agent_name=row.get("agent_name") or "",
        status=row.get("status") or "queued",
        started_at=row.get("started_at") or _now(),
        completed_at=row.get("completed_at")
    )



def _serialize_agent_test_spec(key: str, spec: AgentTestSpecification) -> Dict[str, Any]:
    return {
        "id": spec.id,
        "agent_id": spec.agent_id,
        "goal": spec.goal,
        "inputs": spec.inputs,
        "tools": spec.tools,
        "workflow": spec.workflow,
        "risks": spec.risks,
        "created_at": spec.created_at,
    }


def _deserialize_agent_test_spec(row: Dict[str, Any]) -> AgentTestSpecification:
    return AgentTestSpecification(
        id=row["id"],
        agent_id=row["agent_id"],
        goal=row.get("goal", ""),
        inputs=row.get("inputs", []),
        tools=row.get("tools", []),
        workflow=row.get("workflow", []),
        risks=row.get("risks", []),
        created_at=str(row.get("created_at", _now())),
    )


def _serialize_sandbox_spec(key: str, spec: SandboxSpecification) -> Dict[str, Any]:
    runtime = spec.runtime or {}
    return {
        "id": spec.id,
        "agent_id": spec.agent_id,
        "language": runtime.get("language") or "python",
        "runtime_version": runtime.get("version") or "3.12",
        "base_image": runtime.get("base_image") or "python:3.12-slim",
        "entrypoint": runtime.get("entrypoint") or "agent.py",
        "runtime": runtime,
        "dependencies": spec.dependencies,
        "filesystem": spec.filesystem,
        "network": spec.network,
        "tools": spec.tools,
        "credentials": spec.credentials,
        "status": spec.status or "READY",
        "blockers": spec.blockers or [],
        "created_at": spec.created_at,
    }


def _deserialize_sandbox_spec(row: Dict[str, Any]) -> SandboxSpecification:
    runtime = row.get("runtime") or {}
    if "language" not in runtime and row.get("language"):
        runtime["language"] = row.get("language")
    if "version" not in runtime and row.get("runtime_version"):
        runtime["version"] = row.get("runtime_version")
    if "entrypoint" not in runtime and row.get("entrypoint"):
        runtime["entrypoint"] = row.get("entrypoint")
    if "base_image" not in runtime and row.get("base_image"):
        runtime["base_image"] = row.get("base_image")
    return SandboxSpecification(
        id=row["id"],
        agent_id=row["agent_id"],
        runtime=runtime,
        dependencies=row.get("dependencies", []),
        filesystem=row.get("filesystem", {}),
        network=row.get("network", {}),
        tools=row.get("tools", []),
        credentials=row.get("credentials", []),
        status=row.get("status", "READY"),
        blockers=row.get("blockers", []),
        created_at=str(row.get("created_at", _now())),
    )


# ---------------------------------------------------------------------------
# Dependency Setup Flow Serializers / Deserializers
# ---------------------------------------------------------------------------
def _serialize_agent_dependency(key: str, dep: AgentDependency) -> Dict[str, Any]:
    return {
        "id": dep.id,
        "agent_id": dep.agent_id,
        "dependency_name": dep.dependency_name,
        "dependency_type": dep.dependency_type,
        "required": dep.required,
        "detected_from": dep.detected_from,
    }

def _deserialize_agent_dependency(row: Dict[str, Any]) -> AgentDependency:
    return AgentDependency(
        id=row["id"],
        agent_id=row.get("agent_id", ""),
        dependency_name=row.get("dependency_name", ""),
        dependency_type=row.get("dependency_type", "runtime"),
        required=row.get("required", True),
        detected_from=row.get("detected_from", "source_code"),
    )

def _serialize_platform_resource(key: str, res: PlatformResource) -> Dict[str, Any]:
    return {
        "id": res.id,
        "capability": res.capability,
        "provider": res.provider,
        "mode": res.mode,
        "status": res.status,
    }

def _deserialize_platform_resource(row: Dict[str, Any]) -> PlatformResource:
    return PlatformResource(
        id=row["id"],
        capability=row.get("capability", ""),
        provider=row.get("provider", ""),
        mode=row.get("mode", "sandbox"),
        status=row.get("status", "active"),
    )

def _serialize_dependency_binding(key: str, bind: DependencyBinding) -> Dict[str, Any]:
    return {
        "id": bind.id,
        "agent_id": bind.agent_id,
        "dependency_name": bind.dependency_name,
        "resolution_type": bind.resolution_type,
        "status": bind.status,
        "user_value": bind.user_value,
        "created_at": bind.created_at,
    }

def _deserialize_dependency_binding(row: Dict[str, Any]) -> DependencyBinding:
    return DependencyBinding(
        id=row["id"],
        agent_id=row.get("agent_id", ""),
        dependency_name=row.get("dependency_name", ""),
        resolution_type=row.get("resolution_type", "block"),
        status=row.get("status", "unsupported"),
        user_value=row.get("user_value"),
        created_at=row.get("created_at", _now()),
    )


def _serialize_execution_job(key: str, job: ExecutionJob) -> Dict[str, Any]:
    return {
        "id": job.id,
        "agent_id": job.agent_id,
        "agent_name": job.agent_name,
        "status": job.status,
        "total_scenarios": job.total_scenarios,
        "completed_scenarios": job.completed_scenarios,
        "scenario_ids": job.scenario_ids,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def _deserialize_execution_job(row: Dict[str, Any]) -> ExecutionJob:
    return ExecutionJob(
        id=row["id"],
        agent_id=row.get("agent_id", ""),
        agent_name=row.get("name") or row.get("agent_name", ""),
        status=row.get("status", "pending"),
        total_scenarios=int(row.get("total_scenarios", 0)),
        completed_scenarios=int(row.get("completed_scenarios", 0)),
        scenario_ids=row.get("scenario_ids", []),
        created_at=str(row.get("created_at", _now())),
        finished_at=row.get("finished_at"),
    )


def _serialize_ai_generation_run(key: str, run: AIGenerationRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "stage": run.stage,
        "provider": run.provider,
        "model": run.model,
        "status": run.status,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "error_message": run.error_message,
        "prompt_version": run.prompt_version,
        "input_reference": run.input_reference,
        "output_reference": run.output_reference,
        "created_at": run.created_at or _now(),
    }


def _deserialize_ai_generation_run(row: Dict[str, Any]) -> AIGenerationRun:
    return AIGenerationRun(
        id=row["id"],
        stage=row.get("stage", ""),
        provider=row.get("provider", "gemini"),
        model=row.get("model", ""),
        status=row.get("status", "SUCCESS"),
        input_tokens=row.get("input_tokens", 0),
        output_tokens=row.get("output_tokens", 0),
        error_message=row.get("error_message"),
        prompt_version=row.get("prompt_version", "v1"),
        input_reference=row.get("input_reference"),
        output_reference=row.get("output_reference"),
        created_at=row.get("created_at"),
    )


def _serialize_execution_session(key: str, s: Any) -> Dict[str, Any]:
    if isinstance(s, dict):
        return {
            "id": s.get("id", key),
            "evaluation_run_id": s.get("execution_run_id") or s.get("evaluation_run_id"),
            "agent_version_id": s.get("agent_version_id"),
            "scenario_id": s.get("scenario_id"),
            "sandbox_session_id": s.get("sandbox_session_id"),
            "status": s.get("status", "active"),
            "started_at": s.get("started_at", _now()),
            "completed_at": s.get("finished_at") or s.get("completed_at"),
        }

    return {
        "id": getattr(s, "id", key),
        "evaluation_run_id": getattr(s, "execution_run_id", getattr(s, "evaluation_run_id", None)),
        "agent_version_id": getattr(s, "agent_version_id", None),
        "scenario_id": getattr(s, "scenario_id", None),
        "sandbox_session_id": getattr(s, "sandbox_session_id", None),
        "status": getattr(s, "status", "active"),
        "started_at": getattr(s, "started_at", _now()),
        "completed_at": getattr(s, "finished_at", getattr(s, "completed_at", None)),
    }


def _deserialize_execution_session(row: Dict[str, Any]) -> ExecutionSession:
    pre_snap = None
    if row.get("pre_snapshot"):
        try:
            pre_snap = PreExecutionSnapshot(**row["pre_snapshot"])
        except Exception:
            pre_snap = row["pre_snapshot"]

    post_snap = None
    if row.get("post_snapshot"):
        try:
            post_snap = PostExecutionSnapshot(**row["post_snapshot"])
        except Exception:
            post_snap = row["post_snapshot"]

    ev_pkg = None
    if row.get("evidence_package"):
        try:
            ev_pkg = EvidencePackage(**row["evidence_package"])
        except Exception:
            ev_pkg = row["evidence_package"]

    return ExecutionSession(
        id=row["id"],
        execution_run_id=row.get("evaluation_run_id") or row.get("execution_run_id", ""),
        agent_version_id=row.get("agent_version_id") or "",
        scenario_id=row.get("scenario_id") or "",
        sandbox_session_id=row.get("sandbox_session_id"),
        status=row.get("status", "SCENARIO_SELECTED"),
        started_at=row.get("started_at", _now()),
        finished_at=row.get("completed_at") or row.get("finished_at"),
        trajectory_hash=row.get("trajectory_hash"),
        pre_snapshot=pre_snap,
        post_snapshot=post_snap,
        evidence_package=ev_pkg,
        evidence_graph=row.get("evidence_graph"),
    )




def _serialize_execution_step(key: str, stp: ExecutionStep) -> Dict[str, Any]:
    return {
        "id": stp.id,
        "execution_session_id": stp.execution_session_id,
        "step_number": stp.step_number,
        "event_type": stp.event_type,
        "actor": stp.actor,
        "input_data": stp.input_data,
        "output_data": stp.output_data,
        "metadata": stp.metadata,
        "created_at": stp.created_at or _now(),
    }


def _deserialize_execution_step(row: Dict[str, Any]) -> ExecutionStep:
    return ExecutionStep(
        id=row["id"],
        execution_session_id=row.get("execution_session_id", ""),
        step_number=row.get("step_number", 0),
        event_type=row.get("event_type", "OBSERVATION"),
        actor=row.get("actor", "agent"),
        input_data=row.get("input_data", {}),
        output_data=row.get("output_data", {}),
        metadata=row.get("metadata", {}),
        created_at=row.get("created_at", _now()),
    )


def _serialize_execution_metrics(key: str, m: ExecutionMetrics) -> Dict[str, Any]:
    return {
        "id": m.id,
        "execution_session_id": m.execution_session_id,
        "steps_count": m.steps_count,
        "tool_calls_count": m.tool_calls_count,
        "failed_tools": m.failed_tools,
        "tokens_used": m.tokens_used,
        "latency_ms": m.latency_ms,
        "cost": m.cost,
        "created_at": m.created_at or _now(),
    }


def _deserialize_execution_metrics(row: Dict[str, Any]) -> ExecutionMetrics:
    return ExecutionMetrics(
        id=row["id"],
        execution_session_id=row.get("execution_session_id", ""),
        steps_count=row.get("steps_count", 0),
        tool_calls_count=row.get("tool_calls_count", 0),
        failed_tools=row.get("failed_tools", 0),
        tokens_used=row.get("tokens_used", 0),
        latency_ms=row.get("latency_ms", 0.0),
        cost=row.get("cost", 0.0),
        created_at=row.get("created_at"),
    )


def _serialize_benchmark_record(key: str, b: BenchmarkRecord) -> Dict[str, Any]:
    return {
        "id": b.id,
        "agent_version_id": b.agent_version_id,
        "scenario_id": b.scenario_id,
        "execution_session_id": b.execution_session_id,
        "trajectory": b.trajectory,
        "evaluation": b.evaluation,
        "human_feedback": b.human_feedback,
        "quality_score": b.quality_score,
        "created_at": b.created_at or _now(),
    }


def _deserialize_benchmark_record(row: Dict[str, Any]) -> BenchmarkRecord:
    return BenchmarkRecord(
        id=row["id"],
        agent_version_id=row.get("agent_version_id"),
        scenario_id=row.get("scenario_id"),
        execution_session_id=row.get("execution_session_id", ""),
        trajectory=row.get("trajectory", []),
        evaluation=row.get("evaluation", {}),
        human_feedback=row.get("human_feedback"),
        quality_score=row.get("quality_score", 0.0),
        created_at=row.get("created_at", _now()),
    )


def _serialize_behavior_profile(key: str, bp: AgentBehaviorProfile) -> Dict[str, Any]:
    return {
        "id": bp.id,
        "agent_id": bp.agent_id,
        "agent_version_id": bp.agent_version_id or bp.agent_id,
        "schema_version": bp.schema_version,
        "profile_json": bp.model_dump() if hasattr(bp, "model_dump") else bp.dict(),
        "analysis_run_id": bp.analysis_run_id,
        "confidence": bp.confidence_score,
        "created_at": bp.created_at or _now(),
    }


def _deserialize_behavior_profile(row: Dict[str, Any]) -> AgentBehaviorProfile:
    p_json = row.get("profile_json") or {}
    if not p_json.get("agent_id") and row.get("agent_id"):
        p_json["agent_id"] = row.get("agent_id")
    return AgentBehaviorProfile(**p_json)


def _serialize_repair_session(key: str, sess: RepairSession) -> Dict[str, Any]:
    return {
        "id": sess.id,
        "agent_id": sess.agent_id,
        "agent_name": sess.agent_name,
        "status": sess.status.value if hasattr(sess.status, "value") else str(sess.status),
        "session_spec": sess.model_dump() if hasattr(sess, "model_dump") else sess.dict()
    }


def _deserialize_repair_session(row: Dict[str, Any]) -> RepairSession:
    spec = row.get("session_spec") or {}
    return RepairSession(**spec)


def _serialize_regression_test(key: str, reg: RegressionTest) -> Dict[str, Any]:
    return {
        "id": reg.id,
        "source_evaluation_id": reg.source_evaluation_id,
        "source_verdict_id": reg.source_verdict_id,
        "agent_id": reg.agent_id,
        "scenario_id": reg.scenario_id,
        "failure_category": reg.failure_category,
        "severity": reg.severity,
        "status": reg.status,
        "created_at": reg.created_at,
        "updated_at": reg.updated_at,
        "regression_spec": reg.model_dump() if hasattr(reg, "model_dump") else reg.dict()
    }


def _deserialize_regression_test(row: Dict[str, Any]) -> RegressionTest:
    spec = row.get("regression_spec") or {}
    if spec:
        return RegressionTest(**spec)
    return RegressionTest(
        id=row["id"],
        source_evaluation_id=row.get("source_evaluation_id", ""),
        source_verdict_id=row.get("source_verdict_id", ""),
        agent_id=row.get("agent_id", ""),
        scenario_id=row.get("scenario_id", ""),
        failure_category=row.get("failure_category", ""),
        severity=row.get("severity", "high"),
        assertion=row.get("assertion", {}),
        status=row.get("status", "ACTIVE"),
        created_at=row.get("created_at", _now()),
        updated_at=row.get("updated_at", _now())
    )


def _serialize_execution_preflight(key: str, p: Any) -> Dict[str, Any]:
    return p.model_dump() if hasattr(p, "model_dump") else p.dict()

def _deserialize_execution_preflight(row: Dict[str, Any]) -> Any:
    return ExecutionPreflight(**row)

def _serialize_execution_run(key: str, p: Any) -> Dict[str, Any]:
    if isinstance(p, dict):
        return p
    return {
        "id": getattr(p, "id", key),
        "agent_id": getattr(p, "agent_id", ""),
        "status": getattr(p, "status", "RUNNING"),
        "raw_logs": getattr(p, "failure_reason", None),
        "structured_events": getattr(p, "scenario_ids", []),
        "created_at": getattr(p, "started_at", _now()),
    }

def _deserialize_execution_run(row: Dict[str, Any]) -> Any:
    return ExecutionRun(
        id=row["id"],
        agent_id=row.get("agent_id", ""),
        status=row.get("status", "SCENARIO_SELECTED"),
        failure_reason=row.get("raw_logs"),
        scenario_ids=row.get("structured_events") or [],
        started_at=row.get("created_at", _now())
    )


def _serialize_execution_action(key: str, p: Any) -> Dict[str, Any]:
    full_data = p.model_dump() if hasattr(p, "model_dump") else p.dict()
    return {
        "id": full_data.get("id", key),
        "execution_session_id": full_data.get("execution_session_id", ""),
        "action_type": full_data.get("action_type", "TOOL_CALL"),
        "payload": full_data,
        "created_at": full_data.get("timestamp") or _now()
    }

def _deserialize_execution_action(row: Dict[str, Any]) -> Any:
    payload = row.get("payload") or {}
    if payload and isinstance(payload, dict):
        return ExecutionAction(**payload)
    return ExecutionAction(**row)

def _serialize_execution_artifact(key: str, p: Any) -> Dict[str, Any]:
    full_data = p.model_dump() if hasattr(p, "model_dump") else p.dict()
    return {
        "id": full_data.get("id", key),
        "execution_run_id": full_data.get("execution_run_id") or full_data.get("session_id", ""),
        "artifact_name": full_data.get("artifact_name") or full_data.get("name", "artifact"),
        "artifact_path": full_data.get("artifact_path") or full_data.get("path", ""),
        "mime_type": full_data.get("mime_type", "text/plain"),
        "size_bytes": full_data.get("size_bytes", 0),
        "created_at": full_data.get("created_at") or _now()
    }

def _deserialize_execution_artifact(row: Dict[str, Any]) -> Any:
    return ExecutionArtifact(**row)

def _serialize_model_connection(key: str, mc: ModelConnection) -> Dict[str, Any]:
    data = mc.model_dump() if hasattr(mc, "model_dump") else mc.dict()
    meta = data.get("metadata") or {}
    for k in ["owner_type", "connection_type", "context_window", "supports_tools", "training_capability", "model_weight_access", "is_active", "last_ping_at"]:
        if k in data:
            meta[k] = data[k]
    return {
        "id": data.get("id", key),
        "name": data.get("name", "Model Connection"),
        "provider": data.get("provider", "gemini"),
        "base_url": data.get("base_url", ""),
        "model_identifier": data.get("model_identifier", "gemini-3.6-flash"),
        "api_key": data.get("api_key"),
        "role": data.get("role", "test_agent_ai"),
        "is_local": bool(data.get("is_local", False)),
        "health_status": data.get("health_status", "healthy"),
        "latency_ms": float(data.get("latency_ms") or 0.0),
        "supports_structured_json": bool(data.get("supports_structured_json", True)),
        "metadata": meta,
        "created_at": data.get("created_at") or _now(),
        "updated_at": data.get("updated_at") or _now(),
    }

def _deserialize_model_connection(row: Dict[str, Any]) -> ModelConnection:
    meta = row.get("metadata") or {}
    clean_row = dict(row)
    if isinstance(meta, dict):
        for k, v in meta.items():
            if k not in clean_row:
                clean_row[k] = v
    return ModelConnection(**clean_row)

def _serialize_training_dataset(key: str, td: TrainingDataset) -> Dict[str, Any]:
    return td.model_dump() if hasattr(td, "model_dump") else td.dict()

def _deserialize_training_dataset(row: Dict[str, Any]) -> TrainingDataset:
    return TrainingDataset(**row)

def _serialize_diagnosis_report(key: str, dr: AgentDiagnosisReport) -> Dict[str, Any]:
    return dr.model_dump() if hasattr(dr, "model_dump") else dr.dict()

def _deserialize_diagnosis_report(row: Dict[str, Any]) -> AgentDiagnosisReport:
    return AgentDiagnosisReport(**row)

def _serialize_training_job(key: str, tj: TrainingJob) -> Dict[str, Any]:
    return tj.model_dump() if hasattr(tj, "model_dump") else tj.dict()

def _deserialize_training_job(row: Dict[str, Any]) -> TrainingJob:
    return TrainingJob(**row)

def _serialize_model_version(key: str, mv: ModelVersionRecord) -> Dict[str, Any]:
    return mv.model_dump() if hasattr(mv, "model_dump") else mv.dict()

def _deserialize_model_version(row: Dict[str, Any]) -> ModelVersionRecord:
    return ModelVersionRecord(**row)

def _serialize_stage_judge_audit(key: str, a: Any) -> Dict[str, Any]:
    return a.model_dump() if hasattr(a, "model_dump") else (a if isinstance(a, dict) else a.dict())

def _deserialize_stage_judge_audit(row: Dict[str, Any]) -> Any:
    from app.agent_testers.models import StageAuditVerdict
    return StageAuditVerdict(**row)

def _serialize_multi_agent_audit(key: str, a: Any) -> Dict[str, Any]:
    return a.model_dump() if hasattr(a, "model_dump") else (a if isinstance(a, dict) else a.__dict__)

def _deserialize_multi_agent_audit(row: Dict[str, Any]) -> Any:
    from app.agent_testers.models import MultiAgentAuditVerdict
    try:
        return MultiAgentAuditVerdict(**row)
    except Exception:
        return row


def _serialize_agent_version_record(key: str, v: AgentVersionRecord) -> Dict[str, Any]:
    return {
        "id": v.id,
        "agent_id": v.agent_id,
        "version": v.version_label,
        "version_label": v.version_label,
        "parent_version_id": v.parent_version_id,
        "is_latest": v.is_latest,
        "change_summary": v.change_summary,
        "source_files": v.source_files,
        "patch_artifact_id": v.patch_artifact_id,
        "reliability_score": v.reliability_score,
        "release_decision": v.release_decision,
        "created_at": v.created_at
    }

def _deserialize_agent_version_record(row: Dict[str, Any]) -> AgentVersionRecord:
    is_latest_val = row.get("is_latest")
    if is_latest_val is None:
        is_latest_val = True
    else:
        is_latest_val = bool(is_latest_val)
    return AgentVersionRecord(
        id=row["id"],
        agent_id=row.get("agent_id") or "",
        version_label=row.get("version_label") or row.get("version") or "v1.0",
        parent_version_id=row.get("parent_version_id"),
        is_latest=is_latest_val,
        change_summary=row.get("change_summary") or "Baseline version",
        source_files=row.get("source_files") or {},
        patch_artifact_id=row.get("patch_artifact_id"),
        reliability_score=row.get("reliability_score"),
        release_decision=row.get("release_decision"),
        created_at=str(row.get("created_at") or _now())
    )



def _serialize_patch_artifact(key: str, p: PatchArtifact) -> Dict[str, Any]:
    return p.model_dump() if hasattr(p, "model_dump") else p.dict()

def _deserialize_patch_artifact(row: Dict[str, Any]) -> PatchArtifact:
    return PatchArtifact(**row)

def _serialize_finding(key: str, f: Finding) -> Dict[str, Any]:
    return f.model_dump() if hasattr(f, "model_dump") else f.dict()

def _deserialize_finding(row: Dict[str, Any]) -> Finding:
    return Finding(**row)

def _serialize_test_case_spec(key: str, tc: TestCaseSpecification) -> Dict[str, Any]:
    return tc.model_dump() if hasattr(tc, "model_dump") else tc.dict()

def _deserialize_test_case_spec(row: Dict[str, Any]) -> TestCaseSpecification:
    return TestCaseSpecification(**row)

# ---------------------------------------------------------------------------
# Global Store Implementation

# ---------------------------------------------------------------------------
class Store:
    def __init__(self):
        self.agents = SyncedDict("agents", _serialize_agent, _deserialize_agent)
        self.scenarios = SyncedDict("scenarios", _serialize_scenario, _deserialize_scenario)
        self.jobs = SyncedDict("evaluation_runs", _serialize_job, _deserialize_job)
        self.scorecards = SyncedDict("scorecards", _serialize_scorecard, _deserialize_scorecard, "evaluation_id")
        # Use separate logical table names so verdicts and traces don't share the same snapshot file
        self.verdicts = SyncedDict("evaluation_verdicts", _serialize_verdicts, _deserialize_verdicts, "evaluation_run_id")
        self.traces = SyncedDict("evaluation_traces", _serialize_traces, _deserialize_traces, "evaluation_run_id")
        self.clusters = SyncedDict("failure_clusters", _serialize_clusters, _deserialize_clusters, "evaluation_run_id")


        self.pipeline_runs = SyncedDict("pipeline_runs", _serialize_pipeline_run, _deserialize_pipeline_run)
        self.agent_test_specs = SyncedDict("agent_test_specifications", _serialize_agent_test_spec, _deserialize_agent_test_spec)
        self.sandbox_specs = SyncedDict("sandbox_specifications", _serialize_sandbox_spec, _deserialize_sandbox_spec)
        self.agent_dependencies = SyncedDict("agent_dependencies", _serialize_agent_dependency, _deserialize_agent_dependency)
        self.platform_resources = SyncedDict("platform_resources", _serialize_platform_resource, _deserialize_platform_resource)
        self.dependency_bindings = SyncedDict("dependency_bindings", _serialize_dependency_binding, _deserialize_dependency_binding)
        self.execution_jobs = SyncedDict("execution_jobs", _serialize_execution_job, _deserialize_execution_job)
        self.ai_generation_runs = SyncedDict("ai_generation_runs", _serialize_ai_generation_run, _deserialize_ai_generation_run)
        self.execution_sessions = SyncedDict("execution_sessions", _serialize_execution_session, _deserialize_execution_session)
        self.execution_steps = SyncedDict("execution_steps", _serialize_execution_step, _deserialize_execution_step)
        self.execution_metrics = SyncedDict("execution_metrics", _serialize_execution_metrics, _deserialize_execution_metrics)
        self.benchmark_records = SyncedDict("benchmark_records", _serialize_benchmark_record, _deserialize_benchmark_record)
        self.agent_behavior_profiles = SyncedDict("agent_behavior_profiles", _serialize_behavior_profile, _deserialize_behavior_profile)
        self.execution_preflights = SyncedDict("execution_preflights", _serialize_execution_preflight, _deserialize_execution_preflight)
        self.execution_runs = SyncedDict("execution_runs", _serialize_execution_run, _deserialize_execution_run)
        self.execution_artifacts = SyncedDict("execution_artifacts", _serialize_execution_artifact, _deserialize_execution_artifact)
        self.execution_actions = SyncedDict("execution_actions", _serialize_execution_action, _deserialize_execution_action)
        self.repair_sessions = SyncedDict("repair_sessions", _serialize_repair_session, _deserialize_repair_session)
        self.regression_tests = SyncedDict("regression_tests", _serialize_regression_test, _deserialize_regression_test)
        self.model_connections = SyncedDict("model_connections", _serialize_model_connection, _deserialize_model_connection)
        self.training_datasets = SyncedDict("training_datasets", _serialize_training_dataset, _deserialize_training_dataset)
        self.diagnosis_reports = SyncedDict("diagnosis_reports", _serialize_diagnosis_report, _deserialize_diagnosis_report, "evaluation_run_id")
        self.training_jobs = SyncedDict("training_jobs", _serialize_training_job, _deserialize_training_job)
        self.model_versions = SyncedDict("model_versions", _serialize_model_version, _deserialize_model_version)
        self.stage_judge_audits = SyncedDict("stage_judge_audits", _serialize_stage_judge_audit, _deserialize_stage_judge_audit)
        self.multi_agent_stage_audits = SyncedDict("multi_agent_stage_audits", _serialize_multi_agent_audit, _deserialize_multi_agent_audit)
        self.agent_versions = SyncedDict("agent_versions", _serialize_agent_version_record, _deserialize_agent_version_record)
        self.patch_artifacts = SyncedDict("patch_artifacts", _serialize_patch_artifact, _deserialize_patch_artifact)
        self.findings = SyncedDict("findings", _serialize_finding, _deserialize_finding)
        self.canonical_test_cases = SyncedDict("canonical_test_cases", _serialize_test_case_spec, _deserialize_test_case_spec)
        self._local_artifacts: Dict[str, Dict[str, Any]] = {}




        # Seed platform-provided resources (free sandbox / mock capabilities)
        self._seed_platform_resources()

        # Demo agents are loaded only when the user selects them from Intake.

    def save_execution_preflight(self, preflight: Any) -> None:
        self.execution_preflights[preflight.id] = preflight

    def get_execution_preflight(self, preflight_id: str) -> Optional[Any]:
        return self.execution_preflights.get(preflight_id)

    def save_execution_run(self, run: Any) -> None:
        self.execution_runs[run.id] = run

    def get_execution_run(self, run_id: str) -> Optional[Any]:
        return self.execution_runs.get(run_id)

    def save_execution_session(self, session: Any) -> None:
        sid = getattr(session, "id", None) or (session.get("id") if isinstance(session, dict) else None)
        if sid:
            self.execution_sessions[sid] = session

    def get_execution_session(self, session_id: str) -> Optional[Any]:
        return self.execution_sessions.get(session_id)

    def save_execution_artifact(self, artifact: Any) -> None:
        self.execution_artifacts[artifact.id] = artifact

    def get_execution_artifacts(self, session_id: str) -> List[Any]:
        return [a for a in self.execution_artifacts.values() if a.execution_session_id == session_id]

    def save_execution_action(self, action: Any) -> None:
        self.execution_actions[action.id] = action

    def get_execution_actions(self, session_id: str) -> List[Any]:
        actions = [a for a in self.execution_actions.values() if a.execution_session_id == session_id]
        return sorted(actions, key=lambda x: x.sequence)


    def _seed_platform_resources(self):
        """Seed the platform with MVP sandbox/mock resources that are always available."""
        if len(self.platform_resources) > 0:
            return

        mvp_resources = [
            PlatformResource(id="plat-python-runtime", capability="PYTHON_RUNTIME", provider="Python 3.12 Sandbox", mode="sandbox", status="active"),
            PlatformResource(id="plat-web-search", capability="WEB_SEARCH", provider="Internal Search Sandbox", mode="sandbox", status="active"),
            PlatformResource(id="plat-browser", capability="BROWSER", provider="Playwright Chromium Sandbox", mode="sandbox", status="active"),
            PlatformResource(id="plat-database", capability="DATABASE", provider="PostgreSQL Container Snapshot", mode="sandbox", status="active"),
            PlatformResource(id="plat-filesystem", capability="FILESYSTEM", provider="Virtual Workspace", mode="sandbox", status="active"),
            PlatformResource(id="plat-email", capability="EMAIL", provider="SMTP Mailbox Sandbox", mode="redirect", status="active"),
            PlatformResource(id="plat-news-api", capability="NEWS_API", provider="RSS/GNews Mock Files", mode="simulate", status="active"),
            PlatformResource(id="plat-location", capability="LOCATION_SERVICE", provider="OSM Sandbox", mode="sandbox", status="active"),
            PlatformResource(id="plat-identity", capability="IDENTITY", provider="Local Mock Accounts", mode="simulate", status="active"),
            PlatformResource(id="plat-payment", capability="PAYMENT", provider="Sandbox Credit Card Simulator", mode="simulate", status="active"),
            PlatformResource(id="plat-storage", capability="STORAGE", provider="S3/Drive Mock Directories", mode="sandbox", status="active"),
            PlatformResource(id="plat-git", capability="GIT", provider="Local Isolated Test Repositories", mode="sandbox", status="active"),
            PlatformResource(id="plat-api-mock", capability="API_MOCK", provider="Beeceptor-style Mock Responder", mode="simulate", status="active"),
        ]
        for res in mvp_resources:
            self.platform_resources[res.id] = res

    def _seed_data(self):
        """No hardcoded demo seeding. Agents are created strictly by user intake."""
        pass

    # Helper getters & setters
    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self.agents.get(agent_id)

    def list_agents(self) -> List[AgentRecord]:
        return list(self.agents.values())

    def save_agent(self, agent: AgentRecord):
        self.agents[agent.id] = agent
        if self.agents._sb:
            try:
                version_row = {
                    "id": f"{agent.id}-v1.0",
                    "agent_id": agent.id,
                    "version": agent.version_label or "v1.0",
                    "source_type": "upload",
                    "artifact_hash": agent.artifact_hash or "",
                    "entrypoint": agent.runtime_manifest.get("entrypoint", "agent.py") if agent.runtime_manifest else "agent.py",
                    "agent_spec": agent.runtime_manifest or {},
                    "analysis_status": "completed"
                }
                self.agents._sb.table("agent_versions").upsert(version_row).execute()
            except Exception as e:
                logger.debug(f"Could not sync agent_version to Supabase: {e}")

    def save_behavior_profile(self, bp: Any) -> None:
        """Persists AgentBehaviorProfile directly to memory and Supabase agent_behavior_profiles."""
        bp_dict = bp.model_dump() if hasattr(bp, "model_dump") else bp if isinstance(bp, dict) else bp.dict()
        agent_id = bp_dict.get("agent_id")
        bp_id = bp_dict.get("id") or f"abp-{agent_id}"
        if self.agents._sb and agent_id:
            try:
                row = {
                    "id": bp_id,
                    "agent_id": agent_id,
                    "agent_version_id": bp_dict.get("agent_version_id") or f"{agent_id}-v1.0",
                    "profile_data": bp_dict
                }
                self.agents._sb.table("agent_behavior_profiles").upsert(row, on_conflict="id").execute()
            except Exception as e:
                logger.warning(f"Could not persist agent_behavior_profile to Supabase: {e}")

    def delete_agent(self, agent_id: str) -> None:
        """Completely deletes an agent and all associated scenarios, runs, and artifacts from memory, database, and local snapshots."""
        if agent_id in self.agents:
            del self.agents[agent_id]

        valid_agent_ids = set(self.agents.keys())
        to_del_scenarios = [s_id for s_id, sc in list(self.scenarios.items()) if getattr(sc, 'agent_id', None) not in valid_agent_ids]
        for s_id in to_del_scenarios:
            del self.scenarios[s_id]

        to_del_jobs = [j_id for j_id, j in list(self.jobs.items()) if getattr(j, 'agent_id', None) == agent_id]
        for j_id in to_del_jobs:
            del self.jobs[j_id]

        to_del_specs = [s_id for s_id, spec in list(self.agent_test_specs.items()) if getattr(spec, 'agent_id', None) == agent_id]
        for s_id in to_del_specs:
            del self.agent_test_specs[s_id]

        to_del_sandbox = [s_id for s_id, spec in list(self.sandbox_specs.items()) if getattr(spec, 'agent_id', None) == agent_id]
        for s_id in to_del_sandbox:
            del self.sandbox_specs[s_id]

    def purge_all_agents(self) -> None:
        """Purges all agents, scenarios, jobs, and deletes snapshot files from disk for clean multi-user reset."""
        self.agents._local_data.clear()
        self.agents._save_local_snapshot()
        self.scenarios._local_data.clear()
        self.scenarios._save_local_snapshot()
        self.jobs._local_data.clear()
        self.jobs._save_local_snapshot()

        snapshot_dir = os.path.dirname(__file__)
        for fname in os.listdir(snapshot_dir):
            if fname.startswith("__snapshot_") and fname.endswith(".json"):
                try:
                    os.remove(os.path.join(snapshot_dir, fname))
                except Exception:
                    pass

    def save_behavior_profile(self, profile: AgentBehaviorProfile) -> None:
        self.agent_behavior_profiles[profile.id] = profile

    def get_behavior_profile(self, agent_id: str) -> Optional[AgentBehaviorProfile]:
        for p in self.agent_behavior_profiles.values():
            if p.agent_id == agent_id:
                return p
        return None

    def delete_agent(self, agent_id: str) -> None:
        """Deletes the agent and cascades deletion of all associated scenarios, artifacts, results, jobs, profiles, and files."""
        # 1. Delete associated scenarios
        scenario_keys = [k for k, v in self.scenarios.items() if getattr(v, "agent_id", None) == agent_id]
        for k in scenario_keys:
            try:
                del self.scenarios[k]
            except Exception:
                pass

        # 2. Delete associated evaluation runs (jobs), scorecards, verdicts, traces, and clusters
        eval_job_keys = [k for k, v in self.jobs.items() if getattr(v, "agent_id", None) == agent_id]
        for k in eval_job_keys:
            try:
                del self.jobs[k]
            except Exception:
                pass
            try:
                del self.scorecards[k]
            except Exception:
                pass
            try:
                del self.verdicts[k]
            except Exception:
                pass
            try:
                del self.traces[k]
            except Exception:
                pass
            try:
                del self.clusters[k]
            except Exception:
                pass

        # 3. Delete dependencies, platform resources bindings, and execution jobs
        dep_keys = [k for k, v in self.agent_dependencies.items() if getattr(v, "agent_id", None) == agent_id]
        for k in dep_keys:
            try:
                del self.agent_dependencies[k]
            except Exception:
                pass

        binding_keys = [k for k, v in self.dependency_bindings.items() if getattr(v, "agent_id", None) == agent_id]
        for k in binding_keys:
            try:
                del self.dependency_bindings[k]
            except Exception:
                pass

        execution_job_keys = [k for k, v in self.execution_jobs.items() if getattr(v, "agent_id", None) == agent_id]
        for k in execution_job_keys:
            try:
                del self.execution_jobs[k]
            except Exception:
                pass
            try:
                del self.traces[k]
            except Exception:
                pass
            try:
                del self.verdicts[k]
            except Exception:
                pass

        # 4. Clean up behavior profiles, sandbox specs, pipeline runs, and repair sessions
        profile_keys = [k for k, v in self.agent_behavior_profiles.items() if getattr(v, "agent_id", None) == agent_id]
        for k in profile_keys:
            try:
                del self.agent_behavior_profiles[k]
            except Exception:
                pass

        sb_keys = [k for k, v in self.sandbox_specs.items() if getattr(v, "agent_id", None) == agent_id]
        for k in sb_keys:
            try:
                del self.sandbox_specs[k]
            except Exception:
                pass

        pipe_keys = [k for k, v in self.pipeline_runs.items() if getattr(v, "agent_id", None) == agent_id]
        for k in pipe_keys:
            try:
                del self.pipeline_runs[k]
            except Exception:
                pass

        repair_keys = [k for k, v in self.repair_sessions.items() if getattr(v, "agent_id", None) == agent_id]
        for k in repair_keys:
            try:
                del self.repair_sessions[k]
            except Exception:
                pass

        td_keys = [k for k, v in self.training_datasets.items() if getattr(v, "agent_id", None) == agent_id]
        for k in td_keys:
            try:
                del self.training_datasets[k]
            except Exception:
                pass

        tj_keys = [k for k, v in self.training_jobs.items() if getattr(v, "agent_id", None) == agent_id]
        for k in tj_keys:
            try:
                del self.training_jobs[k]
            except Exception:
                pass

        mv_keys = [k for k, v in self.model_versions.items() if getattr(v, "agent_id", None) == agent_id]
        for k in mv_keys:
            try:
                del self.model_versions[k]
            except Exception:
                pass

        # 5. Clean up local uploaded files/artifacts cache
        if agent_id in self._local_artifacts:
            del self._local_artifacts[agent_id]

        # 6. Delete from live Supabase tables
        if self.agents._sb:
            tables_to_clean = [
                "agent_files",
                "agent_artifacts",
                "agent_versions",
                "agent_dependencies",
                "dependency_bindings",
                "sandbox_specifications",
                "agent_behavior_profiles",
                "scenarios",
                "evaluation_results",
                "evaluation_runs",
                "pipeline_runs",
                "repair_sessions",
                "training_datasets",
                "training_jobs",
            ]
            for t_name in tables_to_clean:
                try:
                    self.agents._sb.table(t_name).delete().eq("agent_id", agent_id).execute()
                except Exception:
                    pass
            try:
                self.agents._sb.table("agents").delete().eq("id", agent_id).execute()
            except Exception:
                pass

        # 7. Finally, delete the agent record from memory
        if agent_id in self.agents:
            del self.agents[agent_id]

    def save_agent_artifact(
        self,
        agent: AgentRecord,
        artifact: Any,
        source_files: Dict[str, str],
    ) -> None:
        """Persist the immutable upload manifest and its source files."""
        artifact_path = f"agent-artifacts/{agent.id}/{artifact.artifact_id}"
        artifact_row = {
            "id": artifact.artifact_id,
            "agent_id": agent.id,
            "artifact_type": "package" if len(source_files) > 1 else "single_file",
            "storage_provider": "supabase_database",
            "storage_path": artifact_path,
            "original_filename": artifact.files_list[0] if len(artifact.files_list) == 1 else None,
            "content_hash": artifact.artifact_hash,
            "size_bytes": artifact.total_bytes,
            "file_count": artifact.file_count,
            "input_type": artifact.input_type,
            "upload_metadata": {"source": "agent_intake", "immutable": True},
        }
        file_rows = []
        for path, content in source_files.items():
            file_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
            lower_path = path.lower()
            file_rows.append({
                "id": f"file-{hashlib.sha256(f'{artifact.artifact_id}:{path}'.encode('utf-8')).hexdigest()[:16]}",
                "agent_artifact_id": artifact.artifact_id,
                "path": path,
                "file_type": path.rsplit('.', 1)[-1] if '.' in path else "text",
                "language": "python" if lower_path.endswith('.py') else "typescript" if lower_path.endswith(('.ts', '.tsx')) else "javascript" if lower_path.endswith(('.js', '.jsx')) else None,
                "size_bytes": len(content.encode('utf-8')),
                "content_hash": file_hash,
                "storage_path": f"{artifact_path}/{path}",
                "is_entrypoint": lower_path.endswith(('agent.py', 'main.py', 'agent.ts', 'index.ts', 'index.js')),
                "is_config": lower_path.endswith(('.json', '.yaml', '.yml', '.toml')),
                "is_prompt": lower_path.endswith(('.prompt', '.txt', '.md')),
                "is_tool_definition": 'tool' in lower_path,
                "content": content,
                "metadata": {"source": "agent_intake"},
            })

        self._local_artifacts[artifact.artifact_id] = {"artifact": artifact_row, "files": file_rows}
        if self.agents._sb:
            try:
                self.agents._sb.table("agent_artifacts").upsert(artifact_row).execute()
                for file_row in file_rows:
                    self.agents._sb.table("agent_files").upsert(file_row).execute()
            except Exception as exc:
                logger.error(f"Supabase error saving artifact {artifact.artifact_id}: {exc}")

    def save_scenario(self, scenario: Scenario):
        self.scenarios[scenario.id] = scenario

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        return self.scenarios.get(scenario_id)

    def list_scenarios(self, agent_id: Optional[str] = None) -> List[Scenario]:
        if not hasattr(self, "_loaded_agent_scenarios"):
            self._loaded_agent_scenarios = set()

        # If specific agent requested and not yet loaded from Supabase into memory:
        if agent_id and agent_id not in self._loaded_agent_scenarios and self.scenarios._sb:
            try:
                res = self.scenarios._sb.table("scenarios").select("*").eq("agent_id", agent_id).execute()
                if res.data is not None:
                    for r in res.data:
                        try:
                            sc = self.scenarios.deserialize_fn(r)
                            self.scenarios._local_data[sc.id] = sc
                        except Exception as row_err:
                            logger.error(f"Error deserializing scenario row: {row_err}")
                self._loaded_agent_scenarios.add(agent_id)
            except Exception as e:
                logger.error(f"Supabase error fetching scenarios for agent {agent_id}: {e}")
        elif not agent_id and not getattr(self, "_all_scenarios_loaded", False) and self.scenarios._sb:
            try:
                res = self.scenarios._sb.table("scenarios").select("*").execute()
                if res.data is not None:
                    for r in res.data:
                        try:
                            sc = self.scenarios.deserialize_fn(r)
                            self.scenarios._local_data[sc.id] = sc
                        except Exception as row_err:
                            logger.error(f"Error deserializing scenario row: {row_err}")
                self._all_scenarios_loaded = True
            except Exception as e:
                logger.error(f"Supabase error fetching all scenarios: {e}")

        active_agent_ids = set(self.agents.keys())
        if agent_id:
            return [s for s in self.scenarios._local_data.values() if getattr(s, 'agent_id', None) == agent_id]
        if active_agent_ids:
            return [s for s in self.scenarios._local_data.values() if getattr(s, 'agent_id', None) in active_agent_ids]
        return list(self.scenarios._local_data.values())

    def clear_scenarios_for_agent(self, agent_id: str):
        """Clears previous scenarios for an agent so newly generated suites replace them."""
        # 1. Clear from memory
        keys_to_del = [k for k, s in self.scenarios._local_data.items() if getattr(s, 'agent_id', None) == agent_id]
        for k in keys_to_del:
            del self.scenarios._local_data[k]
        
        # 2. Delete from Supabase
        if self.scenarios._sb:
            try:
                self.scenarios._sb.table("scenarios").delete().eq("agent_id", agent_id).execute()
            except Exception as e:
                logger.debug(f"Supabase delete note for agent scenarios ({agent_id}): {e}")

        if hasattr(self, "_loaded_agent_scenarios"):
            self._loaded_agent_scenarios.add(agent_id)

    def clear_execution_data_for_agent(self, agent_id: str):
        """Clears previous execution jobs, traces, sessions, and bindings for an agent so a new run replaces the old batch."""
        execution_job_keys = [k for k, j in self.execution_jobs.items() if getattr(j, 'agent_id', None) == agent_id]
        execution_run_keys = [k for k, r in self.execution_runs.items() if getattr(r, 'agent_id', None) == agent_id]
        execution_ids = set(execution_job_keys) | set(execution_run_keys)

        for key in execution_job_keys:
            if key in self.execution_jobs:
                del self.execution_jobs[key]
        for key in execution_run_keys:
            if key in self.execution_runs:
                del self.execution_runs[key]

        for key in list(self.traces.keys()):
            if key in execution_ids:
                del self.traces[key]

        session_keys_to_delete = []
        for key, sess in list(self.execution_sessions.items()):
            if getattr(sess, 'execution_run_id', None) in execution_ids:
                session_keys_to_delete.append(key)
        for key in session_keys_to_delete:
            if key in self.execution_sessions:
                del self.execution_sessions[key]

        session_ids_to_delete = set(session_keys_to_delete)
        for key in list(self.execution_steps.keys()):
            if getattr(self.execution_steps[key], 'execution_session_id', None) in session_ids_to_delete:
                del self.execution_steps[key]
        for key in list(self.execution_metrics.keys()):
            if getattr(self.execution_metrics[key], 'execution_session_id', None) in session_ids_to_delete:
                del self.execution_metrics[key]
        for key in list(self.execution_artifacts.keys()):
            if getattr(self.execution_artifacts[key], 'execution_session_id', None) in session_ids_to_delete:
                del self.execution_artifacts[key]
        for key in list(self.execution_actions.keys()):
            if getattr(self.execution_actions[key], 'execution_session_id', None) in session_ids_to_delete:
                del self.execution_actions[key]

        for key in list(self.execution_preflights.keys()):
            if getattr(self.execution_preflights[key], 'execution_run_id', None) in execution_ids:
                del self.execution_preflights[key]

        if hasattr(self, '_bindings'):
            for key in list(self._bindings.keys()):
                if getattr(self._bindings.get(key), 'execution_id', None) in execution_ids:
                    del self._bindings[key]

    def save_verdicts(self, job_id: str, verdicts: List[RunVerdict]):
        import uuid
        self.verdicts[job_id] = verdicts
        if self.verdicts._sb and verdicts:
            try:
                rows = [
                    {
                        "id": v.id or f"verd-{uuid.uuid4().hex[:8]}",
                        "evaluation_run_id": job_id,
                        "scenario_id": v.scenario_id,
                        "status": v.status or "completed",
                        "evidence": v.model_dump() if hasattr(v, "model_dump") else v.dict()
                    }
                    for v in verdicts
                ]
                self.verdicts._sb.table("evaluation_verdicts").upsert(rows).execute()
            except Exception as e:
                logger.debug(f"Supabase batch sync for evaluation_verdicts: {e}")

    def get_scorecard(self, eval_id: str) -> Optional[ReliabilityScorecard]:
        return self.scorecards.get(eval_id)

    def save_scorecard(self, scorecard: ReliabilityScorecard):
        self.scorecards[scorecard.evaluation_id] = scorecard

    def get_clusters(self, eval_id: str) -> List[FailureCluster]:
        return self.clusters.get(eval_id, [])

    def save_pipeline_run(self, run: PipelineRun):
        self.pipeline_runs[run.id] = run

    def get_pipeline_run(self, run_id: str) -> Optional[PipelineRun]:
        return self.pipeline_runs.get(run_id)

    def list_pipeline_runs(self) -> List[PipelineRun]:
        return list(self.pipeline_runs.values())

    def get_agent_test_spec(self, spec_id: str) -> Optional[AgentTestSpecification]:
        return self.agent_test_specs.get(spec_id)

    def save_agent_test_spec(self, spec: AgentTestSpecification):
        self.agent_test_specs[spec.id] = spec

    def list_agent_test_specs(self) -> List[AgentTestSpecification]:
        return list(self.agent_test_specs.values())

    def get_sandbox_spec(self, spec_id: str) -> Optional[SandboxSpecification]:
        return self.sandbox_specs.get(spec_id)

    def save_sandbox_spec(self, spec: SandboxSpecification):
        self.sandbox_specs[spec.id] = spec

    def list_sandbox_specs(self) -> List[SandboxSpecification]:
        return list(self.sandbox_specs.values())

    # --- Agent Dependencies ---
    def save_agent_dependency(self, dep: AgentDependency):
        self.agent_dependencies[dep.id] = dep

    def get_agent_dependencies(self, agent_id: str) -> List[AgentDependency]:
        return [d for d in self.agent_dependencies.values() if d.agent_id == agent_id]

    def list_agent_dependencies(self, agent_id: Optional[str] = None) -> List[AgentDependency]:
        if agent_id:
            return self.get_agent_dependencies(agent_id)
        return list(self.agent_dependencies.values())

    def list_platform_resources(self) -> List[PlatformResource]:
        return list(self.platform_resources.values())

    def save_dependency_binding(self, binding: DependencyBinding):
        self.dependency_bindings[binding.id] = binding

    def get_dependency_bindings(self, agent_id: str) -> List[DependencyBinding]:
        return [b for b in self.dependency_bindings.values() if b.agent_id == agent_id]

    def list_dependency_bindings(self, agent_id: Optional[str] = None) -> List[DependencyBinding]:
        if agent_id:
            return self.get_dependency_bindings(agent_id)
        return list(self.dependency_bindings.values())


    # --- Execution Jobs ---
    def save_execution_job(self, job: ExecutionJob):
        self.execution_jobs[job.id] = job

    def get_execution_job(self, job_id: str) -> Optional[ExecutionJob]:
        return self.execution_jobs.get(job_id)

    def list_execution_jobs(self) -> List[ExecutionJob]:
        return list(self.execution_jobs.values())
    # --- AI Generation Runs ---
    def save_ai_generation_run(self, run: AIGenerationRun):
        self.ai_generation_runs[run.id] = run

    def list_ai_generation_runs(self) -> List[AIGenerationRun]:
        return list(self.ai_generation_runs.values())

    # --- Kaggle-Style Execution Sessions & Trajectories ---
    def save_execution_session(self, session: ExecutionSession):
        self.execution_sessions[session.id] = session

    def get_execution_session(self, session_id: str) -> Optional[ExecutionSession]:
        return self.execution_sessions.get(session_id)

    def list_execution_sessions(self, execution_run_id: Optional[str] = None) -> List[ExecutionSession]:
        sessions = list(self.execution_sessions.values())
        if execution_run_id:
            sessions = [
                s for s in sessions
                if getattr(s, "execution_run_id", "") == execution_run_id
                or getattr(s, "evaluation_run_id", "") == execution_run_id
            ]
        return sorted(sessions, key=lambda x: getattr(x, "started_at", ""), reverse=True)

    def save_execution_run(self, run: ExecutionRun) -> None:
        self.execution_runs[run.id] = run

    def get_execution_run(self, run_id: str) -> Optional[ExecutionRun]:
        return self.execution_runs.get(run_id)

    def list_execution_runs(self, agent_id: Optional[str] = None) -> List[ExecutionRun]:
        runs = list(self.execution_runs.values())
        if agent_id:
            runs = [r for r in runs if getattr(r, "agent_id", None) == agent_id]
        return sorted(runs, key=lambda x: getattr(x, "started_at", ""), reverse=True)


    def save_execution_step(self, step: ExecutionStep):
        self.execution_steps[step.id] = step

    def get_execution_steps(self, session_id: str) -> List[ExecutionStep]:
        steps = [s for s in self.execution_steps.values() if s.execution_session_id == session_id]
        return sorted(steps, key=lambda x: x.step_number)

    def save_execution_metrics(self, metrics: ExecutionMetrics):
        self.execution_metrics[metrics.id] = metrics

    def get_execution_metrics(self, session_id: str) -> Optional[ExecutionMetrics]:
        for m in self.execution_metrics.values():
            if m.execution_session_id == session_id:
                return m
        return None

    def save_benchmark_record(self, record: BenchmarkRecord):
        self.benchmark_records[record.id] = record

    def list_benchmark_records(self) -> List[BenchmarkRecord]:
        return list(self.benchmark_records.values())

    # --- Agent Model Dependencies & Execution Bindings ---
    def save_agent_dependency_model(self, dep: Any):
        if hasattr(self, "_model_deps"):
            self._model_deps[dep.id] = dep
        else:
            self._model_deps = {dep.id: dep}

    def save_execution_model_binding(self, binding: Any):
        if not hasattr(self, "_bindings"):
            self._bindings = {}
        exec_id = getattr(binding, "execution_id", getattr(binding, "id", None)) or "default"
        self._bindings[exec_id] = binding

    def get_execution_model_binding(self, exec_id: str) -> Optional[Any]:
        if not hasattr(self, "_bindings"):
            self._bindings = {}
        return self._bindings.get(exec_id)

    def save_evaluation_report(self, report: Any):
        if not hasattr(self, "_reports"):
            self._reports = {}
        self._reports[report.evaluation_id] = report

    def get_evaluation_report(self, eval_id: str) -> Optional[Any]:
        if not hasattr(self, "_reports"):
            self._reports = {}
        return self._reports.get(eval_id)

    # --- Model Connections ---
    def save_model_connection(self, conn: ModelConnection) -> None:
        self.model_connections[conn.id] = conn

    def get_model_connection(self, conn_id: str) -> Optional[ModelConnection]:
        return self.model_connections.get(conn_id)

    def list_model_connections(self) -> List[ModelConnection]:
        return list(self.model_connections.values())

    def delete_model_connection(self, conn_id: str) -> None:
        if conn_id in self.model_connections:
            del self.model_connections[conn_id]

    # --- Training Datasets ---
    def save_training_dataset(self, dataset: TrainingDataset) -> None:
        self.training_datasets[dataset.id] = dataset

    def get_training_dataset(self, dataset_id: str) -> Optional[TrainingDataset]:
        return self.training_datasets.get(dataset_id)

    def list_training_datasets(self, agent_id: Optional[str] = None) -> List[TrainingDataset]:
        datasets = list(self.training_datasets.values())
        if agent_id:
            return [d for d in datasets if d.agent_id == agent_id]
        return datasets

    # --- Diagnosis Reports ---
    def save_diagnosis_report(self, report: AgentDiagnosisReport) -> None:
        self.diagnosis_reports[report.evaluation_run_id] = report

    def get_diagnosis_report(self, eval_run_id: str) -> Optional[AgentDiagnosisReport]:
        return self.diagnosis_reports.get(eval_run_id)

    # --- Training Jobs ---
    def save_training_job(self, job: TrainingJob) -> None:
        self.training_jobs[job.id] = job

    def get_training_job(self, job_id: str) -> Optional[TrainingJob]:
        return self.training_jobs.get(job_id)

    def list_training_jobs(self, agent_id: Optional[str] = None) -> List[TrainingJob]:
        jobs = list(self.training_jobs.values())
        if agent_id:
            return [j for j in jobs if j.agent_id == agent_id]
        return sorted(jobs, key=lambda x: x.created_at, reverse=True)

    # --- Model Versions ---
    def save_model_version(self, version: ModelVersionRecord) -> None:
        self.model_versions[version.id] = version

    def get_model_version(self, version_id: str) -> Optional[ModelVersionRecord]:
        return self.model_versions.get(version_id)

    def list_model_versions(self, agent_id: Optional[str] = None) -> List[ModelVersionRecord]:
        versions = list(self.model_versions.values())
        if agent_id:
            return [v for v in versions if getattr(v, "agent_id", None) == agent_id]
        return sorted(versions, key=lambda x: getattr(x, "created_at", ""), reverse=True)


    # --- Stage Judge Audits ---
    def save_stage_judge_audit(self, audit: Any) -> None:
        self.stage_judge_audits[audit.id] = audit

    def get_stage_judge_audit(self, audit_id: str) -> Optional[Any]:
        return self.stage_judge_audits.get(audit_id)

    def list_stage_judge_audits(self, agent_id: Optional[str] = None, stage: Optional[str] = None) -> List[Any]:
        audits = list(self.stage_judge_audits.values())
        if agent_id:
            audits = [a for a in audits if getattr(a, "agent_id", None) == agent_id]
        if stage:
            audits = [a for a in audits if getattr(a, "stage_name", "").lower() == stage.lower()]
        return sorted(audits, key=lambda x: getattr(x, "created_at", ""), reverse=True)

    # --- Multi-Agent Stage Audits ---
    def save_multi_agent_audit(self, audit: Any) -> None:
        self.multi_agent_stage_audits[audit.id] = audit

    def get_multi_agent_audit(self, audit_id: str) -> Optional[Any]:
        return self.multi_agent_stage_audits.get(audit_id)

    def list_multi_agent_audits(self, stage: Optional[str] = None) -> List[Any]:
        audits = list(self.multi_agent_stage_audits.values())
        if stage:
            audits = [a for a in audits if getattr(a, "stage_name", "").lower() == stage.lower()]
        return sorted(audits, key=lambda x: getattr(x, "created_at", ""), reverse=True)

    # --- Canonical Agent Versions ---
    def save_agent_version(self, version: AgentVersionRecord) -> None:
        self.agent_versions[version.id] = version

    def get_agent_version(self, version_id: str) -> Optional[AgentVersionRecord]:
        v = self.agent_versions.get(version_id)
        if v:
            agent = self.get_agent(v.agent_id)
            if agent:
                v.is_latest = (agent.current_version_id == v.id or agent.version_label == v.version_label)
        return v

    def list_agent_versions(self, agent_id: Optional[str] = None) -> List[AgentVersionRecord]:
        versions = list(self.agent_versions.values())
        if agent_id:
            versions = [v for v in versions if getattr(v, "agent_id", None) == agent_id]
            agent = self.get_agent(agent_id)
            if agent:
                for v in versions:
                    v.is_latest = (agent.current_version_id == v.id or agent.version_label == v.version_label)
        return sorted(versions, key=lambda x: getattr(x, "created_at", ""), reverse=True)


    def promote_agent_version(self, agent_id: str, version_id: str) -> Optional[AgentVersionRecord]:
        """Promotes a target agent version to 'latest' and updates the primary AgentRecord."""
        target_version = self.get_agent_version(version_id)
        if not target_version or target_version.agent_id != agent_id:
            return None

        # 1. Update all other versions of this agent to is_latest = False
        for v in self.list_agent_versions(agent_id):
            if v.id == version_id:
                v.is_latest = True
                target_version = v
            else:
                v.is_latest = False
            self.save_agent_version(v)

        # 2. Update primary AgentRecord with new source files and version label
        agent = self.get_agent(agent_id)
        if agent:
            agent.version_label = target_version.version_label
            agent.current_version_id = target_version.id
            if target_version.source_files:
                agent.source_files = target_version.source_files
            self.save_agent(agent)

        target_version.is_latest = True
        return target_version


    # --- Canonical Patches & Remediation ---
    def save_patch(self, patch: PatchArtifact) -> None:
        self.patch_artifacts[patch.id] = patch

    def get_patch(self, patch_id: str) -> Optional[PatchArtifact]:
        return self.patch_artifacts.get(patch_id)

    def list_patches(self, agent_id: Optional[str] = None) -> List[PatchArtifact]:
        patches = list(self.patch_artifacts.values())
        if agent_id:
            patches = [p for p in patches if getattr(p, "agent_id", None) == agent_id]
        return sorted(patches, key=lambda x: getattr(x, "created_at", ""), reverse=True)

    # --- Canonical Findings ---
    def save_finding(self, finding: Finding) -> None:
        self.findings[finding.id] = finding

    def get_finding(self, finding_id: str) -> Optional[Finding]:
        return self.findings.get(finding_id)

    def list_findings(self, eval_run_id: Optional[str] = None, agent_id: Optional[str] = None) -> List[Finding]:
        findings = list(self.findings.values())
        if eval_run_id:
            findings = [f for f in findings if getattr(f, "evaluation_run_id", None) == eval_run_id]
        if agent_id:
            findings = [f for f in findings if getattr(f, "agent_id", None) == agent_id]
        return sorted(findings, key=lambda x: getattr(x, "created_at", ""), reverse=True)

    # --- Canonical Test Cases ---
    def save_test_case(self, test_case: TestCaseSpecification) -> None:
        self.canonical_test_cases[test_case.id] = test_case

    def get_test_case(self, test_case_id: str) -> Optional[TestCaseSpecification]:
        return self.canonical_test_cases.get(test_case_id)

    def list_test_cases(self, agent_id: Optional[str] = None) -> List[TestCaseSpecification]:
        test_cases = list(self.canonical_test_cases.values())
        if agent_id:
            test_cases = [tc for tc in test_cases if getattr(tc, "agent_id", None) == agent_id]
        return sorted(test_cases, key=lambda x: getattr(x, "created_at", ""), reverse=True)

store = Store()



