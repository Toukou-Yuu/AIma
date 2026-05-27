"""MemorySink: EventSink implementation for memory lifecycle management."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.hand_result import HandResult
    from arena.match_result import MatchResult
    from arena.policy import DecisionContext, PolicyDecision
    from arena.result import EngineStepResult

from memory.manager import MemoryManager


class MemorySink:
    """EventSink that manages memory lifecycle.

    Calls MemoryManager.on_hand_end and on_match_end at appropriate times.
    """

    def __init__(
        self,
        manager: MemoryManager,
    ) -> None:
        """Initialize MemorySink.

        Args:
            manager: MemoryManager instance to wrap.
        """
        self._manager = manager

    def on_step(
        self,
        ctx: DecisionContext,
        decision: PolicyDecision,
        result: EngineStepResult,
    ) -> None:
        """Called on each step. No-op for MemorySink.

        Args:
            ctx: Decision context.
            decision: Policy decision result.
            result: Engine step result.
        """
        # MemorySink does not track per-step data
        pass

    def on_hand_end(
        self,
        hand_index: int,
        result: HandResult,
    ) -> None:
        """Called when a hand ends.

        Calls MemoryManager.on_hand_end for all 4 seats.

        Args:
            hand_index: Hand index (0-indexed).
            result: Hand result.
        """
        for seat in range(4):
            player_id = MemoryManager.player_id_for_seat(seat)
            self._manager.on_hand_end(player_id, hand_summary=None)

    def on_match_end(self, result: MatchResult) -> None:
        """Called when match ends.

        Calls MemoryManager.on_match_end for all 4 seats.

        Args:
            result: Complete match result.
        """
        for seat in range(4):
            player_id = MemoryManager.player_id_for_seat(seat)
            self._manager.on_match_end(player_id, match_summary=None)