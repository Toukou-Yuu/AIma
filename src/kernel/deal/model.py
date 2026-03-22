"""配牌后的牌桌子状态（手牌、剩余本墙、王牌、表宝指示牌）。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from kernel.play.model import RiverEntry, TurnPhase
from kernel.tiles.model import Tile
from kernel.wall.split import LIVE_WALL_SIZE, DeadWall

# 开局从本墙取牌张数：三轮 16×3 + 一轮 4 + 亲多 1
INITIAL_DEAL_TILES = 53
# 配牌后本墙剩余：122 - 53
LIVE_WALL_AFTER_DEAL = LIVE_WALL_SIZE - INITIAL_DEAL_TILES

# 表宝指示牌：与 ``DeadWall.indicators`` 顺序一致，先翻开第 1 张（下标 0）
FIRST_DORA_INDICATOR_INDEX = 0


@dataclass(frozen=True, slots=True)
class BoardState:
    """
    一局进行中与牌山相关的快照。

    ``live_wall`` 为配牌后剩余本墙；``live_draw_index`` 指向下一张要摸的牌。
    ``current_seat`` / ``turn_phase`` 描述摸打主循环；``river`` 为舍牌顺序。
    """

    hands: tuple[Counter[Tile], Counter[Tile], Counter[Tile], Counter[Tile]]
    live_wall: tuple[Tile, ...]
    live_draw_index: int
    dead_wall: DeadWall
    revealed_indicators: tuple[Tile, ...]
    current_seat: int
    turn_phase: TurnPhase
    river: tuple[RiverEntry, ...]
    last_draw_tile: Tile | None = None
    """当前行动家上一张自摸（用于判定摸切）；非自摸后打牌阶段可为 ``None``。"""

    def __post_init__(self) -> None:
        validate_board_state(self)


def validate_board_state(board: BoardState) -> None:
    """校验张数守恒、本墙游标与无副露时的 13/14 轮次一致。"""
    if not 0 <= board.current_seat <= 3:
        msg = "current_seat must be 0..3"
        raise ValueError(msg)
    if len(board.live_wall) != LIVE_WALL_AFTER_DEAL:
        msg = f"live_wall must have length {LIVE_WALL_AFTER_DEAL}"
        raise ValueError(msg)
    if not 0 <= board.live_draw_index <= len(board.live_wall):
        msg = "live_draw_index out of range for live_wall"
        raise ValueError(msg)
    if len(board.revealed_indicators) < 1:
        msg = "revealed_indicators must be non-empty"
        raise ValueError(msg)

    in_hand = sum(sum(h.values()) for h in board.hands)
    river_n = len(board.river)
    live_remaining = len(board.live_wall) - board.live_draw_index
    dead_n = len(board.dead_wall.rinshan) + len(board.dead_wall.indicators)
    if in_hand + river_n + live_remaining + dead_n != 136:
        msg = "tile count conservation violated (expected 136 total)"
        raise ValueError(msg)

    counts = [sum(board.hands[s].values()) for s in range(4)]
    cur = board.current_seat
    if board.turn_phase == TurnPhase.NEED_DRAW:
        if any(c != 13 for c in counts):
            msg = "in NEED_DRAW all seats must have 13 concealed tiles (no melds in K6)"
            raise ValueError(msg)
        if board.last_draw_tile is not None:
            msg = "last_draw_tile must be None in NEED_DRAW"
            raise ValueError(msg)
    elif board.turn_phase == TurnPhase.MUST_DISCARD:
        for s in range(4):
            want = 14 if s == cur else 13
            if counts[s] != want:
                msg = f"in MUST_DISCARD seat {s} must have {want} tiles"
                raise ValueError(msg)
    else:
        msg = f"unknown turn phase: {board.turn_phase!r}"
        raise ValueError(msg)
