"""配牌相关常量和函数（BoardState 已迁移至 board 模块）。"""

from __future__ import annotations

# 从 board 模块导入核心类型
from kernel.board import (
    BoardState,
    FIRST_DORA_INDICATOR_INDEX,
    INITIAL_DEAL_TILES,
    LIVE_WALL_AFTER_DEAL,
    validate_board_state,
)

__all__ = (
    "BoardState",
    "FIRST_DORA_INDICATOR_INDEX",
    "INITIAL_DEAL_TILES",
    "LIVE_WALL_AFTER_DEAL",
    "validate_board_state",
)