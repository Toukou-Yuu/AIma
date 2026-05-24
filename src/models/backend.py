"""Backend Protocol 与类型定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """单条对话消息。"""

    role: str
    """``system`` / ``user`` / ``assistant``"""
    content: str


@runtime_checkable
class CompletionClient(Protocol):
    """一次多轮对话 → 模型文本。

    上下文由调用方管理，客户端只负责单次补全调用。
    """

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
    ) -> str:
        """返回助手正文。

        Args:
            messages: 消息列表
            model: 模型名称（可选）

        Returns:
            助手回复文本
        """
        ...


# Backend 类型标识符
# "openai_compatible" | "llama_cpp" | "vllm_native" | "mock" | "dummy"
Backend: TypeAlias = str