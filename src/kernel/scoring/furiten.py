"""荣和振听：舍牌/立直振听由河判定；同巡振听在 ``CallResolution.ron_passed_seats`` 由鸣牌层处理。"""

from __future__ import annotations

from kernel.board import BoardState
from kernel.riichi.tenpai import compute_waiting_tiles
from kernel.tiles.model import Tile


def is_furiten_for_tile(board: BoardState, seat: int, win_tile: Tile) -> bool:
    """
    若和了牌与自家河中含同值牌，则不可荣和（舍牌振听）。
    立直后：听牌集合中任意一张在河中 → 对所有听牌振听。
    同巡振听见 ``kernel.call.transitions.apply_ron``（本巡对该舍牌荣和阶段已 pass 的席不可再荣和）。
    """
    # 舍牌振听：win_tile 在河中
    for e in board.river:
        if e.seat == seat and e.tile == win_tile:
            return True
    # 立直振听：听牌集合中任意一张在河中
    if board.riichi[seat]:
        waiting = compute_waiting_tiles(board.hands[seat], board.melds[seat])
        river_tiles = frozenset(e.tile for e in board.river if e.seat == seat)
        if waiting & river_tiles:
            return True
    return False
