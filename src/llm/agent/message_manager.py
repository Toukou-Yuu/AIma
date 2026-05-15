"""MessageManager - 消息管理."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm.agent.message_ledger import LedgerMessage, MessageLedger


@dataclass
class MessageManager:
    """消息管理器.

    管理本局消息的追加和查询。
    """

    _ledger: MessageLedger = field(default_factory=MessageLedger)

    def append_user_message(self, content: str, *, turn_index: int, hand_number: int) -> LedgerMessage:
        """Append one user turn-state message."""
        return self._ledger.append(
            role="user",
            content=content,
            turn_index=turn_index,
            hand_number=hand_number,
            kind="turn_state",
        )

    def append_assistant_message(self, content: str, *, turn_index: int, hand_number: int) -> LedgerMessage:
        """Append one assistant decision-reply message."""
        return self._ledger.append(
            role="assistant",
            content=content,
            turn_index=turn_index,
            hand_number=hand_number,
            kind="decision_reply",
        )