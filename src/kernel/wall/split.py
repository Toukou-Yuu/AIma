"""牌山切分：本墙与王牌。行为对照 mahjong_rules/Mahjong_Soul.md §5。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from kernel.tiles.model import Tile

# 总张数与切分长度（标准四麻 136）
WALL_SIZE = 136
LIVE_WALL_SIZE = 122
DEAD_WALL_SIZE = 14
# 王牌内：6 张岭上摸用 + 4 槽「里指示 + 表指示」各 1 枚（共 8 张，与 7 对叠中指示区两枚叠一致）
RINSHAN_COUNT = 6
INDICATOR_COUNT = 4
"""表宝指示牌槽位数（与已翻开枚数上限、``revealed_indicators`` 长度一致）。"""
DEAD_INDICATOR_STOCK = INDICATOR_COUNT * 2
"""王牌区内固定不用于岭摸的指示叠张数（里侧 + 表侧各 4）。"""

if LIVE_WALL_SIZE + DEAD_WALL_SIZE != WALL_SIZE:
    msg = "wall partition constants must sum to WALL_SIZE"
    raise RuntimeError(msg)
if RINSHAN_COUNT + DEAD_INDICATOR_STOCK != DEAD_WALL_SIZE:
    msg = "dead wall segments must sum to DEAD_WALL_SIZE"
    raise RuntimeError(msg)


@dataclass(frozen=True, slots=True)
class DeadWall:
    """
    王牌区 14 张，顺序与 ``split_wall`` 切分约定一致。

    在 ``wall[122:136]`` 这段里：
    - 前 6 张：岭上摸牌储备（``rinshan[0..5]``）。
    - 后 8 张：4 槽叠置，每槽 ``(ura_bases[i], indicators[i])`` —— 先里侧、后表侧；
      开局与开杠翻开的是 ``indicators[i]``；**立直和了**结算时用同下标的 ``ura_bases[i]`` 作里宝指示牌。
    """

    rinshan: tuple[Tile, ...]
    ura_bases: tuple[Tile, ...]
    indicators: tuple[Tile, ...]

    def __post_init__(self) -> None:
        if len(self.rinshan) != RINSHAN_COUNT:
            msg = f"rinshan must have {RINSHAN_COUNT} tiles"
            raise ValueError(msg)
        if len(self.ura_bases) != INDICATOR_COUNT:
            msg = f"ura_bases must have {INDICATOR_COUNT} tiles"
            raise ValueError(msg)
        if len(self.indicators) != INDICATOR_COUNT:
            msg = f"indicators must have {INDICATOR_COUNT} tiles"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class WallSplit:
    """136 张牌 = 本墙（可摸） + 王牌区（结构化）。"""

    live: tuple[Tile, ...]
    dead: DeadWall

    def __post_init__(self) -> None:
        if len(self.live) != LIVE_WALL_SIZE:
            msg = f"live wall must have {LIVE_WALL_SIZE} tiles"
            raise ValueError(msg)


def split_wall(wall: Sequence[Tile]) -> WallSplit:
    """
    将长度为 136 的牌山切成「本墙 + 王牌」。

    下标约定：``wall[0]`` 为本墙第一张被摸的牌；``wall[122:136]`` 为王牌区；
    王牌区内：``[122:128]`` 岭上，``[128:136]`` 为 4 组 ``(里指示, 表指示)`` 交错排列。
    """
    if len(wall) != WALL_SIZE:
        msg = f"wall must have length {WALL_SIZE}, got {len(wall)}"
        raise ValueError(msg)
    t = tuple(wall)
    live = t[:LIVE_WALL_SIZE]
    dead_block = t[LIVE_WALL_SIZE:]
    rinshan = dead_block[:RINSHAN_COUNT]
    pair_block = dead_block[RINSHAN_COUNT:]
    ura_bases = tuple(pair_block[2 * i] for i in range(INDICATOR_COUNT))
    indicators = tuple(pair_block[2 * i + 1] for i in range(INDICATOR_COUNT))
    return WallSplit(
        live=live,
        dead=DeadWall(rinshan=rinshan, ura_bases=ura_bases, indicators=indicators),
    )
