"""局内行牌相关类型（轮次阶段、河牌记录）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from kernel.tiles.model import Tile


class TurnPhase(Enum):
    """当前行动家子阶段：须摸牌 / 须打牌 / 舍牌应答。"""

    NEED_DRAW = "need_draw"
    """须从本墙摸一张（持 13 张）。"""
    MUST_DISCARD = "must_discard"
    """须打出一张（持 14 张）。"""
    CALL_RESPONSE = "call_response"
    """他家舍牌后的鸣牌/荣和应答窗口（详见 ``CallResolution``）。"""


@dataclass(frozen=True, slots=True)
class RiverEntry:
    """河牌一条记录。``tsumogiri`` 为真表示摸打；``riichi`` 为真表示该打同时宣告立直。"""

    seat: int
    tile: Tile
    tsumogiri: bool = False
    riichi: bool = False


CallStage = Literal["ron", "pon_kan", "chi"]


@dataclass(frozen=True, slots=True)
class CallResolution:
    """
    舍牌应答状态机快照。

    阶段顺序：荣和收集（三家任意顺序表态）→ 碰/大明杠（下家起逆时针依次）→ 上家是否吃。
    """

    discard_seat: int
    claimed_tile: Tile
    river_index: int
    stage: CallStage
    ron_remaining: frozenset[int]
    """尚未对荣和机会表态（荣和或 pass）的座位。"""
    ron_claimants: frozenset[int]
    """已宣告荣和的座位（须通过和了形校验）。"""
    pon_kan_order: tuple[int, int, int]
    """碰/杠询问顺序：``(discard+1, discard+2, discard+3) % 4``。"""
    pon_kan_idx: int
    """当前轮到 ``pon_kan_order[idx]`` 答复碰/杠/pass；仅在 ``stage==pon_kan`` 使用。"""
    finished: bool = False
    """荣和阶段已结束且至少一家荣和；由引擎转入 ``HAND_OVER``。"""
    ron_passed_seats: frozenset[int] = field(default_factory=frozenset)
    """本巡荣和阶段已对当前 ``claimed_tile`` 选择 pass 的席（同巡振听门禁）。"""
    chankan_rinshan_pending: bool = False
    """加杠后抢杠窗口：荣和阶段结束且无人荣和时须接 ``apply_after_kan_rinshan_draw``（非碰吃）。"""

    @staticmethod
    def initial_after_discard(discard_seat: int, river_index: int, tile: Tile) -> CallResolution:
        o1 = (discard_seat + 1) % 4
        o2 = (discard_seat + 2) % 4
        o3 = (discard_seat + 3) % 4
        return CallResolution(
            discard_seat=discard_seat,
            claimed_tile=tile,
            river_index=river_index,
            stage="ron",
            ron_remaining=frozenset((o1, o2, o3)),
            ron_claimants=frozenset(),
            pon_kan_order=(o1, o2, o3),
            pon_kan_idx=0,
            finished=False,
        )

    @staticmethod
    def initial_chankan(kan_seat: int, added_tile: Tile) -> CallResolution:
        """加杠抢杠：``claimed_tile`` 为从手牌补入明刻的那一张；
        ``river_index=-1`` 表示非河底舍牌。"""
        o1 = (kan_seat + 1) % 4
        o2 = (kan_seat + 2) % 4
        o3 = (kan_seat + 3) % 4
        return CallResolution(
            discard_seat=kan_seat,
            claimed_tile=added_tile,
            river_index=-1,
            stage="ron",
            ron_remaining=frozenset((o1, o2, o3)),
            ron_claimants=frozenset(),
            pon_kan_order=(o1, o2, o3),
            pon_kan_idx=0,
            finished=False,
            chankan_rinshan_pending=True,
        )


def kamicha_seat(discard_seat: int) -> int:
    """切牌者的上家（可吃的一家）：``(discard_seat + 3) % 4``。"""
    return (discard_seat + 3) % 4
