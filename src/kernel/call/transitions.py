"""舍牌应答：荣和、pass、吃碰大明杠；返回新 ``BoardState``。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.hand.melds import Meld, MeldKind, triplet_key, validate_meld_shape
from kernel.hand.multiset import remove_tiles
from kernel.play.model import CallResolution, TurnPhase, kamicha_seat
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


def _replace_board(board: BoardState, **kwargs: object) -> BoardState:
    from kernel.deal.model import BoardState

    return BoardState(
        hands=kwargs.get("hands", board.hands),
        live_wall=kwargs.get("live_wall", board.live_wall),
        live_draw_index=kwargs.get("live_draw_index", board.live_draw_index),
        dead_wall=kwargs.get("dead_wall", board.dead_wall),
        revealed_indicators=kwargs.get("revealed_indicators", board.revealed_indicators),
        current_seat=kwargs.get("current_seat", board.current_seat),
        turn_phase=kwargs.get("turn_phase", board.turn_phase),
        river=kwargs.get("river", board.river),
        melds=kwargs.get("melds", board.melds),
        last_draw_tile=kwargs.get("last_draw_tile", board.last_draw_tile),
        call_state=kwargs.get("call_state", board.call_state),
    )


def _finish_call_all_passed(board: BoardState) -> BoardState:
    """三家均放弃鸣牌：下家进入摸牌。"""
    return _replace_board(
        board,
        turn_phase=TurnPhase.NEED_DRAW,
        call_state=None,
    )


def _after_ron_collection(board: BoardState) -> BoardState:
    cs = board.call_state
    assert cs is not None
    new_cs = CallResolution(
        discard_seat=cs.discard_seat,
        claimed_tile=cs.claimed_tile,
        river_index=cs.river_index,
        stage="pon_kan",
        ron_remaining=cs.ron_remaining,
        ron_claimants=cs.ron_claimants,
        pon_kan_order=cs.pon_kan_order,
        pon_kan_idx=0,
        finished=False,
    )
    return _replace_board(board, call_state=new_cs)


def apply_pass_call(board: BoardState, seat: int) -> BoardState:
    """放弃当前阶段可声明的机会（荣和 / 碰杠轮询 / 吃）。"""

    if board.turn_phase != TurnPhase.CALL_RESPONSE:
        msg = "PASS_CALL requires CALL_RESPONSE"
        raise ValueError(msg)
    cs = board.call_state
    assert cs is not None
    if cs.finished:
        msg = "call already finished (ron); cannot PASS_CALL"
        raise ValueError(msg)
    if cs.stage == "ron":
        if seat not in cs.ron_remaining:
            msg = "not in ron_remaining for this seat"
            raise ValueError(msg)
        rem = frozenset(cs.ron_remaining - {seat})
        new_cs = CallResolution(
            discard_seat=cs.discard_seat,
            claimed_tile=cs.claimed_tile,
            river_index=cs.river_index,
            stage="ron",
            ron_remaining=rem,
            ron_claimants=cs.ron_claimants,
            pon_kan_order=cs.pon_kan_order,
            pon_kan_idx=cs.pon_kan_idx,
            finished=False,
        )
        b2 = _replace_board(board, call_state=new_cs)
        if rem:
            return b2
        return _after_ron_collection(b2)
    if cs.stage == "pon_kan":
        active = cs.pon_kan_order[cs.pon_kan_idx]
        if seat != active:
            msg = "PASS_CALL pon_kan: wrong seat"
            raise ValueError(msg)
        nxt = cs.pon_kan_idx + 1
        if nxt < 3:
            new_cs = CallResolution(
                discard_seat=cs.discard_seat,
                claimed_tile=cs.claimed_tile,
                river_index=cs.river_index,
                stage="pon_kan",
                ron_remaining=cs.ron_remaining,
                ron_claimants=cs.ron_claimants,
                pon_kan_order=cs.pon_kan_order,
                pon_kan_idx=nxt,
                finished=False,
            )
            return _replace_board(board, call_state=new_cs)
        new_cs = CallResolution(
            discard_seat=cs.discard_seat,
            claimed_tile=cs.claimed_tile,
            river_index=cs.river_index,
            stage="chi",
            ron_remaining=cs.ron_remaining,
            ron_claimants=cs.ron_claimants,
            pon_kan_order=cs.pon_kan_order,
            pon_kan_idx=3,
            finished=False,
        )
        return _replace_board(board, call_state=new_cs)
    if cs.stage == "chi":
        if seat != kamicha_seat(cs.discard_seat):
            msg = "PASS_CALL chi: only kamicha"
            raise ValueError(msg)
        return _finish_call_all_passed(board)
    msg = f"unknown call stage: {cs.stage!r}"
    raise ValueError(msg)


def apply_ron(
    board: BoardState,
    seat: int,
    *,
    can_ron=None,
) -> BoardState:
    """
    宣告荣和。``can_ron(concealed, melds, win_tile) -> bool`` 可注入；默认七对子。
    荣和收集结束时若有和牌者，置 ``call_state.finished``，由引擎转 ``HAND_OVER``。
    """
    from collections.abc import Callable

    from kernel.call.win import can_ron_seven_pairs

    if board.turn_phase != TurnPhase.CALL_RESPONSE:
        msg = "RON requires CALL_RESPONSE"
        raise ValueError(msg)
    cs = board.call_state
    assert cs is not None
    if cs.stage != "ron":
        msg = "RON only in ron stage"
        raise ValueError(msg)
    if seat not in cs.ron_remaining:
        msg = "seat cannot declare RON now"
        raise ValueError(msg)
    checker: Callable[..., bool] = can_ron if can_ron is not None else can_ron_seven_pairs
    if not checker(board.hands[seat], board.melds[seat], cs.claimed_tile):
        msg = "illegal ron shape"
        raise ValueError(msg)
    rem = frozenset(cs.ron_remaining - {seat})
    cl = frozenset(cs.ron_claimants | {seat})
    done_ron = not rem
    new_cs = CallResolution(
        discard_seat=cs.discard_seat,
        claimed_tile=cs.claimed_tile,
        river_index=cs.river_index,
        stage="ron",
        ron_remaining=rem,
        ron_claimants=cl,
        pon_kan_order=cs.pon_kan_order,
        pon_kan_idx=cs.pon_kan_idx,
        finished=done_ron and bool(cl),
    )
    b2 = _replace_board(board, call_state=new_cs)
    if done_ron:
        if cl:
            return b2
        return _after_ron_collection(b2)
    return b2


def _strip_called_meld(meld: Meld, claimer: int, discard_seat: int) -> Meld:
    rel = (discard_seat - claimer + 4) % 4
    return Meld(
        kind=meld.kind,
        tiles=meld.tiles,
        called_tile=meld.called_tile,
        from_seat=rel,
    )


def _remove_claimed_river(board: BoardState) -> tuple[Tile, ...]:
    cs = board.call_state
    assert cs is not None
    if cs.river_index != len(board.river) - 1:
        msg = "can only claim the latest river discard"
        raise ValueError(msg)
    return board.river[:-1]


def apply_open_meld(board: BoardState, seat: int, meld: Meld) -> BoardState:
    """吃 / 碰 / 大明杠：鸣入当前 ``call_state`` 所指的舍牌。"""
    from kernel.deal.model import BoardState

    validate_meld_shape(meld)
    if board.turn_phase != TurnPhase.CALL_RESPONSE:
        msg = "OPEN_MELD requires CALL_RESPONSE"
        raise ValueError(msg)
    cs = board.call_state
    assert cs is not None
    tile = cs.claimed_tile
    ds = cs.discard_seat
    if meld.called_tile != tile:
        msg = "meld.called_tile must match claimed discard"
        raise ValueError(msg)

    if meld.kind == MeldKind.CHI:
        if cs.stage != "chi":
            msg = "CHI only in chi stage"
            raise ValueError(msg)
        if seat != kamicha_seat(ds):
            msg = "CHI only by kamicha"
            raise ValueError(msg)
        from_hand = [t for t in meld.tiles if t != tile]
        if len(from_hand) != 2:
            msg = "chi must use exactly two hand tiles besides claim"
            raise ValueError(msg)
        new_concealed = remove_tiles(board.hands[seat], from_hand)
        m2 = _strip_called_meld(meld, seat, ds)
        new_melds = list(board.melds)
        new_melds[seat] = board.melds[seat] + (m2,)
        new_river = _remove_claimed_river(board)
        return BoardState(
            hands=tuple(new_concealed if s == seat else board.hands[s] for s in range(4)),
            live_wall=board.live_wall,
            live_draw_index=board.live_draw_index,
            dead_wall=board.dead_wall,
            revealed_indicators=board.revealed_indicators,
            current_seat=seat,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=new_river,
            melds=tuple(new_melds),
            last_draw_tile=None,
            call_state=None,
        )

    if meld.kind == MeldKind.PON:
        if cs.stage != "pon_kan":
            msg = "PON only in pon_kan stage"
            raise ValueError(msg)
        if cs.pon_kan_order[cs.pon_kan_idx] != seat:
            msg = "PON: not your turn in pon_kan order"
            raise ValueError(msg)
        from_hand = [t for t in meld.tiles if t != tile]
        if len(from_hand) != 2:
            msg = "pon must use exactly two hand tiles besides claim"
            raise ValueError(msg)
        k0 = triplet_key(tile)
        if any(triplet_key(t) != k0 for t in from_hand):
            msg = "pon hand tiles must match claimed triplet_key"
            raise ValueError(msg)
        new_concealed = remove_tiles(board.hands[seat], from_hand)
        m2 = _strip_called_meld(meld, seat, ds)
        new_melds = list(board.melds)
        new_melds[seat] = board.melds[seat] + (m2,)
        new_river = _remove_claimed_river(board)
        return BoardState(
            hands=tuple(new_concealed if s == seat else board.hands[s] for s in range(4)),
            live_wall=board.live_wall,
            live_draw_index=board.live_draw_index,
            dead_wall=board.dead_wall,
            revealed_indicators=board.revealed_indicators,
            current_seat=seat,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=new_river,
            melds=tuple(new_melds),
            last_draw_tile=None,
            call_state=None,
        )

    if meld.kind == MeldKind.DAIMINKAN:
        if cs.stage != "pon_kan":
            msg = "DAIMINKAN only in pon_kan stage"
            raise ValueError(msg)
        if cs.pon_kan_order[cs.pon_kan_idx] != seat:
            msg = "DAIMINKAN: not your turn in pon_kan order"
            raise ValueError(msg)
        from_hand = [t for t in meld.tiles if t != tile]
        if len(from_hand) != 3:
            msg = "daiminkan must use three hand tiles besides claim"
            raise ValueError(msg)
        k0 = triplet_key(tile)
        if any(triplet_key(t) != k0 for t in from_hand):
            msg = "daiminkan hand tiles must match claimed triplet_key"
            raise ValueError(msg)
        new_concealed = remove_tiles(board.hands[seat], from_hand)
        m2 = _strip_called_meld(meld, seat, ds)
        new_melds = list(board.melds)
        new_melds[seat] = board.melds[seat] + (m2,)
        new_river = _remove_claimed_river(board)
        return BoardState(
            hands=tuple(new_concealed if s == seat else board.hands[s] for s in range(4)),
            live_wall=board.live_wall,
            live_draw_index=board.live_draw_index,
            dead_wall=board.dead_wall,
            revealed_indicators=board.revealed_indicators,
            current_seat=seat,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=new_river,
            melds=tuple(new_melds),
            last_draw_tile=None,
            call_state=None,
        )

    msg = f"unsupported meld kind for open meld: {meld.kind!r}"
    raise ValueError(msg)


def board_after_ron_winners(board: BoardState) -> BoardState:
    """
    多家荣和后的牌桌快照（结算占位）：保持手牌/河不变，仅清除应答状态。
    和了牌仍在河中由上层处理或后续 K10 细化。
    """
    from kernel.deal.model import BoardState

    cs = board.call_state
    if cs is None or not cs.ron_claimants or not cs.finished:
        msg = "board_after_ron_winners requires finished ron with non-empty ron_claimants"
        raise ValueError(msg)
    return BoardState(
        hands=board.hands,
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=board.current_seat,
        turn_phase=TurnPhase.NEED_DRAW,
        river=board.river,
        melds=board.melds,
        last_draw_tile=None,
        call_state=None,
    )
