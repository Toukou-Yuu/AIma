"""PromptRenderer - 提示词渲染组件.

职责：
- 将 DecisionContext 渲染为 ChatMessage 列表
- 使用 prompts/renderer.py 的真正实现
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llm.protocol import ChatMessage
from prompts.loader import load_template
from prompts.renderer import PromptRenderer as RealPromptRenderer

if TYPE_CHECKING:
    from arena.policy import DecisionContext


class PromptRenderer:
    """提示词渲染器.

    将决策上下文渲染为 LLM 消息列表。
    使用 prompts/renderer.py 的真正实现。
    """

    def __init__(self, template_id: str = "riichi_json_action_v1") -> None:
        """初始化提示词渲染器.

        Args:
            template_id: 模板ID（默认 riichi_json_action_v1）
        """
        self._template_id = template_id
        self._spec = load_template(template_id, use_cache=True)
        self._renderer = RealPromptRenderer(self._spec)

    def render(self, ctx: "DecisionContext") -> list[ChatMessage]:
        """渲染提示词.

        Args:
            ctx: 决策上下文

        Returns:
            包含 system 和 user 消息的列表
        """
        result = self._renderer.render(ctx)
        return list(result.messages)