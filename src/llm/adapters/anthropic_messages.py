"""Anthropic Messages API（``httpx``）。"""

from __future__ import annotations

from typing import Any

import httpx

from llm.config import LLMClientConfig
from llm.protocol import ChatMessage


class AnthropicMessagesClient:
    """``POST /v1/messages``。"""

    def __init__(self, cfg: LLMClientConfig) -> None:
        if cfg.provider != "anthropic":
            msg = "AnthropicMessagesClient requires provider=anthropic"
            raise ValueError(msg)
        self._cfg = cfg
        base = cfg.base_url.rstrip("/")
        self._url = f"{base}/v1/messages"

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        session_id: str | None = None,  # Anthropic 不支持，仅保持接口兼容
    ) -> str:
        system_parts: list[str] = []
        api_messages: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            elif m.role in ("user", "assistant"):
                api_messages.append({"role": m.role, "content": m.content})
            else:
                api_messages.append({"role": "user", "content": m.content})

        payload: dict[str, Any] = {
            "model": model or self._cfg.model,
            "max_tokens": self._cfg.max_tokens,
            "messages": api_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        headers = {
            "x-api-key": self._cfg.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._cfg.timeout_sec) as client:
            r = client.post(self._url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        try:
            blocks = data["content"]
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return "".join(texts).strip()
        except (KeyError, TypeError) as e:
            msg = f"unexpected Anthropic response shape: {data!r}"
            raise RuntimeError(msg) from e
