"""Mock CompletionClient 用于测试。"""

from __future__ import annotations

from llm.protocol import ChatMessage


class DummyBackend:
    """测试用 Mock 后端，返回预设响应。

    不调用任何外部服务，适合单元测试。
    """

    def __init__(self, response: str = "mock response") -> None:
        """初始化 Mock 后端。

        Args:
            response: complete() 返回的预设响应
        """
        self._response = response

    @property
    def response(self) -> str:
        """当前预设响应。"""
        return self._response

    @response.setter
    def response(self, value: str) -> None:
        """设置新响应。"""
        self._response = value

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,  # noqa: ARG002
    ) -> str:
        """返回预设响应。

        Args:
            messages: 消息列表（忽略）
            model: 模型名称（忽略）

        Returns:
            预设响应字符串
        """
        return self._response