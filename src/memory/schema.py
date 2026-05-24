"""Memory configuration schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemorySpec(BaseModel):
    """Memory configuration."""

    mode: Literal["off", "passive"] = "off"
    layers: list[Literal["hand", "match", "persistent", "opponent"]] = Field(
        default_factory=list
    )
    store: Literal["in_memory", "json", "sqlite"] = "in_memory"
    persist: bool = False
