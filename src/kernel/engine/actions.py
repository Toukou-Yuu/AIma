"""玩家/系统意图的最小动作集；K4 仅验收壳层，K5 起由真实事件替换/扩展。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kernel.tiles.model import Tile


class ActionKind(Enum):
    """动作种类。"""

    NOOP = "noop"
    """恒等探针；仅在 ``IN_ROUND`` 合法。"""
    BEGIN_ROUND = "begin_round"
    """配牌前 → 局中：须提供完整 136 张牌山并完成配牌与首张表宝指示牌。"""
    DRAW = "draw"
    """自摸：须在 ``IN_ROUND`` 且当前为 ``NEED_DRAW``；``seat`` 可省略（视为 ``current_seat``）。"""
    DISCARD = "discard"
    """打牌：须在 ``MUST_DISCARD``；须指定 ``seat``（须为 ``current_seat``）与 ``tile``。"""


@dataclass(frozen=True, slots=True)
class Action:
    """一次 ``apply`` 的输入。"""

    kind: ActionKind
    """动作类型。"""
    seat: int | None = None
    """执行者座位 ``0..3``；未使用时可省略。若给出则必须合法。"""
    wall: tuple[Tile, ...] | None = None
    """``BEGIN_ROUND`` 时必填：长度 136 的标准牌山（须与 ``build_deck`` 多重集合一致）。"""
    tile: Tile | None = None
    """``DISCARD`` 时必填：要打出的牌。"""
