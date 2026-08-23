import pytest
from app.models.agent import AgentRecord, AgentConstitution, DependencyDefinition
from app.models.scenario import ScenarioPlan, ScenarioPlanItem, ScenarioCategory
from app.core.scenarios.scenario_generator import generate_scenarios_deterministically


def test_generate_scenarios_deterministically():
    agent = AgentRecord(
        id="agent-test-123",
        name="test-summarizer",
        description="Demo summarizer agent",
        domain="media",
        constitution=AgentConstitution(
            goals=["Fetch topic", "Summarize briefing"],
            never_rules=["Never violate safety policy"],
            always_rules=[]
        ),
        dependencies=[
            DependencyDefinition(id="dep-openai", name="OPENAI_API_KEY", type="credential", required=True, detected_from="AST_IMPORT"),
            DependencyDefinition(id="dep-newsapi", name="NEWS_API_KEY", type="credential", required=False, detected_from="AST_IMPORT")
        ],
        created_at="2026-08-23T00:00:00Z"
    )

    plan = ScenarioPlan(
        plan_id="plan-123",
        agent_id=agent.id,
        agent_name=agent.name,
        total_target=8,
        plan_items=[
            ScenarioPlanItem(
                plan_id="item-1",
                target_type="category",
                category=ScenarioCategory.NORMAL,
                target="Normal flow check"
            )
        ]
    )

    scenarios = generate_scenarios_deterministically(agent, plan)
    
    assert len(scenarios) == 8
    
    categories = [sc.category for sc in scenarios]
    assert ScenarioCategory.NORMAL in categories
    assert ScenarioCategory.EDGE in categories
    assert ScenarioCategory.RECOVERY in categories
    assert ScenarioCategory.ADVERSARIAL in categories
    assert ScenarioCategory.SECURITY in categories
    assert ScenarioCategory.STRESS in categories
    assert ScenarioCategory.CHAOS in categories

    for sc in scenarios:
        assert sc.id.startswith("SC-")
        assert sc.agent_id == agent.id
        assert sc.fingerprint is not None
        assert len(sc.assertions) > 0
        if sc.category == ScenarioCategory.RECOVERY:
            assert len(sc.fault_injections) == 1
            assert sc.fault_injections[0].target_tool == "env"
