"""完整局面根对象（K4 仅含阶段 + 场况；牌山/手牌等见后续）。"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.engine.phase import GamePhase
from kernel.table import TableSnapshot, initial_table_snapshot


@dataclass(frozen=True, slots=True)
class GameState:
    """
    对局状态根节点。

    K5 起可在此挂载本墙游标、手牌、河、宝牌等；K4 不校验牌张守恒。
    """

    phase: GamePhase
    table: TableSnapshot


def initial_game_state(table: TableSnapshot | None = None) -> GameState:
    """开局：``PRE_DEAL``；``table`` 缺省时为半庄默认场况。"""
    t = table if table is not None else initial_table_snapshot()
    return GameState(phase=GamePhase.PRE_DEAL, table=t)
