"""局内行牌相关类型导出（从 board 模块导入）。"""

from __future__ import annotations

# 从 board 模块导入核心类型（保持向后兼容）
from kernel.board import (
    CallResolution,
    CallStage,
    RiverEntry,
    shimocha_seat,
    TurnPhase,
)

__all__ = (
    "CallResolution",
    "CallStage",
    "RiverEntry",
    "shimocha_seat",
    "TurnPhase",
)