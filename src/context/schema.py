"""Context builder configuration schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ContextSpec(BaseModel):
    """Context builder configuration."""

    scope: Literal["stateless", "per_turn", "per_hand", "per_match"] = "stateless"
    compression: Literal["none", "snip", "collapse", "autocompact"] = "none"
    include_public_events: bool = True
    include_scoreboard: bool = True
    include_self_discards: bool = True
    include_opponent_discards: bool = True
    max_events: int | None = None
