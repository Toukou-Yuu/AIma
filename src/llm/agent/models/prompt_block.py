"""Prompt block data models for budget planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

CompressionState = Literal["full", "snip", "micro", "collapse", "autocompact", "drop"]
_COMPRESSION_ORDER: dict[CompressionState, int] = {
    "full": 0,
    "snip": 1,
    "micro": 2,
    "collapse": 3,
    "autocompact": 4,
    "drop": 5,
}


def _role_from_wire(value: object) -> Literal["system", "user", "assistant"]:
    role = str(value)
    if role not in ("system", "user", "assistant"):
        raise ValueError(f"invalid prompt block role: {role!r}")
    return cast(Literal["system", "user", "assistant"], role)


def _compression_state_from_wire(value: object) -> CompressionState:
    state = str(value)
    if state not in _COMPRESSION_ORDER:
        raise ValueError(f"invalid compression state: {state!r}")
    return cast(CompressionState, state)


@dataclass(frozen=True, slots=True)
class PromptBlockVariant:
    """A single compression candidate of a prompt block."""

    state: CompressionState
    text: str


@dataclass(frozen=True, slots=True)
class PromptBlock:
    """A prompt block with ordered compression variants."""

    block_id: str
    role: Literal["system", "user", "assistant"]
    priority: int
    required: bool
    variants: tuple[PromptBlockVariant, ...]

    def validate(self) -> None:
        if not self.variants:
            raise ValueError(f"prompt block {self.block_id!r} must provide at least one variant")


@dataclass(frozen=True, slots=True)
class SelectedPromptBlock:
    """Selected prompt block variant after budget planning."""

    block_id: str
    role: Literal["system", "user", "assistant"]
    priority: int
    required: bool
    state: CompressionState
    text: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class BlockTokenUsage:
    """Token usage of one selected prompt block."""

    block_id: str
    role: Literal["system", "user", "assistant"]
    priority: int
    required: bool
    state: CompressionState
    estimated_tokens: int

    def to_wire(self) -> dict[str, Any]:
        """Serialize for replay/session logs."""
        return {
            "block_id": self.block_id,
            "role": self.role,
            "priority": self.priority,
            "required": self.required,
            "state": self.state,
            "estimated_tokens": self.estimated_tokens,
        }

    @staticmethod
    def from_wire(data: dict[str, Any]) -> "BlockTokenUsage":
        """Deserialize from replay/session logs."""
        return BlockTokenUsage(
            block_id=str(data["block_id"]),
            role=_role_from_wire(data["role"]),
            priority=int(data["priority"]),
            required=bool(data["required"]),
            state=_compression_state_from_wire(data["state"]),
            estimated_tokens=int(data["estimated_tokens"]),
        )