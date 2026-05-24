"""OpenAI 兼容后端实现。"""

# backend type: "openai_compatible"

from __future__ import annotations

import os
from typing import Any

import httpx

from models.backend import ChatMessage
from models.schema import ModelSpec


class OpenAICompatibleBackend:
    """OpenAI 兼容 API 后端。

    通过 ``POST /chat/completions`` 调用模型。
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

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
    ) -> str:
        """发送请求。

        Args:
            messages: 消息列表
            model: 模型名称（可选，默认使用配置）

        Returns:
            模型回复内容
        """
        payload: dict[str, Any] = {
            "model": model or self._spec.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._spec.temperature,
            "max_tokens": self._spec.max_tokens,
        }

        if self._spec.top_p is not None:
            payload["top_p"] = self._spec.top_p

        # 合并额外参数
        if self._spec.extra:
            payload.update(self._spec.extra)

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

        try:
            return str(data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as e:
            msg = f"unexpected OpenAI response shape: {data!r}"
            raise RuntimeError(msg) from e