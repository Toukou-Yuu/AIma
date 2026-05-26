"""Prompt DSL Renderer.

Section-based prompt renderer without if/for logic in templates.
"""

from __future__ import annotations

import logging
import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from models.backend import ChatMessage
from prompts.sections import estimate_tokens, get_renderer

if TYPE_CHECKING:
    from agents.runtime import PromptRuntime
    from arena.policy import DecisionContext
    from prompts.schema import PromptSpec, PromptSectionSpec


logger = logging.getLogger(__name__)


@dataclass
class SectionRenderResult:
    """Result of rendering a single section.

    Attributes:
        id: Section ID
        content: Rendered content (empty string if disabled or failed)
        enabled: Whether section was enabled
        token_estimate: Estimated token count
        skipped: Whether section was skipped (disabled, failed, or empty)
        skip_reason: Reason for skipping, if any
    """

    id: str
    content: str
    enabled: bool
    token_estimate: int
    skipped: bool
    skip_reason: str | None = None


@dataclass
class PromptRenderResult:
    """Result of rendering a full prompt.

    Attributes:
        messages: Rendered chat messages
        sections: Individual section results
        total_tokens: Total estimated token count
    """

    messages: tuple[ChatMessage, ...]
    sections: list[SectionRenderResult] = field(default_factory=list)
    total_tokens: int = 0


class PromptRenderer:
    """Section-based prompt renderer.

    Renders prompts from PromptSpec configurations. Each section is rendered
    independently and combined into the final message list.

    The renderer does not support if/for logic in templates - all conditional
    rendering is handled by section enabled flags and renderer functions.
    """

    def __init__(self, spec: "PromptSpec") -> None:
        """Initialize renderer with prompt specification.

        Args:
            spec: Prompt specification defining sections and their configuration
        """
        self.spec = spec
        self._section_cache: dict[str, str] = {}

    def render(
        self,
        ctx: "DecisionContext",
        runtime: "PromptRuntime | None" = None,
    ) -> PromptRenderResult:
        """Render prompt from decision context.

        Args:
            ctx: Decision context containing game state and legal actions
            runtime: Optional AgentPipeline runtime bundles

        Returns:
            PromptRenderResult with messages and section details
        """
        section_results: list[SectionRenderResult] = []
        system_content_parts: list[str] = []
        user_content_parts: list[str] = []

        for section_spec in self.spec.sections:
            result = self._render_section(ctx, section_spec, runtime=runtime)
            section_results.append(result)

            if result.skipped or not result.content:
                continue

            # Determine role based on section id convention
            role = self._get_section_role(section_spec.id)

            if role == "system":
                system_content_parts.append(result.content)
            else:
                user_content_parts.append(result.content)

        # Build messages
        messages: list[ChatMessage] = []

        system_content = "\n\n".join(system_content_parts).strip()
        if system_content:
            messages.append(ChatMessage(role="system", content=system_content))

        user_content = "\n\n".join(user_content_parts).strip()
        if user_content:
            messages.append(ChatMessage(role="user", content=user_content))

        total_tokens = sum(r.token_estimate for r in section_results)

        return PromptRenderResult(
            messages=tuple(messages),
            sections=section_results,
            total_tokens=total_tokens,
        )

    def _render_section(
        self,
        ctx: "DecisionContext",
        spec: "PromptSectionSpec",
        *,
        runtime: "PromptRuntime | None" = None,
    ) -> SectionRenderResult:
        """Render a single section.

        Args:
            ctx: Decision context
            spec: Section specification

        Returns:
            SectionRenderResult with content and metadata
        """
        # Check if section is enabled
        if not spec.enabled:
            return SectionRenderResult(
                id=spec.id,
                content="",
                enabled=False,
                token_estimate=0,
                skipped=True,
                skip_reason="disabled",
            )

        # Get renderer
        renderer_name = spec.renderer or spec.id
        renderer = get_renderer(renderer_name)

        if renderer is None:
            logger.warning(f"Unknown renderer: {renderer_name}")
            return SectionRenderResult(
                id=spec.id,
                content="",
                enabled=True,
                token_estimate=0,
                skipped=True,
                skip_reason=f"unknown renderer: {renderer_name}",
            )

        # Render section
        try:
            content = self._call_renderer(renderer, ctx, spec, runtime)
        except Exception:
            logger.exception(f"Error rendering section {spec.id}")
            return SectionRenderResult(
                id=spec.id,
                content="",
                enabled=True,
                token_estimate=0,
                skipped=True,
                skip_reason="render error",
            )

        # Check max_tokens constraint
        if spec.max_tokens is not None and content:
            token_estimate = estimate_tokens(content)
            if token_estimate > spec.max_tokens:
                # Truncate content to fit max_tokens
                # Simple approach: truncate by character count
                max_chars = spec.max_tokens * 4
                content = content[:max_chars]
                logger.debug(
                    f"Section {spec.id} truncated from {token_estimate} to "
                    f"~{spec.max_tokens} tokens"
                )

        token_estimate = estimate_tokens(content) if content else 0

        return SectionRenderResult(
            id=spec.id,
            content=content,
            enabled=True,
            token_estimate=token_estimate,
            skipped=not content,
            skip_reason=None if content else "empty content",
        )

    @staticmethod
    def _call_renderer(
        renderer: object,
        ctx: "DecisionContext",
        spec: "PromptSectionSpec",
        runtime: "PromptRuntime | None",
    ) -> str:
        """Call section renderers that use either the old or runtime signature."""
        try:
            signature = inspect.signature(renderer)
        except (TypeError, ValueError):
            return renderer(ctx, spec, runtime)  # type: ignore[misc]

        positional = [
            param
            for param in signature.parameters.values()
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        has_varargs = any(
            param.kind == inspect.Parameter.VAR_POSITIONAL
            for param in signature.parameters.values()
        )
        if has_varargs or len(positional) >= 3:
            return renderer(ctx, spec, runtime)  # type: ignore[misc]
        return renderer(ctx, spec)  # type: ignore[misc]

    @staticmethod
    def _get_section_role(section_id: str) -> str:
        """Determine message role for a section.

        Convention:
        - Sections with id starting with "system_" go to system message
        - All other sections go to user message

        Args:
            section_id: Section identifier

        Returns:
            Message role ("system" or "user")
        """
        if section_id.startswith("system_"):
            return "system"
        return "user"

    def render_messages(
        self,
        ctx: "DecisionContext",
        runtime: "PromptRuntime | None" = None,
    ) -> tuple[ChatMessage, ...]:
        """Render prompt and return just the messages.

        Convenience method for simple use cases.

        Args:
            ctx: Decision context

        Returns:
            Tuple of chat messages
        """
        result = self.render(ctx, runtime=runtime)
        return result.messages
