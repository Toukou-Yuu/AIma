"""补全协议抽象：便于单测注入 stub 与多厂商适配。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from llm.config import LLMClientConfig


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """单条对话消息。"""

    role: str
    """``system`` / ``user`` / ``assistant``"""
    content: str


@runtime_checkable
class CompletionClient(Protocol):
    """一次多轮对话 → 模型文本（由调用方再解析为结构化动作）。"""

    def complete(self, messages: list[ChatMessage], *, model: str | None = None) -> str:
        """返回助手正文（不含 tool 结构）。"""
        ...


def build_client(cfg: LLMClientConfig) -> CompletionClient:
    """根据 ``provider`` 构造具体适配器。"""
    if cfg.provider == "openai":
        from llm.adapters.openai_chat import OpenAIChatClient

        return OpenAIChatClient(cfg)
    from llm.adapters.anthropic_messages import AnthropicMessagesClient

    return AnthropicMessagesClient(cfg)
