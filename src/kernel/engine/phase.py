"""对局阶段枚举（壳层）；具体行牌逻辑由后续模块填充。"""

from __future__ import annotations

from enum import Enum


class GamePhase(Enum):
    """引擎阶段；仅 ``PRE_DEAL`` / ``IN_ROUND`` 在 K4 接入转移，其余为占位。"""

    PRE_DEAL = "pre_deal"
    """配牌前。"""
    IN_ROUND = "in_round"
    """局中主循环（摸打等）占位。"""
    CALL_RESPONSE = "call_response"
    """对他家舍牌的应答窗口占位。"""
    HAND_OVER = "hand_over"
    """一局结束（结算前/后细分由后续实现）。"""
    FLOWN = "flown"
    """流局（听牌结算、连庄/亲流判定）。"""
    MATCH_END = "match_end"
    """整场比赛结束。"""
