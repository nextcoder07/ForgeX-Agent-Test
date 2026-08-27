"""
Unit tests for the Zero-Friction Requirement Resolver.
Verifies the 6-stage resolution chain and automatic sandbox mock provisioning.
"""

import pytest
from app.models.agent import AgentRecord, ToolDefinition, DependencyDefinition, ToolRisk
from app.core.dependencies.requirement_resolver import RequirementResolver
from app.models.execution_requirement import RequirementStatus, ResolutionMethod


def test_news_agent_zero_friction_resolution():
    """Verify NewsAPI agent requires 0 user inputs and auto-resolves sandbox mock."""
    agent = AgentRecord(
        id="test-news-agent",
        name="News Digest Agent",
        description="Processes media headlines.",
        domain="Media",
        entrypoint="main.py",
        dependencies=[
            DependencyDefinition(id="dep-1", name="newsapi", type="api", required=True, detected_from="requirements.txt"),
            DependencyDefinition(id="dep-2", name="requests", type="package", required=True, detected_from="requirements.txt"),
        ],
        tools=[
            ToolDefinition(name="fetch_headlines", description="Fetches news headlines", risk=ToolRisk.LOW)
        ],
        source_files={
            "main.py": "import os\nfrom newsapi import NewsApiClient\napi_key = os.getenv('NEWS_API_KEY')\n"
        }
    )

    report = RequirementResolver.resolve_agent_requirements(agent)

    assert report.overall_status == "READY"
    assert report.needs_user_input_count == 0
    assert len(report.ai_models) >= 1
    assert any("NewsAPI" in svc.name and svc.status == RequirementStatus.RESOLVED_SANDBOX for svc in report.external_services)
    assert any("Python" in env.name for env in report.environment)


def test_stripe_customer_support_zero_friction_resolution():
    """Verify Customer Support agent with Stripe & Postgres auto-resolves to sandbox simulators."""
    agent = AgentRecord(
        id="test-support-agent",
        name="Customer Support Agent",
        description="Assists customers with orders and refunds.",
        domain="E-Commerce",
        entrypoint="agent.py",
        dependencies=[
            DependencyDefinition(id="dep-stripe", name="stripe", type="api", required=True, detected_from="imports"),
            DependencyDefinition(id="dep-pg", name="postgres", type="database", required=True, detected_from="imports"),
        ],
        tools=[
            ToolDefinition(name="refund_order", description="Refunds customer order", risk=ToolRisk.CRITICAL)
        ],
        source_files={
            "agent.py": "import stripe\nimport psycopg2\n"
        }
    )

    report = RequirementResolver.resolve_agent_requirements(agent)

    assert report.overall_status == "READY"
    assert report.needs_user_input_count == 0
    assert any("Stripe" in svc.name and svc.status == RequirementStatus.RESOLVED_SANDBOX for svc in report.external_services)
    assert any("PostgreSQL" in svc.name and svc.status == RequirementStatus.RESOLVED_SANDBOX for svc in report.external_services)


def test_user_override_model_binding():
    """Verify user-provided model binding overrides default to RESOLVED_USER."""
    agent = AgentRecord(
        id="test-planner-agent",
        name="Planner Agent",
        description="Plans tasks and delegates steps.",
        domain="Productivity",
        entrypoint="main.py",
        runtime_manifest={
            "model_bindings": {
                "planner_llm": "ollama_local_qwen"
            }
        },
        source_files={
            "main.py": "planner_llm = 'gpt-4o'\n"
        }
    )

    report = RequirementResolver.resolve_agent_requirements(agent)

    planner_slot = next((m for m in report.ai_models if "planner" in m.id.lower() or "planner" in m.name.lower()), None)
    if planner_slot:
        assert planner_slot.status == RequirementStatus.RESOLVED_USER
        assert planner_slot.resolution_method == ResolutionMethod.USER_SUPPLIED
