"""流局类型枚举与流局结果结构。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class FlowKind(Enum):
    """流局种类。"""

    EXHAUSTED = "exhausted"
    """荒牌流局（牌山摸完）。"""
    NINE_NINE = "nine_nine"
    """九种九牌（配牌后幺九牌 + 字牌≥9 种）。"""
    FOUR_WINDS = "four_winds"
    """四风连打（开局 4 家连续打出相同风牌）。"""
    FOUR_KANS = "four_kans"
    """四杠散了（同一局 4 个杠完成）。"""
    FOUR_RIICHI = "four_riichi"
    """四家立直（4 家均宣言立直）。"""
    THREE_RON = "three_ron"
    """三家和（同张舍牌 3 家同时荣和）。"""


@dataclass(frozen=True, slots=True)
class FlowResult:
    """
    流局结果。

    ``kind``: 流局种类。
    ``kan_count``: 流局时已完成的杠数（四杠流局时用）。
    ``ron_claimants``: 三家和时的荣和者集合。
    """

    kind: FlowKind
    kan_count: int = 0
    ron_claimants: FrozenSet[int] = frozenset()


@dataclass(frozen=True, slots=True)
class TenpaiResult:
    """
    听牌结果。

    ``tenpai_seats``: 听牌者集合。
    ``tenpai_types``: 各家听牌类型（标准形/七对子等，暂留扩展）。
    """

    tenpai_seats: FrozenSet[int]
    tenpai_types: tuple[str, ...] = ()  # 预留：每家听牌类型
