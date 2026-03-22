"""开局配牌与牌桌快照（手牌、剩余本墙、表宝指示牌）。"""

from kernel.deal.initial import assert_wall_is_standard_deck, build_board_after_split
from kernel.deal.model import (
    FIRST_DORA_INDICATOR_INDEX,
    INITIAL_DEAL_TILES,
    LIVE_WALL_AFTER_DEAL,
    BoardState,
    validate_board_state,
)

__all__ = [
    "BoardState",
    "FIRST_DORA_INDICATOR_INDEX",
    "INITIAL_DEAL_TILES",
    "LIVE_WALL_AFTER_DEAL",
    "assert_wall_is_standard_deck",
    "build_board_after_split",
    "validate_board_state",
]
