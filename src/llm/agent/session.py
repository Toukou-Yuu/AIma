"""Local context boundary policy and log naming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4


ContextScope = Literal["stateless", "per_hand", "per_match"]


@dataclass(frozen=True, slots=True)
class PromptContextWindow:
    """一次请求应注入的本地上下文窗口。"""

    include_match_archive: bool = False
    include_public_history: bool = False
    include_self_history: bool = False


class LocalContextPolicy:
    """AIma 本地上下文边界策略.

    不依赖任何服务端会话能力，完全由本地决定要注入哪些上下文：
    - stateless: 只发送当前观测
    - per_hand: 发送本局历史 + 当前观测
    - per_match: 发送本场前情摘要 + 本局历史 + 当前观测
    """

    def __init__(
        self,
        *,
        scope: ContextScope,
    ) -> None:
        """初始化本地上下文策略。"""
        self.scope = scope

    def build_window(self) -> PromptContextWindow:
        """Return which local context layers should be injected."""
        if self.scope == "stateless":
            return PromptContextWindow()
        return PromptContextWindow(
            include_match_archive=self.scope == "per_match",
            include_public_history=True,
            include_self_history=True,
        )


class ConversationIdNamer:
    """对话日志命名器。"""

    def __init__(self, player_id: str | None = None) -> None:
        self.player_id = player_id
        self._conversation_token = str(uuid4())[:8]

    def build_conversation_id(self, seat: int, hand_number: int = 1) -> str:
        """为日志文件构建稳定的局级会话名。"""
        session_key = self.player_id or f"seat_{seat}"
        return f"majiang_player_{session_key}_{self._conversation_token}_h{hand_number}"
