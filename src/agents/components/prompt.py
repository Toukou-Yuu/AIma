"""PromptRenderer - 提示词渲染组件.

职责：
- 将 DecisionContext 渲染为 ChatMessage 列表
- 生成 system prompt 和 user prompt
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from llm.protocol import ChatMessage

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.api.observation import Observation


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """决策上下文（v4.0 stub）.

    Attributes:
        observation: 观测信息
        legal_actions: 合法动作列表
    """

    observation: "Observation"
    legal_actions: tuple["LegalAction", ...]


class PromptRenderer:
    """提示词渲染器.

    将决策上下文渲染为 LLM 消息列表。
    """

    def render(self, ctx: DecisionContext) -> list[ChatMessage]:
        """渲染提示词.

        Args:
            ctx: 决策上下文

        Returns:
            包含 system 和 user 消息的列表
        """
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._build_system_prompt()),
            ChatMessage(role="user", content=self._build_user_prompt(ctx)),
        ]
        return messages

    @staticmethod
    def _build_system_prompt() -> str:
        """构建系统提示词（v4.0 stub）."""
        return "You are a Mahjong player."

    @staticmethod
    def _build_user_prompt(ctx: DecisionContext) -> str:
        """构建用户提示词（v4.0 stub）."""
        return f"Please choose an action. You have {len(ctx.legal_actions)} legal actions."