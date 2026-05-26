"""Agent prompt configuration should be authoritative."""

from __future__ import annotations

from agents.components.factory import build_components
from agents.runtime import BuiltContext, BuiltObservation, MemoryReadResult, PromptRuntime
from agents.schema import AgentSpec
from context.schema import ContextSpec
from memory.schema import MemorySpec
from models.schema import ModelSpec
from prompts.renderer import PromptRenderer
from prompts.schema import PromptSectionSpec, PromptSpec


def _runtime() -> PromptRuntime:
    return PromptRuntime(
        decision=object(),
        observation=BuiltObservation(text="runtime observation"),
        context=BuiltContext(text="runtime public history"),
        memory=MemoryReadResult(rendered_text="runtime memory", layers=("hand",)),
    )


def test_build_components_does_not_force_disabled_runtime_sections() -> None:
    prompt = PromptSpec(
        template_id="custom",
        version="1.0",
        sections=[
            PromptSectionSpec(
                id="public_history",
                enabled=False,
                renderer="public_history",
                source="runtime",
            ),
            PromptSectionSpec(
                id="memory",
                enabled=False,
                renderer="memory",
                source="runtime",
            ),
        ],
    )
    agent = AgentSpec(
        context=ContextSpec(scope="per_match"),
        memory=MemorySpec(mode="passive", layers=["hand"]),
        prompt=prompt,
        model=ModelSpec(backend="dummy"),
    )

    components = build_components(agent, seed=1)
    messages = components.prompt.render(_runtime().decision, _runtime())

    assert messages == []


def test_section_runtime_content_requires_runtime_source() -> None:
    spec = PromptSpec(
        template_id="custom",
        version="1.0",
        sections=[
            PromptSectionSpec(
                id="memory",
                enabled=True,
                renderer="memory",
                source="static",
                options={"content": "static memory"},
            )
        ],
    )
    renderer = PromptRenderer(spec)

    result = renderer.render(_runtime().decision, runtime=_runtime())

    assert len(result.messages) == 1
    assert "static memory" in result.messages[0].content
    assert "runtime memory" not in result.messages[0].content
