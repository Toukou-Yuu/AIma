"""Sink implementations for experiment event collection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from arena.match_result import MatchResult
    from arena.policy import DecisionContext, PolicyDecision
    from arena.result import EngineStepResult


class EventSink(Protocol):
    """Protocol for experiment event sinks.

    Event sinks receive events during match execution for logging,
    indexing, or other side effects.
    """

    def on_step(
        self,
        ctx: "DecisionContext",
        decision: "PolicyDecision",
        result: "EngineStepResult",
    ) -> None:
        """Called after each step decision.

        Args:
            ctx: Decision context.
            decision: Policy decision result.
            result: Engine step result.
        """
        ...

    def on_match_end(self, result: "MatchResult") -> None:
        """Called when match ends.

        Args:
            result: Complete match result.
        """
        ...


from experiments.sinks.artifact import ArtifactWriter
from experiments.sinks.index import IndexSink
from experiments.sinks.tee import TeeSink

__all__ = [
    "ArtifactWriter",
    "EventSink",
    "IndexSink",
    "TeeSink",
]