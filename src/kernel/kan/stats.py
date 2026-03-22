"""与开杠相关的可观测计数；完整流局语义见 K11。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


def completed_kan_rinshan_count(board: BoardState) -> int:
    """
    已完成「开杠并自岭上摸入」的次数，等于 ``BoardState.rinshan_draw_index``。

    大明杠 / 暗杠 / 加杠均经同一条岭摸链推进该游标；与桌上杠组数无简单一一对应。
    **四杠流局**（K11）若按杠宣言次数计，可用本值作钩子。
    """

    return board.rinshan_draw_index
