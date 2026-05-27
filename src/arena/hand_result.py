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
    """

    match_id: str
    hand_index: int
    hand_count: int