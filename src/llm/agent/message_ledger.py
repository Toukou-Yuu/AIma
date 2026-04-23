"""Message-ledger primitives for local chat-style context management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from llm.agent.token_budget import CompressionState

MessageKind = Literal["turn_state", "decision_reply", "summary", "match_archive"]


@dataclass(frozen=True, slots=True)
class LedgerMessage:
    """One locally managed chat message."""

    message_id: str
    role: Literal["user", "assistant"]
    content: str
    turn_index: int
    hand_number: int
    kind: MessageKind
    compression_state: CompressionState = "full"


@dataclass
class MessageLedger:
    """Append-only per-hand message ledger."""

    messages: list[LedgerMessage] = field(default_factory=list)

    def append(
        self,
        *,
        role: Literal["user", "assistant"],
        content: str,
        turn_index: int,
        hand_number: int,
        kind: MessageKind,
    ) -> LedgerMessage:
        """Append one chat message to the ledger."""
        suffix = "user" if role == "user" else "assistant"
        message = LedgerMessage(
            message_id=f"turn_{turn_index}_{suffix}",
            role=role,
            content=content,
            turn_index=turn_index,
            hand_number=hand_number,
            kind=kind,
            compression_state="full",
        )
        self.messages.append(message)
        return message

    def turn_indexes(self) -> list[int]:
        """Return distinct turn indexes in append order."""
        seen: set[int] = set()
        ordered: list[int] = []
        for message in self.messages:
            if message.turn_index in seen:
                continue
            seen.add(message.turn_index)
            ordered.append(message.turn_index)
        return ordered

    def messages_for_turns(self, turn_indexes: set[int]) -> list[LedgerMessage]:
        """Return messages whose turn index belongs to the provided set."""
        return [message for message in self.messages if message.turn_index in turn_indexes]
