"""OpenAI 兼容后端实现。"""

# backend type: "openai_compatible"

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from models.backend import ChatMessage, ModelRequest, ModelResponse
from models.schema import ModelSpec


class OpenAICompatibleBackend:
    """OpenAI 兼容 API 后端。

    通过 ``POST /chat/completions`` 调用模型。
    同时实现 CompletionClient 和 ModelBackend 协议。
    """

    def __init__(self, spec: ModelSpec) -> None:
        """初始化后端。

        Args:
            spec: 模型配置规格
        """
        if spec.backend != "openai_compatible":
            msg = f"OpenAICompatibleBackend requires backend=openai_compatible, got {spec.backend}"
            raise ValueError(msg)
        if not spec.endpoint:
            msg = "OpenAICompatibleBackend requires endpoint"
            raise ValueError(msg)

        self._spec = spec
        self._url = spec.endpoint.rstrip("/") + "/chat/completions"

        # 从环境变量读取 API key
        if spec.api_key_env:
            self._api_key = os.environ.get(spec.api_key_env, "")
        else:
            self._api_key = ""

    @property
    def spec(self) -> ModelSpec:
        """当前模型配置。"""
        return self._spec

    @property
    def backend_name(self) -> str:
        """后端名称。"""
        return "openai_compatible"

    @property
    def model_name(self) -> str:
        """模型名称。"""
        return self._spec.model_name

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
    ) -> str:
        """发送请求（CompletionClient 协议）。

        Args:
            messages: 消息列表
            model: 模型名称（可选，默认使用配置）

        Returns:
            模型回复内容
        """
        response = self._call_api(messages, model or self._spec.model_name)
        return response.text

    def generate(self, request: ModelRequest) -> ModelResponse:
        """生成响应（ModelBackend 协议）。

        Args:
            request: 模型请求

        Returns:
            ModelResponse 包含响应和元信息
        """
        model = str(request.extra_params.get("model", self._spec.model_name))
        return self._call_api(request.messages, model, request=request)

    def _call_api(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        request: ModelRequest | None = None,
    ) -> ModelResponse:
        """调用 API 并返回完整响应。

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            ModelResponse 包含响应和元信息
        """
        start_time = time.perf_counter()

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": (
                request.temperature
                if request is not None and request.temperature is not None
                else self._spec.temperature
            ),
            "max_tokens": (
                request.max_tokens
                if request is not None and request.max_tokens is not None
                else self._spec.max_tokens
            ),
        }

        top_p = request.top_p if request is not None and request.top_p is not None else self._spec.top_p
        if top_p is not None:
            payload["top_p"] = top_p
        if request is not None and request.stop is not None:
            payload["stop"] = request.stop
        if request is not None and request.response_format is not None:
            payload["response_format"] = request.response_format
        if request is not None and request.seed is not None:
            payload["seed"] = request.seed

        # 合并额外参数
        if self._spec.extra:
            payload.update(self._spec.extra)
        if request is not None and request.extra_params:
            payload.update(
                {
                    key: value
                    for key, value in request.extra_params.items()
                    if key != "model"
                }
            )

        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        timeout = self._spec.extra.get("timeout_sec", 60.0)
        with httpx.Client(timeout=timeout) as client:
            r = client.post(self._url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        latency_ms = (time.perf_counter() - start_time) * 1000

        try:
            text = str(data["choices"][0]["message"]["content"] or "").strip()
            finish_reason = data["choices"][0].get("finish_reason", "stop")
        except (KeyError, IndexError, TypeError) as e:
            msg = f"unexpected OpenAI response shape: {data!r}"
            raise RuntimeError(msg) from e

        # 提取 token usage
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

        return ModelResponse(
            text=text,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw_response=data,
            backend_name=self.backend_name,
            model_name=model,
        )
