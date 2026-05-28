"""Model backend configuration schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelSpec(BaseModel):
    """Model backend configuration."""

    backend: Literal[
        "openai_compatible",
        "llama_cpp",
        "vllm_native",
        "mock",
        "replay",
        "dummy",
    ]
    model_name: str = "dummy"
    endpoint: str | None = None
    api_key_env: str | None = None
    model_path: str | None = None
    temperature: float = 0.0
    top_p: float | None = None
    max_tokens: int = 512
    extra: dict[str, Any] = Field(default_factory=dict)
