"""Arena error types."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel import Action, LegalAction


class IllegalPolicyDecisionError(Exception):
    """Policy returned action not in legal_actions."""

    seat: int
    action: Action
    legal_actions: tuple[LegalAction, ...]

    def __init__(
        self,
        seat: int,
        action: Action,
        legal_actions: tuple[LegalAction, ...],
        message: str | None = None,
    ) -> None:
        self.seat = seat
        self.action = action
        self.legal_actions = legal_actions
        if message is None:
            message = f"Policy at seat {seat} returned illegal action {action}"
        super().__init__(message)