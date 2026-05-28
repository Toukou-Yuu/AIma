"""ActionGrounder - 动作接地组件.

职责：
- 包装 find_matching_legal_action
- 返回 GroundResult 供 pipeline 使用
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agents.pipeline_result import GroundResult
from llm.validate import find_matching_legal_action

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction


class ActionGrounder:
    """动作接地器.

    将解析后的 choice 匹配到合法动作。
    """

    @staticmethod
    def ground(
        legal_actions: tuple["LegalAction", ...],
        choice: dict[str, Any],
    ) -> GroundResult:
        """将 choice 接地到合法动作.

        Args:
            legal_actions: 合法动作列表
            choice: 解析后的选择字典

        Returns:
            GroundResult 包含 legal_action、status
        """
        matched = find_matching_legal_action(legal_actions, choice)
        if matched is not None:
            return GroundResult(
                legal_action=matched,
                status="grounded",
            )
        return GroundResult(
            legal_action=None,
            status="no_match",
        )