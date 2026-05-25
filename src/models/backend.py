"""Backend Protocol 与类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeAlias, runtime_checkable


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """单条对话消息。"""

    role: str
    """``system`` / ``user`` / ``assistant``"""
    content: str


@dataclass
class ModelRequest:
    """模型请求参数。

    Attributes:
        messages: 消息列表
        temperature: 温度参数（可选）
        top_p: top_p 参数（可选）
        max_tokens: 最大生成 tokens（可选）
        stop: 停止词列表（可选）
        response_format: 响应格式（可选）
        seed: 随机种子（可选）
        extra_params: 额后参数（可选）
    """

    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """模型响应结果。

    Attributes:
        text: 生成的文本
        finish_reason: 结束原因（stop, length, error 等）
        latency_ms: 调用耗时（毫秒）
        prompt_tokens: 输入 tokens 数
        completion_tokens: 输出 tokens 数
        raw_response: 原始响应对象（可选）
        backend_name: 后端名称
        model_name: 模型名称
    """

    text: str
    finish_reason: str | None = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw_response: Any | None = None
    backend_name: str = "unknown"
    model_name: str = "unknown"


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


@runtime_checkable
class ModelBackend(Protocol):
    """模型后端协议（v4.0 新接口）。

    返回完整的 ModelResponse，包含 token usage 等信息。
    """

    def generate(self, request: ModelRequest) -> ModelResponse:
        """生成模型响应。

        Args:
            request: 模型请求

        Returns:
            ModelResponse 包含文本和元信息
        """
        ...

    @property
    def backend_name(self) -> str:
        """后端名称。"""
        ...

    @property
    def model_name(self) -> str:
        """模型名称。"""
        ...


# Backend 类型标识符
# "openai_compatible" | "llama_cpp" | "vllm_native" | "mock" | "dummy" | "replay"
Backend: TypeAlias = str