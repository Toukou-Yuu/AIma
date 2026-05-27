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
        # 生成可读的hand summary
        hand_summary = self._generate_hand_summary(hand_index, result)

        for seat in range(4):
            player_id = MemoryManager.player_id_for_seat(seat)
            self._manager.on_hand_end(player_id, hand_summary=hand_summary)

    def _generate_hand_summary(self, hand_index: int, result: HandResult) -> dict[str, str]:
        """生成可读的hand summary。

        Args:
            hand_index: Hand index (0-indexed).
            result: Hand result.

        Returns:
            包含summary文本的字典。
        """
        scores_str = "/".join(str(s) for s in result.scores)

        if result.end_reason == "flow":
            summary_text = f"Hand {hand_index} ended by flow. Scores: {scores_str}."
        elif result.end_reason == "ron":
            winner = result.winner_seat if result.winner_seat is not None else "?"
            loser = result.loser_seat if result.loser_seat is not None else "?"
            points_str = f", points={result.points}" if result.points > 0 else ""
            summary_text = (
                f"Hand {hand_index} ended by ron. "
                f"Winner seat={winner}, loser seat={loser}{points_str}. "
                f"Scores: {scores_str}."
            )
        else:
            summary_text = f"Hand {hand_index} ended by {result.end_reason}. Scores: {scores_str}."

        return {"text": summary_text, "hand_index": str(hand_index)}

    def on_match_end(self, result: MatchResult) -> None:
        """Called when match ends.

        Calls MemoryManager.on_match_end for all 4 seats.

        Args:
            result: Complete match result.
        """
        for seat in range(4):
            player_id = MemoryManager.player_id_for_seat(seat)
            self._manager.on_match_end(player_id, match_summary=None)