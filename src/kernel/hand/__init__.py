"""门内手牌与副露（形状与张数守恒）；鸣牌可否、向听等由后续模块处理。"""

from kernel.hand.melds import Meld, MeldKind, meld_tile_count, triplet_key, validate_meld_shape
from kernel.hand.multiset import (
    add_tile,
    concealed_from_iterable,
    concealed_total,
    remove_tile,
    remove_tiles,
)
from kernel.hand.validate import (
    tiles_from_concealed_and_melds,
    validate_hand_package,
    validate_tile_conservation,
)

__all__ = [
    "Meld",
    "MeldKind",
    "add_tile",
    "concealed_from_iterable",
    "concealed_total",
    "meld_tile_count",
    "remove_tile",
    "remove_tiles",
    "tiles_from_concealed_and_melds",
    "triplet_key",
    "validate_hand_package",
    "validate_meld_shape",
    "validate_tile_conservation",
]
