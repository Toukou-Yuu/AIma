"""Dummy 后端实现，返回固定响应。"""

# backend type: "dummy"

from __future__ import annotations

from models.backend import ChatMessage
from models.schema import ModelSpec


class DummyBackend:
    """固定响应后端，用于简单测试。

    不调用任何外部服务，始终返回配置的固定响应。
    """

    def __init__(self, spec: ModelSpec) -> None:
        """初始化 Dummy 后端。

        Args:
            spec: 模型配置规格
        """
        if spec.backend != "dummy":
            msg = f"DummyBackend requires backend=dummy, got {spec.backend}"
            raise ValueError(msg)

        self._spec = spec
        self._response = spec.extra.get("response", "dummy response")
        self._last_messages: list[ChatMessage] | None = None

    @property
    def spec(self) -> ModelSpec:
        """当前模型配置。"""
        return self._spec

    @property
    def last_messages(self) -> list[ChatMessage] | None:
        """最近一次调用时传入的消息列表，用于调试。"""
        return self._last_messages

    @property
    def response(self) -> str:
        """当前固定响应。"""
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
        """返回固定响应。

        Args:
            messages: 消息列表（忽略）
            model: 模型名称（忽略）

        Returns:
            固定响应字符串
        """
        self._last_messages = list(messages)
        return self._response