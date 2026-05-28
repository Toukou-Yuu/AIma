"""FallbackStrategy - 决策回退策略组件.

职责：
- 在解析失败或接地失败时提供回退动作
- 支持三种策略：first_legal、random_legal、none
"""

from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING

from agents.pipeline_result import ParseStatus

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction


class FallbackKind(str, Enum):
    """回退策略类型."""

    FIRST_LEGAL = "first_legal"
    RANDOM_LEGAL = "random_legal"
    NONE = "none"


class FallbackStrategy:
    """决策回退策略.

    当解析失败或接地失败时，提供备选动作选择策略。
    """

    def __init__(self, kind: FallbackKind, seed: int | None = None) -> None:
        """初始化回退策略.

        Args:
            kind: 策略类型
            seed: 随机种子（仅 random_legal 策略使用）
        """
        self.kind = kind
        self.seed = seed

    @staticmethod
    def should_fallback(status: ParseStatus) -> bool:
        """判断是否需要回退.

        Args:
            status: 解析状态

        Returns:
            是否需要回退
        """
        return status in ("parse_failed", "match_failed")

    def select(self, legal_actions: tuple["LegalAction", ...]) -> "LegalAction":
        """根据策略选择一个合法动作.

        Args:
            legal_actions: 合法动作列表

        Returns:
            选中的合法动作

        Raises:
            RuntimeError: 策略为 none 时抛出
            ValueError: legal_actions 为空时抛出
        """
        if not legal_actions:
            msg = "legal_actions is empty, cannot fallback"
            raise ValueError(msg)

        if self.kind == FallbackKind.FIRST_LEGAL:
            return legal_actions[0]

        if self.kind == FallbackKind.RANDOM_LEGAL:
            rng = random.Random(self.seed)
            return rng.choice(legal_actions)

        # FallbackKind.NONE
        msg = "Fallback strategy is 'none', no fallback action available"
        raise RuntimeError(msg)