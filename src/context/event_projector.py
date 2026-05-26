"""Event projector: filter events by scope and type.

Scope behavior:
- stateless: no history
- per_turn: last turn only
- per_hand: current hand events
- per_match: full match events
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from llm.agent.context_store import ContextEvent


# Event filter scope type
# "stateless" | "per_turn" | "per_hand" | "per_match"
EventScope = Literal["stateless", "per_turn", "per_hand", "per_match"]


@dataclass(frozen=True, slots=True)
class EventFilterConfig:
    """Configuration for event filtering."""

    scope: EventScope = "stateless"
    include_public_events: bool = True
    include_scoreboard: bool = True
    include_self_discards: bool = True
    include_opponent_discards: bool = True
    max_events: int | None = None


class EventProjector:
    """Project events based on scope and filter configuration."""

    def __init__(self, config: EventFilterConfig) -> None:
        self._config = config

    def project(
        self,
        events: list[ContextEvent],
        *,
        current_hand_index: int,
        current_turn_index: int,
        self_seat: int | None = None,
    ) -> list[ContextEvent]:
        """Filter events based on scope and configuration.

        Args:
            events: List of context events
            current_hand_index: Current hand index (for per_hand scope)
            current_turn_index: Current turn index within hand (for per_turn scope)
            self_seat: Player's seat for filtering self vs opponent actions

        Returns:
            Filtered list of events
        """
        # Scope filtering
        filtered = self._filter_by_scope(
            events,
            current_hand_index=current_hand_index,
            current_turn_index=current_turn_index,
        )

        # Type filtering
        if self_seat is not None:
            filtered = self._filter_by_type(filtered, self_seat)

        # Max events limit
        if self._config.max_events is not None and len(filtered) > self._config.max_events:
            filtered = filtered[-self._config.max_events :]

        return filtered

    def _filter_by_scope(
        self,
        events: list[ContextEvent],
        *,
        current_hand_index: int,
        current_turn_index: int,
    ) -> list[ContextEvent]:
        """Filter events by scope."""
        if self._config.scope == "stateless":
            return []

        if self._config.scope == "per_turn":
            # Last turn only within the current hand.
            if not events:
                return []
            return [
                ev for ev in events
                if getattr(ev, "hand_index", current_hand_index) == current_hand_index
                and ev.turn_index == current_turn_index
            ]

        if self._config.scope == "per_hand":
            return [
                ev for ev in events
                if getattr(ev, "hand_index", current_hand_index) == current_hand_index
            ]

        # per_match: full match events
        return events

    def _filter_by_type(
        self,
        events: list[ContextEvent],
        self_seat: int,
    ) -> list[ContextEvent]:
        """Filter events by type configuration."""
        # If all include flags are True, no filtering needed
        if (
            self._config.include_public_events
            and self._config.include_scoreboard
            and self._config.include_self_discards
            and self._config.include_opponent_discards
        ):
            return events

        # For now, return all events as we don't have event type info
        # in ContextEvent to distinguish public vs private events
        # This could be extended with event metadata in the future
        return events
