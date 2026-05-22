"""荣和振听：舍牌/立直振听由河判定；同巡振听在 ``CallResolution.ron_passed_seats`` 由鸣牌层处理。"""

from __future__ import annotations

from kernel.board import BoardState
from kernel.riichi.tenpai import compute_waiting_tiles
from kernel.tiles.model import Tile
from kernel.tiles.key import tile_key  # H-15: 赤五归一化


def is_furiten_for_tile(board: BoardState, seat: int, win_tile: Tile) -> bool:
    """
    若和了牌与自家河中含同值牌，则不可荣和（舍牌振听，赤五归一化）。
    立直后：听牌集合中任意一张在河中 → 对所有听牌振听。
    P2-01: 同巡振听和立直见逃振听检查。
    同巡振听见 ``kernel.call.transitions.apply_ron``（本巡对该舍牌荣和阶段已 pass 的席不可再荣和）。
    """
    # P2-01: 检查临时振听和立直振听
    if seat in board.temporary_furiten:
        return True
    if seat in board.riichi_furiten:
        return True

    win_key = tile_key(win_tile)  # H-15: 使用逻辑牌种
    # 舍牌振听：win_tile 在河中（逻辑牌种比较）
    for e in board.river:
        if e.seat == seat and tile_key(e.tile) == win_key:
            return True
    # 立直振听：听牌集合中任意一张在河中（逻辑牌种比较）
    if board.riichi[seat]:
        waiting = compute_waiting_tiles(board.hands[seat], board.melds[seat])
        waiting_keys = frozenset(tile_key(t) for t in waiting)
        river_keys = frozenset(tile_key(e.tile) for e in board.river if e.seat == seat)
        if waiting_keys & river_keys:
            return True
    return False
