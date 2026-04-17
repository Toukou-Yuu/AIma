"""鸣牌与杠候选枚举：供 ``legal_actions`` 使用，语义与 ``apply_*`` 对齐。"""

from __future__ import annotations

from collections import Counter
from itertools import combinations, product

from kernel.call.transitions import _hand_subset_for_open_meld
from kernel.deal.model import BoardState
from kernel.hand.melds import (
    Meld,
    MeldKind,
    _chi_sort_key,
    _pon_sort_key,
    triplet_key,
    validate_meld_shape,
)
from kernel.hand.multiset import remove_tile, remove_tiles
from kernel.play.model import TurnPhase, shimocha_seat
from kernel.tiles.model import Suit, Tile


def _strip_from_seat(discard_seat: int, claimer: int) -> int:
    return (discard_seat - claimer + 4) % 4


def _tiles_matching_triplet_key(hand: Counter[Tile], k: tuple[Suit, int]) -> list[Tile]:
    return [t for t in hand.elements() if triplet_key(t) == k]


def _pool_rank(hand: Counter[Tile], suit: Suit, rank: int) -> list[Tile]:
    return [t for t in hand.elements() if t.suit == suit and t.rank == rank]


def enumerate_call_response_open_melds(board: BoardState, seat: int) -> tuple[Meld, ...]:
    """
    当前 ``CALL_RESPONSE`` 下，该席可声明的吃/碰/大明杠。
    ``from_seat`` 已填，与 ``apply_open_meld`` 一致。
    """
    if board.turn_phase != TurnPhase.CALL_RESPONSE:
        return ()
    cs = board.call_state
    if cs is None or cs.chankan_rinshan_pending:
        return ()
    if board.riichi[seat]:
        return ()

    hand = board.hands[seat]
    claimed = cs.claimed_tile
    ds = cs.discard_seat
    rel = _strip_from_seat(ds, seat)
    seen: set[Meld] = set()
    out: list[Meld] = []

    def try_add(m: Meld) -> None:
        if m in seen:
            return
        try:
            validate_meld_shape(m)
            want = 2 if m.kind in (MeldKind.CHI, MeldKind.PON) else 3
            wh = _hand_subset_for_open_meld(m, claimed, want)
            remove_tiles(hand, wh)
        except ValueError:
            return
        seen.add(m)
        out.append(m)

    if cs.stage == "pon_kan" and seat == cs.pon_kan_order[cs.pon_kan_idx]:
        k0 = triplet_key(claimed)
        pool = _tiles_matching_triplet_key(hand, k0)
        for pair in combinations(pool, 2):
            tiles = tuple(sorted(pair + (claimed,), key=_pon_sort_key))
            m = Meld(
                kind=MeldKind.PON,
                tiles=tiles,
                called_tile=claimed,
                from_seat=rel,
            )
            try_add(m)
        for triple in combinations(pool, 3):
            tiles = tuple(sorted(triple + (claimed,), key=_pon_sort_key))
            m = Meld(
                kind=MeldKind.DAIMINKAN,
                tiles=tiles,
                called_tile=claimed,
                from_seat=rel,
            )
            try_add(m)

    elif cs.stage == "chi" and seat == shimocha_seat(ds):
        if claimed.suit == Suit.HONOR:
            return ()
        suit = claimed.suit
        cr = claimed.rank
        for start in range(1, 8):
            r0, r1, r2 = start, start + 1, start + 2
            if cr not in (r0, r1, r2):
                continue
            others = [r for r in (r0, r1, r2) if r != cr]
            if len(others) != 2:
                continue
            ra, rb = others[0], others[1]
            for ta, tb in product(_pool_rank(hand, suit, ra), _pool_rank(hand, suit, rb)):
                tiles = tuple(sorted((ta, tb, claimed), key=_chi_sort_key))
                m = Meld(
                    kind=MeldKind.CHI,
                    tiles=tiles,
                    called_tile=claimed,
                    from_seat=rel,
                )
                try_add(m)

    return tuple(out)


def enumerate_ankan_melds(board: BoardState, seat: int) -> tuple[Meld, ...]:
    """``MUST_DISCARD`` 下可暗杠的 ``Meld``（``called_tile=None``）。"""
    if board.turn_phase != TurnPhase.MUST_DISCARD:
        return ()
    if seat != board.current_seat or board.last_draw_was_rinshan or board.call_state is not None:
        return ()

    hand = board.hands[seat]
    by_key: dict[tuple[Suit, int], list[Tile]] = {}
    for t in hand.elements():
        k = triplet_key(t)
        by_key.setdefault(k, []).append(t)

    seen: set[Meld] = set()
    out: list[Meld] = []
    for pool in by_key.values():
        if len(pool) < 4:
            continue
        for quad in combinations(pool, 4):
            tiles = tuple(sorted(quad, key=_pon_sort_key))
            m = Meld(kind=MeldKind.ANKAN, tiles=tiles, called_tile=None, from_seat=None)
            try:
                validate_meld_shape(m)
                remove_tiles(hand, list(quad))
            except ValueError:
                continue
            if m not in seen:
                seen.add(m)
                out.append(m)
    return tuple(out)


def enumerate_shankuminkan_melds(board: BoardState, seat: int) -> tuple[Meld, ...]:
    """``MUST_DISCARD`` 下可加杠的 ``Meld``（立直后无；引擎与 ``apply_shankuminkan`` 一致）。"""
    if board.turn_phase != TurnPhase.MUST_DISCARD:
        return ()
    if seat != board.current_seat or board.last_draw_was_rinshan or board.call_state is not None:
        return ()
    if board.riichi[seat]:
        return ()

    hand = board.hands[seat]
    seen: set[Meld] = set()
    out: list[Meld] = []

    for pon in board.melds[seat]:
        if pon.kind != MeldKind.PON:
            continue
        k0 = triplet_key(pon.tiles[0])
        old_c = Counter(pon.tiles)
        for extra in set(hand.elements()):
            if triplet_key(extra) != k0:
                continue
            tiles = tuple(sorted(pon.tiles + (extra,), key=_pon_sort_key))
            m = Meld(kind=MeldKind.SHANKUMINKAN, tiles=tiles, called_tile=None, from_seat=None)
            try:
                validate_meld_shape(m)
                new_c = Counter(m.tiles)
                diff = new_c - old_c
                if sum(diff.values()) != 1:
                    continue
                remove_tile(hand, extra)
            except ValueError:
                continue
            if m not in seen:
                seen.add(m)
                out.append(m)
    return tuple(out)
