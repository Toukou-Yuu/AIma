"""Ron declaration rules shared by action enumeration and application."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from kernel.call.win import can_ron_default
from kernel.deal.model import BoardState, Meld
from kernel.play.model import TurnPhase
from kernel.scoring.furiten import is_furiten_for_tile
from kernel.tiles.model import Tile

RonShapeChecker = Callable[[Counter[Tile], tuple[Meld, ...], Tile], bool]


@dataclass(frozen=True, slots=True)
class RonDeclarationCheck:
    """Result of checking whether a seat may declare ron in the current call window."""

    allowed: bool
    reason: str = ""


def can_declare_ron(
    board: BoardState,
    seat: int,
    *,
    can_ron: RonShapeChecker | None = None,
) -> RonDeclarationCheck:
    """Check BoardState-level ron declaration gates.

    This deliberately excludes yaku scoring checks that need ``GameState.table``.
    """
    if board.turn_phase != TurnPhase.CALL_RESPONSE:
        return RonDeclarationCheck(False, "RON requires CALL_RESPONSE")

    cs = board.call_state
    if cs is None:
        return RonDeclarationCheck(False, "RON requires call_state")
    if cs.stage != "ron":
        return RonDeclarationCheck(False, "RON only in ron stage")

    opponents = frozenset(((cs.discard_seat + i) % 4) for i in (1, 2, 3))
    if seat not in opponents:
        return RonDeclarationCheck(False, "RON seat must be opponent of discarder")
    if seat in cs.ron_claimants:
        return RonDeclarationCheck(False, "already declared ron")
    if seat in cs.ron_passed_seats:
        return RonDeclarationCheck(False, "同巡振听")
    if seat not in cs.ron_remaining:
        return RonDeclarationCheck(False, "seat cannot declare RON now")

    checker = can_ron if can_ron is not None else can_ron_default
    if not checker(board.hands[seat], board.melds[seat], cs.claimed_tile):
        return RonDeclarationCheck(False, "illegal ron shape")
    if is_furiten_for_tile(board, seat, cs.claimed_tile):
        return RonDeclarationCheck(False, "furiten: cannot ron")
    return RonDeclarationCheck(True)


def require_can_declare_ron(
    board: BoardState,
    seat: int,
    *,
    can_ron: RonShapeChecker | None = None,
) -> None:
    """Raise ``ValueError`` when ``seat`` cannot declare ron."""
    check = can_declare_ron(board, seat, can_ron=can_ron)
    if not check.allowed:
        raise ValueError(check.reason)
