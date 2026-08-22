"""
Sandbox Specification Manager.
Constructs, configures, and persists SandboxSpecification objects for AI Agents.
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import Dict, Any, List
from app.models.agent import AgentRecord
from app.models.intake import SandboxSpecification
from app.services.store import store


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


def build_sandbox_specification_for_agent(agent: AgentRecord) -> SandboxSpecification:
    """Builds a complete, deterministic SandboxSpecification for an AgentRecord."""
    spec_id = f"sb-spec-{uuid.uuid4().hex[:8]}"

    runtime_config = {
        "language": "python",
        "version": "3.12",
        "cpu_limit": 1.0,
        "memory_limit_mb": 512,
        "execution_timeout_seconds": 15,
        "isolation_mode": "subprocess",  # "subprocess", "docker", "gvisor"
    }

    dependencies = [
        {"name": d.name, "type": d.type, "detected_from": d.detected_from}
        for d in agent.dependencies
    ]

    filesystem_config = {
        "read_only_root": True,
        "tmp_dir_mb": 64,
        "allowed_paths": ["/tmp", "/workspace"],
        "virtual_fs": {
            "order_db.json": '{"status": "active", "seeded": true}',
            "customer_records.json": '{"seeded": true}',
        }
    }

    network_config = {
        "allow_external_http": False,
        "allowed_domains": ["localhost", "127.0.0.1"],
        "intercept_outbound": True,
    }

    tools_config = [
        {
            "name": t.name,
            "description": t.description,
            "risk": t.risk.value if hasattr(t.risk, "value") else str(t.risk),
            "canonical_capability": t.canonical_capability,
            "is_destructive": t.is_destructive,
        }
        for t in agent.tools
    ]

    spec = SandboxSpecification(
        id=spec_id,
        agent_id=agent.id,
        runtime=runtime_config,
        dependencies=dependencies,
        filesystem=filesystem_config,
        network=network_config,
        tools=tools_config,
        credentials=[],
        created_at=_now()
    )

    store.save_sandbox_spec(spec)
    return spec


def get_or_create_sandbox_spec(agent: AgentRecord) -> SandboxSpecification:
    """Retrieves an existing SandboxSpecification for an agent, or builds a new one if missing."""
    existing_specs = store.list_sandbox_specs()
    for spec in existing_specs:
        if spec.agent_id == agent.id:
            return spec
    return build_sandbox_specification_for_agent(agent)
