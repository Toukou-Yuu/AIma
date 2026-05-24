"""engine/call 测试共享 helper。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel import BoardState, build_board_after_split, build_deck, split_wall
from kernel.hand.melds import Meld, MeldKind
from kernel.board import CallResolution, RiverEntry, TurnPhase
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


def make_tsumo_board(
    *,
    dealer: int = 0,
    target_seat: int = 0,
    target_hand: Counter[Tile],
    win_tile: Tile,
) -> BoardState:
    """构造自摸听牌状态：target_seat 有 13 张手牌 + 1 张 win_tile = 14 张和牌形。

    target_hand: 13 张手牌（不含 win_tile）。
    win_tile: 刚摸到的和了牌。
    返回的 board turn_phase=MUST_DISCARD, last_draw_tile=win_tile。
    """
    b0 = board_sorted_deal(dealer=dealer)
    pool = pool_not_in_wall(b0)

    # 从 pool 移除 target_hand 的牌
    for t, n in target_hand.items():
        assert pool[t] >= n, f"pool 中 {t} 不足：需要 {n}，仅有 {pool[t]}"
        pool[t] -= n
        if pool[t] == 0:
            del pool[t]

    # win_tile 也需要在 pool 中（用来替换 live_wall 的第一张）
    assert pool[win_tile] >= 1, f"pool 中无 {win_tile}"
    pool[win_tile] -= 1
    if pool[win_tile] == 0:
        del pool[win_tile]

    # 其他座位
    hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == target_seat:
            h = Counter(target_hand)
            h[win_tile] += 1  # 手牌含 win_tile（刚摸到）
            hands.append(h)
        else:
            hands.append(take_n(pool, 13))

    # 替换 live_wall[0] 为 win_tile（确保 apply_draw 摸到 win_tile）
    # 原来的 live_wall[0] 放回 pool 以保持张数守恒
    live = list(b0.live_wall)
    original_tile = live[0]
    pool[original_tile] = pool.get(original_tile, 0) + 1
    live[0] = win_tile

    return BoardState(
        hands=tuple(hands),
        live_wall=tuple(live),
        live_draw_index=0,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=target_seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=(),
        melds=b0.melds,
        last_draw_tile=win_tile,
        last_draw_was_rinshan=False,
        rinshan_draw_index=0,
        call_state=None,
        riichi=(False, False, False, False),
        ippatsu_eligible=frozenset(),
        double_riichi=frozenset(),
        all_discards_per_seat=((), (), (), ()),
        called_discard_indices=b0.called_discard_indices,
    )


def make_ron_board(
    *,
    dealer: int = 0,
    discarder: int = 0,
    winner: int = 1,
    winner_hand: Counter[Tile],
    win_tile: Tile,
) -> BoardState:
    """构造 CALL_RESPONSE 状态：discarder 打出 win_tile，winner 手牌可荣和。

    winner_hand: winner 的 13 张手牌（可能含 win_tile，如七对子单张等待）。
    win_tile: 被打出的和牌。
    返回的 board turn_phase=CALL_RESPONSE, call_state.stage="ron", winner 在 ron_remaining 中。
    """
    assert winner != discarder, "winner 不能是 discarder"

    b0 = board_sorted_deal(dealer=dealer)
    pool = pool_not_in_wall(b0)

    # 从 pool 移除 winner_hand 的牌
    for t, n in winner_hand.items():
        assert pool[t] >= n, f"pool 中 {t} 不足：需要 {n}，仅有 {pool[t]}"
        pool[t] -= n
        if pool[t] == 0:
            del pool[t]

    # discarder: 13 张（不含 win_tile）+ win_tile = 14 张
    # 打出 win_tile 后手里剩 13 张
    assert pool[win_tile] >= 1, f"pool 中无 {win_tile}"
    pool[win_tile] -= 1  # 预留
    if pool[win_tile] == 0:
        del pool[win_tile]
    hand_discarder = take_n(pool, 13)
    hand_discarder[win_tile] += 1
    # 打出 win_tile 到河里，手里减掉
    hand_discarder[win_tile] -= 1
    if hand_discarder[win_tile] == 0:
        del hand_discarder[win_tile]

    # 其他座位
    hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == discarder:
            hands.append(hand_discarder)
        elif s == winner:
            hands.append(Counter(winner_hand))
        else:
            hands.append(take_n(pool, 13))

    # 构造 river（discarder 打出 win_tile）
    entry = RiverEntry(seat=discarder, tile=win_tile, tsumogiri=False, riichi=False)
    new_river = b0.river + (entry,)
    new_disc = list(b0.all_discards_per_seat)
    new_disc[discarder] = b0.all_discards_per_seat[discarder] + (win_tile,)
    river_index = len(new_river) - 1

    # 构造 CallResolution: ron 阶段，winner 在 ron_remaining 中
    o1 = (discarder + 1) % 4
    o2 = (discarder + 2) % 4
    o3 = (discarder + 3) % 4
    ron_remaining = frozenset((o1, o2, o3))
    assert winner in ron_remaining, f"winner {winner} 不是 discarder {discarder} 的对手"

    cs = CallResolution(
        discard_seat=discarder,
        claimed_tile=win_tile,
        river_index=river_index,
        stage="ron",
        ron_remaining=ron_remaining,
        ron_claimants=frozenset(),
        pon_kan_order=(o1, o2, o3),
        pon_kan_idx=0,
        finished=False,
    )

    return BoardState(
        hands=tuple(hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=winner,
        turn_phase=TurnPhase.CALL_RESPONSE,
        river=new_river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=0,
        call_state=cs,
        riichi=(False, False, False, False),
        ippatsu_eligible=frozenset(),
        double_riichi=frozenset(),
        all_discards_per_seat=tuple(new_disc),
        called_discard_indices=b0.called_discard_indices,
    )


def shimocha_seat(discarder: int) -> int:
    """下家座位。"""
    return (discarder + 1) % 4


def make_four_kans_wall() -> tuple[Tile, ...]:
    """构造固定牌山用于四杠散了测试：四家各有 4 张相同牌可暗杠。

    牌山分配顺序（dealer=0）：
    - seat 0: live[0:4, 16:20, 32:36, 48, 52]
    - seat 1: live[4:8, 20:24, 36:40, 49]
    - seat 2: live[8:12, 24:28, 40:44, 50]
    - seat 3: live[12:16, 28:32, 44:48, 51]

    构造：
    - seat 0: MAN1×4（放在 live[0:4])
    - seat 1: MAN9×4（放在 live[4:8])
    - seat 2: PIN1×4（放在 live[8:12])
    - seat 3: PIN9×4（放在 live[12:16])

    其余位置填充标准牌山剩余牌（随机但确定性）。
    """
    # 构造标准牌山作为填充来源
    filler_deck = list(build_deck())
    # 移除已使用的特殊牌
    to_remove = [
        Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1),
        Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1),
        Tile(Suit.PIN, 9), Tile(Suit.PIN, 9), Tile(Suit.PIN, 9), Tile(Suit.PIN, 9),
    ]
    filler_counter = Counter(filler_deck)
    for t in to_remove:
        filler_counter[t] -= 1
        if filler_counter[t] == 0:
            del filler_counter[t]
    filler = list(filler_counter.elements())

    # 构造完整牌山
    wall = [None] * 136

    # seat 0 的 4 张 MAN1
    for i in range(4):
        wall[i] = Tile(Suit.MAN, 1)
    # seat 1 的 4 张 MAN9
    for i in range(4, 8):
        wall[i] = Tile(Suit.MAN, 9)
    # seat 2 的 4 张 PIN1
    for i in range(8, 12):
        wall[i] = Tile(Suit.PIN, 1)
    # seat 3 的 4 张 PIN9
    for i in range(12, 16):
        wall[i] = Tile(Suit.PIN, 9)

    # 填充剩余位置
    filler_idx = 0
    for i in range(136):
        if wall[i] is None:
            wall[i] = filler[filler_idx]
            filler_idx += 1

    return tuple(wall)


def make_chi_pon_daiminkan_board(
    *,
    dealer: int = 0,
    discarder: int = 0,
    claimer: int = 1,
    discard_tile: Tile,
    claimer_extra_tiles: list[Tile],
    stage: str = "pon_kan",
) -> tuple[BoardState, Meld]:
    """构造 CALL_RESPONSE 状态的 board 和对应的 meld。

    discarder: 打牌者
    claimer: 鸣牌者
    discard_tile: 被打出的牌
    claimer_extra_tiles: claimer 手中除 discard_tile 外需要的牌（chi=2张, pon=2张, daiminkan=3张）
    stage: "chi" 或 "pon_kan"

    返回: (board, meld) 其中 meld 是构造好的副露对象
    """
    b0 = board_sorted_deal(dealer=dealer)
    pool = pool_not_in_wall(b0)

    # claimer 手牌 = discard_tile（鸣牌用副本）+ claimer_extra_tiles + 补充到 13 张
    claimer_hand = Counter()
    claimer_hand[discard_tile] += 1  # 鸣牌用副本
    pool[discard_tile] -= 1
    if pool[discard_tile] == 0:
        del pool[discard_tile]
    for t in claimer_extra_tiles:
        claimer_hand[t] += 1
        pool[t] -= 1
        if pool[t] == 0:
            del pool[t]
    while sum(claimer_hand.values()) < 13:
        t = next(iter(pool.elements()))
        claimer_hand[t] += 1
        pool[t] -= 1
        if pool[t] == 0:
            del pool[t]

    # discarder: 从 pool 取 14 张（含 discard_tile），打出 discard_tile 后剩 13 张
    hand_discarder = take_n(pool, 14)
    # 确保 hand_discarder 含 discard_tile
    if hand_discarder[discard_tile] < 1:
        # 用一张 filler 替换
        filler = next(t for t in hand_discarder if t != discard_tile)
        hand_discarder[filler] -= 1
        if hand_discarder[filler] == 0:
            del hand_discarder[filler]
        hand_discarder[discard_tile] += 1
    # 打出 discard_tile
    hand_discarder[discard_tile] -= 1
    if hand_discarder[discard_tile] == 0:
        del hand_discarder[discard_tile]

    # 其他座位
    hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == discarder:
            hands.append(hand_discarder)
        elif s == claimer:
            hands.append(claimer_hand)
        else:
            hands.append(take_n(pool, 13))

    # 构造 meld
    n_extra = len(claimer_extra_tiles)
    def _sort_tiles(tiles: tuple[Tile, ...]) -> tuple[Tile, ...]:
        return tuple(sorted(tiles, key=lambda t: (t.suit.value, t.rank, t.is_red)))

    if n_extra == 2 and stage == "chi":
        meld_tiles = _sort_tiles((discard_tile,) + tuple(claimer_extra_tiles))
        meld = Meld(kind=MeldKind.CHI, tiles=meld_tiles, called_tile=discard_tile)
    elif n_extra == 2:
        meld_tiles = _sort_tiles((discard_tile,) + tuple(claimer_extra_tiles))
        meld = Meld(kind=MeldKind.PON, tiles=meld_tiles, called_tile=discard_tile)
    elif n_extra == 3:
        meld_tiles = _sort_tiles((discard_tile,) + tuple(claimer_extra_tiles))
        meld = Meld(kind=MeldKind.DAIMINKAN, tiles=meld_tiles, called_tile=discard_tile)
    else:
        raise ValueError(f"unsupported extra_tiles count: {n_extra}")

    # 构造 river 和 call_state
    entry = RiverEntry(seat=discarder, tile=discard_tile, tsumogiri=False, riichi=False)
    new_river = b0.river + (entry,)
    new_disc = list(b0.all_discards_per_seat)
    new_disc[discarder] = b0.all_discards_per_seat[discarder] + (discard_tile,)
    river_index = len(new_river) - 1

    o1 = (discarder + 1) % 4
    o2 = (discarder + 2) % 4
    o3 = (discarder + 3) % 4

    if stage == "chi":
        cs = CallResolution(
            discard_seat=discarder,
            claimed_tile=discard_tile,
            river_index=river_index,
            stage="chi",
            ron_remaining=frozenset(),
            ron_claimants=frozenset(),
            pon_kan_order=(o1, o2, o3),
            pon_kan_idx=3,
            finished=False,
        )
    else:
        pon_kan_idx = list((o1, o2, o3)).index(claimer)
        cs = CallResolution(
            discard_seat=discarder,
            claimed_tile=discard_tile,
            river_index=river_index,
            stage="pon_kan",
            ron_remaining=frozenset(),
            ron_claimants=frozenset(),
            pon_kan_order=(o1, o2, o3),
            pon_kan_idx=pon_kan_idx,
            finished=False,
        )

    board = BoardState(
        hands=tuple(hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=claimer,
        turn_phase=TurnPhase.CALL_RESPONSE,
        river=new_river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=0,
        call_state=cs,
        riichi=(False, False, False, False),
        ippatsu_eligible=frozenset(),
        double_riichi=frozenset(),
        all_discards_per_seat=tuple(new_disc),
        called_discard_indices=b0.called_discard_indices,
    )

    return board, meld
