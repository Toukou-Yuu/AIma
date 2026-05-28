"""Dummy 后端实现，返回固定响应。"""

# backend type: "dummy"

from __future__ import annotations

import time

from models.backend import ChatMessage, ModelRequest, ModelResponse
from models.schema import ModelSpec


class DummyBackend:
    """固定响应后端，用于简单测试。

    不调用任何外部服务，始终返回配置的固定响应。
    同时实现 CompletionClient 和 ModelBackend 协议。
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
    def backend_name(self) -> str:
        """后端名称。"""
        return "dummy"

    @property
    def model_name(self) -> str:
        """模型名称。"""
        return self._spec.model_name

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
        """返回固定响应（CompletionClient 协议）。

        Args:
            messages: 消息列表（忽略）
            model: 模型名称（忽略）

        Returns:
            固定响应字符串
        """
        self._last_messages = list(messages)
        return self._response

    def generate(self, request: ModelRequest) -> ModelResponse:
        """生成固定响应（ModelBackend 协议）。

        Args:
            request: 模型请求

        Returns:
            ModelResponse 包含固定响应
        """
        start_time = time.perf_counter()
        self._last_messages = list(request.messages)

        latency_ms = (time.perf_counter() - start_time) * 1000

        return ModelResponse(
            text=self._response,
            finish_reason="stop",
            latency_ms=latency_ms,
            prompt_tokens=0,
            completion_tokens=0,
            backend_name=self.backend_name,
            model_name=self.model_name,
        )