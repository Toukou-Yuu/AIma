"""牌山切分：本墙与王牌。行为对照 mahjong_rules/Mahjong_Soul.md §5。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from kernel.tiles.model import Tile

# 总张数与切分长度（标准四麻 136）
WALL_SIZE = 136
LIVE_WALL_SIZE = 122
DEAD_WALL_SIZE = 14
# 王牌内：10 张岭上摸用 + 4 张指示牌底下牌
RINSHAN_COUNT = 10
INDICATOR_COUNT = 4

if LIVE_WALL_SIZE + DEAD_WALL_SIZE != WALL_SIZE:
    msg = "wall partition constants must sum to WALL_SIZE"
    raise RuntimeError(msg)
if RINSHAN_COUNT + INDICATOR_COUNT != DEAD_WALL_SIZE:
    msg = "dead wall segments must sum to DEAD_WALL_SIZE"
    raise RuntimeError(msg)


@dataclass(frozen=True, slots=True)
class DeadWall:
    """
    王牌区 14 张，顺序与 ``split_wall`` 切分约定一致。

    在 ``wall[122:136]`` 这段里：
    - 前 10 张：岭上摸牌储备（具体摸取顺序由后续杠相关逻辑衔接）。
    - 后 4 张：表宝指示牌所压住的牌位（翻开逻辑由后续配牌/宝牌模块衔接）。

    若日后采用不同实体摆放约定，应集中改本模块并同步测试。
    """

    rinshan: tuple[Tile, ...]
    indicators: tuple[Tile, ...]

    def __post_init__(self) -> None:
        if len(self.rinshan) != RINSHAN_COUNT:
            msg = f"rinshan must have {RINSHAN_COUNT} tiles"
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
    王牌区内部分块见 ``DeadWall`` 文档。
    """
    if len(wall) != WALL_SIZE:
        msg = f"wall must have length {WALL_SIZE}, got {len(wall)}"
        raise ValueError(msg)
    t = tuple(wall)
    live = t[:LIVE_WALL_SIZE]
    dead_block = t[LIVE_WALL_SIZE:]
    rinshan = dead_block[:RINSHAN_COUNT]
    indicators = dead_block[RINSHAN_COUNT:]
    return WallSplit(live=live, dead=DeadWall(rinshan=rinshan, indicators=indicators))
