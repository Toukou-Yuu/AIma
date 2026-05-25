"""Mock 后端实现，用于测试。"""

# backend type: "mock"

from __future__ import annotations

import time

from models.backend import ChatMessage, ModelRequest, ModelResponse
from models.schema import ModelSpec


class MockBackend:
    """可配置响应的 Mock 后端。

    支持预设响应和消息追踪，适合测试场景。
    同时实现 CompletionClient 和 ModelBackend 协议。
    """

    def __init__(self, spec: ModelSpec, responses: dict[str, str] | None = None) -> None:
        """初始化 Mock 后端。

        Args:
            spec: 模型配置规格
            responses: 可选的预设响应映射，key 为消息内容的特征，
                       若为 None 则返回 spec.model_name 作为默认响应
        """
        if spec.backend != "mock":
            msg = f"MockBackend requires backend=mock, got {spec.backend}"
            raise ValueError(msg)

        self._spec = spec
        self._responses = responses or {}
        self._default_response = spec.extra.get("default_response", spec.model_name)
        self._last_messages: list[ChatMessage] | None = None

    @property
    def spec(self) -> ModelSpec:
        """当前模型配置。"""
        return self._spec

    @property
    def backend_name(self) -> str:
        """后端名称。"""
        return "mock"

    @property
    def model_name(self) -> str:
        """模型名称。"""
        return self._spec.model_name

    @property
    def last_messages(self) -> list[ChatMessage] | None:
        """最近一次调用时传入的消息列表，用于测试断言。"""
        return self._last_messages

    def _get_response_for_messages(self, messages: list[ChatMessage]) -> str:
        """根据消息列表获取响应。"""
        # 尝试根据最后一条用户消息匹配响应
        for msg in reversed(messages):
            if msg.role == "user":
                content_key = msg.content
                if content_key in self._responses:
                    return self._responses[content_key]
                break

        return self._default_response

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,  # noqa: ARG002
    ) -> str:
        """返回预设响应（CompletionClient 协议）。

        Args:
            messages: 消息列表
            model: 模型名称（忽略）

        Returns:
            预设响应字符串
        """
        self._last_messages = list(messages)
        return self._get_response_for_messages(messages)

    def generate(self, request: ModelRequest) -> ModelResponse:
        """生成预设响应（ModelBackend 协议）。

        Args:
            request: 模型请求

        Returns:
            ModelResponse 包含预设响应
        """
        start_time = time.perf_counter()
        self._last_messages = list(request.messages)

        text = self._get_response_for_messages(request.messages)
        latency_ms = (time.perf_counter() - start_time) * 1000

        return ModelResponse(
            text=text,
            finish_reason="stop",
            latency_ms=latency_ms,
            prompt_tokens=0,
            completion_tokens=0,
            backend_name=self.backend_name,
            model_name=self.model_name,
        )

    def set_response(self, key: str, response: str) -> None:
        """设置指定 key 的响应。

        Args:
            key: 消息内容 key
            response: 对应的响应
        """
        self._responses[key] = response

    def set_default_response(self, response: str) -> None:
        """设置默认响应。

        Args:
            response: 默认响应字符串
        """
        self._default_response = response