"""
Execution Trace Normalizer.
Transforms raw ExecutionTrace objects into standardized, normalized evidence packets
without mutating raw execution evidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.execution import ExecutionTrace, TraceEvent, ToolCallRecord


class NormalizedEvent(BaseModel):
    event_index: int
    timestamp: str
    event_type: str  # "PROCESS", "STDOUT", "STDERR", "TOOL_CALL", "FUNCTION_CALL", "WORKFLOW", "LLM_CALL", "HTTP_REQUEST", "EXCEPTION"
    source: str      # "system", "sandbox", "agent", "tool", "preflight"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedTracePacket(BaseModel):
    trace_id: str
    agent_id: str
    agent_version: str
    scenario_id: str
    execution_status: str  # "BLOCKED", "FAILED", "TIMEOUT", "COMPLETED"
    process_started: bool = False
    process_pid: Optional[int] = None
    exit_code: Optional[int] = None
    stdout_full: str = ""
    stderr_full: str = ""
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    function_calls: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_events: List[Dict[str, Any]] = Field(default_factory=list)
    llm_calls: List[Dict[str, Any]] = Field(default_factory=list)
    http_requests: List[Dict[str, Any]] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    normalized_events: List[NormalizedEvent] = Field(default_factory=list)


def normalize_execution_trace(trace: ExecutionTrace) -> NormalizedTracePacket:
    """Normalizes raw execution traces into a standardized evidence packet."""
    stdout_chunks = []
    stderr_chunks = []
    normalized_events: List[NormalizedEvent] = []
    tool_calls: List[Dict[str, Any]] = []
    workflow_events: List[Dict[str, Any]] = []
    exceptions: List[str] = []
    process_started = False
    exit_code = None

    for idx, event in enumerate(trace.events or []):
        content = event.content or ""
        role = (event.role or "system").lower()
        ev_type = "EVENT"

        if "PROCESS_STARTED" in content:
            process_started = True
            ev_type = "PROCESS"
        elif "PROCESS_EXITED" in content:
            ev_type = "PROCESS"
            if "Exit code " in content:
                try:
                    exit_code = int(content.split("Exit code ")[1].strip())
                except ValueError:
                    pass
        elif "STDOUT_CHUNK:" in content:
            ev_type = "STDOUT"
            chunk = content.replace("STDOUT_CHUNK:", "").strip()
            stdout_chunks.append(chunk)
        elif "STDERR_CHUNK:" in content:
            ev_type = "STDERR"
            chunk = content.replace("STDERR_CHUNK:", "").strip()
            stderr_chunks.append(chunk)
            if "Traceback" in chunk or "Exception" in chunk:
                exceptions.append(chunk)
        elif role == "tool_call":
            ev_type = "TOOL_CALL"
        elif role == "preflight":
            ev_type = "PREFLIGHT"

        normalized_events.append(NormalizedEvent(
            event_index=idx + 1,
            timestamp=event.timestamp or "",
            event_type=ev_type,
            source=role,
            content=content,
            metadata={"tool_call": event.tool_call.dict() if hasattr(event.tool_call, "dict") and event.tool_call else None}
        ))

    for tc in trace.tool_calls or []:
        tool_calls.append(tc.dict() if hasattr(tc, "dict") else dict(tc))

    stdout_full = "\n".join(stdout_chunks)
    stderr_full = "\n".join(stderr_chunks)

    return NormalizedTracePacket(
        trace_id=trace.id,
        agent_id=trace.agent_id,
        agent_version=trace.agent_version or "v1.0",
        scenario_id=trace.scenario_id,
        execution_status=trace.status,
        process_started=process_started or (trace.status == "COMPLETED"),
        exit_code=exit_code if exit_code is not None else (0 if trace.status == "COMPLETED" else None),
        stdout_full=stdout_full,
        stderr_full=stderr_full,
        tool_calls=tool_calls,
        workflow_events=workflow_events,
        exceptions=exceptions,
        total_latency_ms=trace.total_latency_ms,
        normalized_events=normalized_events
    )
