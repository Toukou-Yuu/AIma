"""从环境变量读取 LLM 配置（不设默认密钥）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class LLMClientConfig:
    """单连接配置；多席可共用或按环境变量覆盖。"""

    provider: Literal["openai", "anthropic"]
    base_url: str
    api_key: str
    model: str
    timeout_sec: float = 120.0
    max_tokens: int = 1024


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is not None and v.strip() != "":
        return v.strip()
    return default


def load_llm_config(*, seat: int | None = None) -> LLMClientConfig | None:
    """
    读取配置。未设置任何 key 时返回 ``None``（调用方应用 dry-run / 跳过）。

    环境变量（示例）::

        AIMA_LLM_PROVIDER=openai
        AIMA_OPENAI_API_KEY=...
        AIMA_OPENAI_BASE_URL=https://api.openai.com/v1
        AIMA_OPENAI_MODEL=gpt-4o-mini

    按席覆盖（可选）::

        AIMA_OPENAI_API_KEY_SEAT0=...
    """
    provider_s = (_env("AIMA_LLM_PROVIDER", "openai") or "openai").lower()
    if provider_s not in ("openai", "anthropic"):
        msg = f"AIMA_LLM_PROVIDER must be openai or anthropic, got {provider_s!r}"
        raise ValueError(msg)
    provider = provider_s  # type: ignore[assignment]

    seat_suffix = f"_SEAT{seat}" if seat is not None else ""
    if provider == "openai":
        key = _env(f"AIMA_OPENAI_API_KEY{seat_suffix}") or _env("AIMA_OPENAI_API_KEY")
        base = _env("AIMA_OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = _env("AIMA_OPENAI_MODEL", "gpt-4o-mini")
    else:
        key = _env(f"AIMA_ANTHROPIC_API_KEY{seat_suffix}") or _env("AIMA_ANTHROPIC_API_KEY")
        base = _env("AIMA_ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        model = _env("AIMA_ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

    if not key:
        return None

    timeout_s = float(_env("AIMA_LLM_TIMEOUT_SEC", "120") or "120")
    max_tok = int(_env("AIMA_LLM_MAX_TOKENS", "1024") or "1024")
    return LLMClientConfig(
        provider=provider,
        base_url=base or "",
        api_key=key,
        model=model or "",
        timeout_sec=timeout_s,
        max_tokens=max_tok,
    )
