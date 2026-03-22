"""局内行牌相关类型（轮次阶段、河牌记录）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kernel.tiles.model import Tile


class TurnPhase(Enum):
    """当前行动家子阶段：须摸牌 / 须打牌。"""

    NEED_DRAW = "need_draw"
    """须从本墙摸一张（持 13 张）。"""
    MUST_DISCARD = "must_discard"
    """须打出一张（持 14 张）。"""


@dataclass(frozen=True, slots=True)
class RiverEntry:
    """河牌一条记录。``tsumogiri`` 为真表示摸打（刚摸进的同一张即打出）。"""

    seat: int
    tile: Tile
    tsumogiri: bool = False
