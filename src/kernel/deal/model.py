"""配牌后的牌桌子状态（手牌、剩余本墙、王牌、表宝指示牌）。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

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
    一局进行中与牌山相关的快照（K5：配牌与首张指示牌）。

    ``live_wall`` 为配牌后剩余本墙（通常 69 张）；``live_draw_index`` 指向下一张要摸的牌。
    """

    hands: tuple[Counter[Tile], Counter[Tile], Counter[Tile], Counter[Tile]]
    live_wall: tuple[Tile, ...]
    live_draw_index: int
    dead_wall: DeadWall
    revealed_indicators: tuple[Tile, ...]

    def __post_init__(self) -> None:
        validate_board_state(self)


def validate_board_state(board: BoardState) -> None:
    """校验手牌张数、本墙长度与指示牌非空。"""
    counts = sorted(sum(h.values()) for h in board.hands)
    if counts != [13, 13, 13, 14]:
        msg = "hands must be three 13-tile and one 14-tile concealed counts"
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
