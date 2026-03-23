"""荣和振听：舍牌/立直振听由河判定；同巡振听在 ``CallResolution.ron_passed_seats`` 由鸣牌层处理。"""

from __future__ import annotations

from kernel.deal.model import BoardState
from kernel.tiles.model import Tile


def is_furiten_for_tile(board: BoardState, seat: int, win_tile: Tile) -> bool:
    """
    若和了牌与自家河中含同值牌，则不可荣和（舍牌振听与立直振听在此子集下同一判定）。
    同巡振听见 ``kernel.call.transitions.apply_ron``（本巡对该舍牌荣和阶段已 pass 的席不可再荣和）。
    """
    for e in board.river:
        if e.seat == seat and e.tile == win_tile:
            return True
    return False
