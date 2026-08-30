from types import SimpleNamespace

from app.core.dependencies.dependency_resolver import DependencyResolver


def test_resolve_mode_flags_unimportable_runtime_package_as_blocked(monkeypatch):
    agent = SimpleNamespace(
        id="agent-runtime-check",
        name="research-agent",
        dependencies=[
            SimpleNamespace(name="langchain-openai", type="package", required=True, detected_from="requirements.txt")
        ],
        runtime_manifest={"agent_category": "LLM_POWERED"},
        tools=[],
    )

    monkeypatch.setattr(DependencyResolver, "_package_is_importable", lambda _pkg: False)

    result = DependencyResolver.resolve_mode(agent)

    assert result.execution_dependency_binding.all_fulfilled is False
    assert "importable" in result.execution_dependency_binding.reason.lower()
