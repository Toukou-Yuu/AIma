"""Context builder: combine filtering, compression, and token budget.

Main entry point for building context from events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from context.compression import CompressionEngine, CompressionMode
from context.event_projector import EventFilterConfig, EventProjector
from context.schema import ContextSpec
from context.token_budget import TokenBudgetConfig, TokenBudgetManager

if TYPE_CHECKING:
    from context.events import ContextEvent


@dataclass(frozen=True, slots=True)
class BuiltContext:
    """Result of context building."""

    text: str
    raw_event_count: int
    rendered_event_count: int
    snipped_event_count: int = 0
    collapsed_event_count: int = 0
    prompt_truncated: bool = False
    compression_mode: CompressionMode = "none"


class ContextBuilder:
    """Build context from events using spec configuration.

    Combines:
    - Event filtering (scope, type)
    - Compression
    - Token budget truncation
    """

    def __init__(
        self,
        spec: ContextSpec,
        token_budget: int = 0,
    ) -> None:
        """Initialize context builder.

        Args:
            spec: Context specification
            token_budget: Maximum tokens for context (0 = no limit)
        """
        self._spec = spec
        self._token_budget = token_budget

        # Create components
        self._filter_config = EventFilterConfig(
            scope=spec.scope,
            include_public_events=spec.include_public_events,
            include_scoreboard=spec.include_scoreboard,
            include_self_discards=spec.include_self_discards,
            include_opponent_discards=spec.include_opponent_discards,
            max_events=spec.max_events,
        )
        self._projector = EventProjector(self._filter_config)
        self._compression = CompressionEngine(
            mode=spec.compression,
            budget=spec.max_events or 0,
        )
        if token_budget > 0:
            self._budget_manager = TokenBudgetManager(
                TokenBudgetConfig(max_tokens=token_budget)
            )
        else:
            self._budget_manager = None

    @property
    def spec(self) -> ContextSpec:
        """Return the context specification."""
        return self._spec

    def build(
        self,
        events: list[ContextEvent],
        *,
        current_hand_index: int = 0,
        current_turn_index: int = 0,
        self_seat: int | None = None,
        detailed: bool = True,
    ) -> BuiltContext:
        """Build context from events.

        Args:
            events: List of context events
            current_hand_index: Current hand index (for per_hand scope)
            current_turn_index: Current turn index (for per_turn scope)
            self_seat: Player's seat for filtering
            detailed: Whether to include detailed information

        Returns:
            Built context with text and statistics
        """
        # Step 1: Filter events by scope and type
        filtered = self._projector.project(
            events,
            current_hand_index=current_hand_index,
            current_turn_index=current_turn_index,
            self_seat=self_seat,
        )

        # Step 2: Apply compression
        compression_result = self._compression.compress(filtered, detailed=detailed)

        # Step 3: Apply token budget truncation
        if self._budget_manager is not None:
            truncation_result = self._budget_manager.truncate(compression_result.text)
            return BuiltContext(
                text=truncation_result.text,
                raw_event_count=compression_result.raw_event_count,
                rendered_event_count=compression_result.rendered_event_count,
                snipped_event_count=compression_result.snipped_event_count,
                collapsed_event_count=compression_result.collapsed_event_count,
                prompt_truncated=truncation_result.prompt_truncated,
                compression_mode=compression_result.compression_mode,
            )

        return BuiltContext(
            text=compression_result.text,
            raw_event_count=compression_result.raw_event_count,
            rendered_event_count=compression_result.rendered_event_count,
            snipped_event_count=compression_result.snipped_event_count,
            collapsed_event_count=compression_result.collapsed_event_count,
            prompt_truncated=False,
            compression_mode=compression_result.compression_mode,
        )

    def build_empty(self) -> BuiltContext:
        """Build empty context for stateless mode."""
        return BuiltContext(
            text="",
            raw_event_count=0,
            rendered_event_count=0,
            prompt_truncated=False,
            compression_mode="none",
        )