"""完整局面根对象（K4 仅含阶段 + 场况；牌山/手牌等见后续）。"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.deal import BoardState
from kernel.engine.phase import GamePhase
from kernel.flow import FlowResult, TenpaiResult
from kernel.table import TableSnapshot, initial_table_snapshot


@dataclass(frozen=True, slots=True)
class GameState:
    """
    对局状态根节点。

    ``board`` 在 ``PRE_DEAL`` 为 ``None``；``BEGIN_ROUND`` 后为配牌结果（手牌、剩余本墙、王牌等）。
    """

    phase: GamePhase
    table: TableSnapshot
    board: BoardState | None = None
    ron_winners: frozenset[int] | None = None
    """``HAND_OVER`` 时和了席集合：荣和（一炮多响）或自摸（单席）；否则 ``None``。"""
    flow_result: FlowResult | None = None
    """``FLOWN`` 时流局结果；否则 ``None``。"""
    tenpai_result: TenpaiResult | None = None
    """``FLOWN`` 时听牌结果；否则 ``None``。"""
    event_sequence: int = 0
    """事件序列号计数器（用于 K13 事件日志）。"""


def initial_game_state(table: TableSnapshot | None = None) -> GameState:
    """开局：``PRE_DEAL``；``table`` 缺省时为半庄默认场况。"""
    t = table if table is not None else initial_table_snapshot()
    return GameState(phase=GamePhase.PRE_DEAL, table=t, board=None)
