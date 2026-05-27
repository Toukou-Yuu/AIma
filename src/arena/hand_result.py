"""HandResult: 单局结果记录。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandResult:
    """单局结果。

    用于在局结束时传递给 EventSink.on_hand_end。

    Attributes:
        match_id: 对局唯一标识符
        hand_index: 已完成的局号（0-indexed）
        hand_count: 已完成局数（含当前局）
        end_reason: 局结束原因（flow/ron/tsumo）
        scores: 当前分数（四家）
        winner_seat: 赢家座位（如果是ron/tsumo），否则为None
        loser_seat: 输家座位（如果是ron），否则为None
        points: 得分（如果是ron/tsumo），否则为0
    """

    match_id: str
    hand_index: int
    hand_count: int
    end_reason: str = "flow"
    scores: tuple[int, int, int, int] = (25000, 25000, 25000, 25000)
    winner_seat: int | None = None
    loser_seat: int | None = None
    points: int = 0