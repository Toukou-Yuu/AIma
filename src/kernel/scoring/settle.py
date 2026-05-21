"""荣和后的点棒与供托结算（扩展子集）。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel.board import BoardState
from kernel.event_log import WinSettlementLine
from kernel.hand.melds import Meld
from kernel.scoring.dora import count_aka_dora, count_dora_total, count_ura_dora_total
from kernel.scoring.fu import compute_fu_detail
from kernel.scoring.points import child_ron_payment_from_discarder, child_tsumo_payments
from kernel.scoring.yaku import (
    hand_pattern_label,
    is_kokushi_musou,
    is_kokushi_thirteen_waits,
    prevailing_wind_tile,
    non_dora_yaku_han_and_labels,
    _is_menzen,
)
from kernel.table.model import TableSnapshot, seat_wind_rank
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.pinfu import pinfu_eligible


def _is_haitei(board: BoardState) -> bool:
    """是否海底（本墙已摸完）。"""
    return board.live_draw_index >= len(board.live_wall)


def _is_hotei(board: BoardState, discard_seat: int) -> bool:
    """是否河底（本墙已摸完时的舍牌）。"""
    return board.live_draw_index >= len(board.live_wall)


def settle_ron_table(
    table: TableSnapshot,
    board: BoardState,
    *,
    ron_winners: frozenset[int],
    discard_seat: int,
    win_tile: Tile,
    ura_indicators: tuple[Tile, ...] = (),
    allow_open_tanyao: bool = True,
    red_dora_enabled: bool = True,
    is_chankan: bool = False,
) -> tuple[TableSnapshot, tuple[WinSettlementLine, ...], tuple[int, int, int, int]]:
    """
    一炮多响：每位和了者从放铳家收取完整荣和点（含本场）；供托清零并按席位数整数分给和了者。

    返回 ``(新场况, 和了明细行, 各家点棒本局增减)``。

    注意：本场数（honba）由调用方通过 ``update_honba`` 更新。
    """
    if not ron_winners:
        msg = "ron_winners must be non-empty"
        raise ValueError(msg)
    if not 0 <= discard_seat <= 3:
        msg = "discard_seat must be 0..3"
        raise ValueError(msg)

    old_scores = table.scores
    scores = list(table.scores)
    winners_sorted = tuple(sorted(ron_winners))
    built: list[WinSettlementLine] = []

    for w in winners_sorted:
        if not 0 <= w <= 3:
            msg = "winner seat must be 0..3"
            raise ValueError(msg)
        menzen = _is_menzen(board.melds[w])
        rw = prevailing_wind_tile(table.prevailing_wind)
        sw = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, w))

        from kernel.call.win import can_ron_seven_pairs

        is_chiitoitsu = can_ron_seven_pairs(board.hands[w], board.melds[w], win_tile)

        pf = pinfu_eligible(
            board.hands[w],
            board.melds[w],
            win_tile,
            for_ron=True,
            round_wind_tile=rw,
            seat_wind_tile=sw,
        )

        fu_detail = compute_fu_detail(
            board.hands[w],
            board.melds[w],
            win_tile,
            for_ron=True,
            menzen=menzen,
            pinfu=pf,
            self_wind=sw,
            round_wind=rw,
            is_chiitoitsu=is_chiitoitsu,
        )
        fu = fu_detail["total"]

        is_hotei = _is_hotei(board, discard_seat)

        nd_han, nd_labels = non_dora_yaku_han_and_labels(
            board,
            table,
            w,
            for_ron=True,
            win_tile=win_tile,
            concealed=board.hands[w],
            melds=board.melds[w],
            allow_open_tanyao=allow_open_tanyao,
            last_draw_was_rinshan=False,
            is_haitei=_is_haitei(board),
            is_hotei=is_hotei,
            is_chankan=is_chankan,
            is_tsumo=False,
        )
        if nd_han < 1:
            msg = "荣和须至少一番役（ドラ不可单独计和）"
            raise ValueError(msg)
        dora_h = count_dora_total(
            board.hands[w],
            board.melds[w],
            win_tile,
            for_ron=True,
            revealed_indicators=board.revealed_indicators,
        )
        ura_h = 0
        if board.riichi[w] and ura_indicators:
            ura_h = count_ura_dora_total(
                board.hands[w],
                board.melds[w],
                win_tile,
                for_ron=True,
                ura_indicators=ura_indicators,
            )
        aka_h = count_aka_dora(
            board.hands[w],
            board.melds[w],
            win_tile,
            for_ron=True,
            enabled=red_dora_enabled,
        )
        han = nd_han + dora_h + ura_h + aka_h

        yakus_list = list(nd_labels)
        if dora_h:
            yakus_list.append(f"表宝牌{dora_h}")
        if ura_h:
            yakus_list.append(f"里宝牌{ura_h}")
        if aka_h:
            yakus_list.append(f"赤宝牌{aka_h}")

        pay = child_ron_payment_from_discarder(
            w,
            discard_seat,
            table.dealer_seat,
            fu,
            han,
            table.honba,
        )
        scores[discard_seat] -= pay
        scores[w] += pay

        pattern = hand_pattern_label(board.hands[w], board.melds[w], win_tile, for_ron=True)
        built.append(
            WinSettlementLine(
                seat=w,
                win_kind="ron",
                han=han,
                fu=fu,
                hand_pattern=pattern,
                yakus=tuple(yakus_list),
                discard_seat=discard_seat,
                payment_from_discarder=pay,
                tsumo_deltas=None,
                kyoutaku_share=0,
                points=pay,
            )
        )

    kt = table.kyoutaku
    if kt:
        n = len(winners_sorted)
        base = kt // n
        rem = kt % n
        for i, w in enumerate(winners_sorted):
            share = base + (1 if i < rem else 0)
            scores[w] += share
            prev = built[i]
            built[i] = WinSettlementLine(
                seat=prev.seat,
                win_kind=prev.win_kind,
                han=prev.han,
                fu=prev.fu,
                hand_pattern=prev.hand_pattern,
                yakus=prev.yakus,
                discard_seat=prev.discard_seat,
                payment_from_discarder=prev.payment_from_discarder,
                tsumo_deltas=prev.tsumo_deltas,
                kyoutaku_share=share,
                points=prev.points + share,
            )

    new_table = replace(table, scores=tuple(scores), kyoutaku=0)
    payments = tuple(new_table.scores[i] - old_scores[i] for i in range(4))
    return new_table, tuple(built), payments


def settle_tsumo_table(
    table: TableSnapshot,
    board: BoardState,
    *,
    winner: int,
    win_tile: Tile,
    ura_indicators: tuple[Tile, ...] = (),
    allow_open_tanyao: bool = True,
    red_dora_enabled: bool = True,
) -> tuple[TableSnapshot, tuple[WinSettlementLine, ...], tuple[int, int, int, int]]:
    """自摸：三家点棒按子/亲公式；供托归和了者。

    返回 ``(新场况, 和了明细行, 各家点棒本局增减)``。

    注意：本场数（honba）由调用方通过 ``update_honba`` 更新。
    """
    if not 0 <= winner <= 3:
        msg = "winner must be 0..3"
        raise ValueError(msg)

    old_scores = table.scores
    menzen = _is_menzen(board.melds[winner])
    rw = prevailing_wind_tile(table.prevailing_wind)
    sw = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, winner))

    from kernel.call.win import can_win_seven_pairs_concealed_14

    is_chiitoitsu = can_win_seven_pairs_concealed_14(board.hands[winner], board.melds[winner])

    pf = pinfu_eligible(
        board.hands[winner],
        board.melds[winner],
        win_tile,
        for_ron=False,
        round_wind_tile=rw,
        seat_wind_tile=sw,
    )

    fu_detail = compute_fu_detail(
        board.hands[winner],
        board.melds[winner],
        win_tile,
        for_ron=False,
        menzen=menzen,
        pinfu=pf,
        self_wind=sw,
        round_wind=rw,
        is_chiitoitsu=is_chiitoitsu,
    )
    fu = fu_detail["total"]

    is_rinshan = board.last_draw_was_rinshan
    is_haitei = _is_haitei(board)

    nd_han, nd_labels = non_dora_yaku_han_and_labels(
        board,
        table,
        winner,
        for_ron=False,
        win_tile=win_tile,
        concealed=board.hands[winner],
        melds=board.melds[winner],
        allow_open_tanyao=allow_open_tanyao,
        last_draw_was_rinshan=is_rinshan,
        is_haitei=is_haitei,
        is_hotei=False,
        is_chankan=False,
        is_tsumo=True,
    )
    if nd_han < 1:
        msg = "自摸须至少一番役（ドラ不可单独计和）"
        raise ValueError(msg)
    dora_h = count_dora_total(
        board.hands[winner],
        board.melds[winner],
        win_tile,
        for_ron=False,
        revealed_indicators=board.revealed_indicators,
    )
    ura_h = 0
    if board.riichi[winner] and ura_indicators:
        ura_h = count_ura_dora_total(
            board.hands[winner],
            board.melds[winner],
            win_tile,
            for_ron=False,
            ura_indicators=ura_indicators,
        )
    aka_h = count_aka_dora(
        board.hands[winner],
        board.melds[winner],
        win_tile,
        for_ron=False,
        enabled=red_dora_enabled,
    )
    han = nd_han + dora_h + ura_h + aka_h

    yakus_list = list(nd_labels)
    if dora_h:
        yakus_list.append(f"表宝牌{dora_h}")
    if ura_h:
        yakus_list.append(f"里宝牌{ura_h}")
    if aka_h:
        yakus_list.append(f"赤宝牌{aka_h}")

    deltas = child_tsumo_payments(
        winner,
        table.dealer_seat,
        fu,
        han,
        table.honba,
    )
    scores = list(table.scores)
    for s in range(4):
        scores[s] += deltas[s]

    kt = table.kyoutaku
    if kt:
        scores[winner] += kt

    # child_tsumo_payments 已含本场；和了者净得（含三家支付）+ 供托
    points_line = deltas[winner] + kt

    pattern = hand_pattern_label(board.hands[winner], board.melds[winner], win_tile, for_ron=False)
    line = WinSettlementLine(
        seat=winner,
        win_kind="tsumo",
        han=han,
        fu=fu,
        hand_pattern=pattern,
        yakus=tuple(yakus_list),
        discard_seat=None,
        payment_from_discarder=None,
        tsumo_deltas=tuple(deltas),
        kyoutaku_share=kt,
        points=points_line,
    )

    new_table = replace(table, scores=tuple(scores), kyoutaku=0)
    payments = tuple(new_table.scores[i] - old_scores[i] for i in range(4))
    return new_table, (line,), payments
