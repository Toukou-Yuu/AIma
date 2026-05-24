"""Memory configuration schemas."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MemoryLayer(str, Enum):
    """Memory layer identifiers.

    Each layer represents a different scope of memory persistence:
    - hand: Current hand memory (cleared after each hand)
    - match: Current match memory (cleared after each match)
    - persistent: Long-term memory (persists across sessions)
    - opponent: Opponent-specific memory (persists across sessions)
    """

    HAND = "hand"
    MATCH = "match"
    PERSISTENT = "persistent"
    OPPONENT = "opponent"


class MemorySpec(BaseModel):
    """Memory configuration."""

    mode: Literal["off", "passive"] = "off"
    layers: list[Literal["hand", "match", "persistent", "opponent"]] = Field(
        default_factory=list
    )
    store: Literal["in_memory", "json", "sqlite"] = "in_memory"
    persist: bool = False
