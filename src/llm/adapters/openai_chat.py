"""OpenAI 兼容 Chat Completions（``httpx``）。"""

from __future__ import annotations

from typing import Any

import httpx

from llm.config import LLMClientConfig
from llm.protocol import ChatMessage


class OpenAIChatClient:
    """``POST /chat/completions``。"""

    def __init__(self, cfg: LLMClientConfig) -> None:
        if cfg.provider != "openai":
            msg = "OpenAIChatClient requires provider=openai"
            raise ValueError(msg)
        self._cfg = cfg
        self._url = cfg.base_url.rstrip("/") + "/chat/completions"

    def complete(self, messages: list[ChatMessage], *, model: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model or self._cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self._cfg.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._cfg.timeout_sec) as client:
            r = client.post(self._url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        try:
            return str(data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as e:
            msg = f"unexpected OpenAI response shape: {data!r}"
            raise RuntimeError(msg) from e
