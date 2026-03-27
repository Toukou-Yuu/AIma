"""和了形判定（标准四面子一雀头）；七对子见 ``kernel.call.win``。"""

from kernel.win_shape.decompose import (
    enumerate_menzen_decompositions_vec34,
    menzen_peikou_level,
    menzen_peikou_level_vec34,
)
from kernel.win_shape.std import (
    can_win_standard_form,
    can_win_standard_form_concealed_total,
    concealed_to_vec34,
    tile_to_index,
)

__all__ = [
    "can_win_standard_form",
    "can_win_standard_form_concealed_total",
    "concealed_to_vec34",
    "enumerate_menzen_decompositions_vec34",
    "menzen_peikou_level",
    "menzen_peikou_level_vec34",
    "tile_to_index",
]
