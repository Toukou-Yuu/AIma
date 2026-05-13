"""engine/call 测试共享 helper。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel import BoardState, build_board_after_split, build_deck, split_wall
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.tiles.model import Suit, Tile


def board_sorted_deal(*, dealer: int = 0) -> BoardState:
    """未洗牌牌山，测试用砌牌可复现。"""
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def pool_not_in_wall(b0: BoardState) -> Counter[Tile]:
    """136 −（本墙未摸段 + 王牌岭上 + 指示牌槽）= 已配手牌与河可占用的 53 张。"""
    rem = Counter(b0.live_wall[b0.live_draw_index :])
    rem.update(b0.dead_wall.rinshan)
    rem.update(b0.dead_wall.ura_bases)
    rem.update(b0.dead_wall.indicators)
    pool = Counter(build_deck())
    for t, n in rem.items():
        pool[t] -= n
    assert sum(pool.values()) == 53
    return pool


def take_n(pool: Counter[Tile], n: int) -> Counter[Tile]:
    """从 pool 中取 n 张（任意顺序）。"""
    out = Counter()
    for _ in range(n):
        x = next(iter(pool.elements()))
        out[x] += 1
        pool[x] -= 1
        if pool[x] == 0:
            del pool[x]
    return out


def make_board(
    *,
    dealer: int = 0,
    target_seat: int = 0,
    target_hand: Counter[Tile],
) -> BoardState:
    """构造 BoardState：target_seat 拿指定手牌，其余随机补 13 张。

    target_hand 应含 14 张（亲家）或 13 张（子家）。
    返回的 board current_seat=dealer, turn_phase=MUST_DISCARD。
    """
    b0 = board_sorted_deal(dealer=dealer)
    pool = pool_not_in_wall(b0)
    # 从 pool 中移除 target_hand 的牌
    for t, n in target_hand.items():
        assert pool[t] >= n, f"pool 中 {t} 不足：需要 {n}，仅有 {pool[t]}"
        pool[t] -= n
        if pool[t] == 0:
            del pool[t]
    hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == target_seat:
            hands.append(Counter(target_hand))
        else:
            hands.append(take_n(pool, 13))
    assert sum(pool.values()) == 0, f"pool 剩余 {sum(pool.values())} 张"
    return replace(b0, hands=tuple(hands))


def make_board_with_discard(
    *,
    dealer: int = 0,
    discarder: int = 0,
    discard_tile: Tile,
    discarder_hand: Counter[Tile] | None = None,
) -> BoardState:
    """构造 CALL_RESPONSE 状态：discarder 刚打出 discard_tile。

    discarder_hand: discarder 的手牌（含要打出的那张）。若为 None 则用默认配牌。
    返回的 board turn_phase=CALL_RESPONSE, call_state 已设置。
    """
    if discarder_hand is not None:
        b = make_board(dealer=dealer, target_seat=discarder, target_hand=discarder_hand)
    else:
        b = board_sorted_deal(dealer=dealer)
    # 打出 discard_tile
    new_hands = list(b.hands)
    h = new_hands[discarder].copy()
    assert h[discard_tile] >= 1, f"seat {discarder} 手中无 {discard_tile}"
    h[discard_tile] -= 1
    if h[discard_tile] == 0:
        del h[discard_tile]
    new_hands[discarder] = h
    entry = RiverEntry(seat=discarder, tile=discard_tile, tsumogiri=False, riichi=False)
    new_river = b.river + (entry,)
    new_disc = list(b.all_discards_per_seat)
    new_disc[discarder] = b.all_discards_per_seat[discarder] + (discard_tile,)
    river_index = len(new_river) - 1
    next_seat = (discarder + 1) % 4
    return BoardState(
        hands=tuple(new_hands),
        live_wall=b.live_wall,
        live_draw_index=b.live_draw_index,
        dead_wall=b.dead_wall,
        revealed_indicators=b.revealed_indicators,
        current_seat=next_seat,
        turn_phase=TurnPhase.CALL_RESPONSE,
        river=new_river,
        melds=b.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b.rinshan_draw_index,
        call_state=CallResolution.initial_after_discard(discarder, river_index, discard_tile),
        riichi=b.riichi,
        ippatsu_eligible=b.ippatsu_eligible,
        double_riichi=b.double_riichi,
        all_discards_per_seat=tuple(new_disc),
        called_discard_indices=b.called_discard_indices,
    )


def make_meld(kind: MeldKind, tiles: tuple[Tile, ...], called_tile: Tile | None = None) -> Meld:
    """快捷构造 Meld。"""
    return Meld(kind=kind, tiles=tiles, called_tile=called_tile)
