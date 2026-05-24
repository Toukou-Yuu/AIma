"""ObservationBuilder - 观测信息构建组件.

职责：
- 从 DecisionContext 构建观测描述字符串
- v4.0 存根实现，Stage 5 将完成完整逻辑
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.policy import DecisionContext


class ObservationBuilder:
    """观测信息构建器.

    从 DecisionContext 提取信息，构建供 LLM 理解的观测描述。
    """

    def build(self, ctx: "DecisionContext") -> str:
        """构建观测描述.

        Args:
            ctx: 决策上下文

        Returns:
            观测描述字符串
        """
        # Stub for v4.0 - Stage 5 will implement full logic
        return f"Stub observation for seat {ctx.seat} at {ctx.phase}"