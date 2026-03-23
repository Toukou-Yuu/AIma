"""荣和后的点棒与供托结算（扩展子集）。"""

from __future__ import annotations

from dataclasses import replace

from kernel.deal.model import BoardState
from kernel.scoring.dora import count_dora_total, count_ura_dora_total
from kernel.scoring.fu import compute_fu, compute_fu_detail
from kernel.win_shape.pinfu import pinfu_eligible
from kernel.scoring.points import child_ron_payment_from_discarder, child_tsumo_payments
from kernel.scoring.yaku import _prevailing_wind_tile, count_yaku_han
from kernel.table.model import TableSnapshot, seat_wind_rank
from kernel.tiles.model import Suit, Tile


def _is_haitei(board: BoardState) -> bool:
    """是否海底（本墙已摸完）。"""
    return board.live_draw_index >= len(board.live_wall)


def _is_hotei(board: BoardState, discard_seat: int) -> bool:
    """
    是否河底（某席的舍牌已是该席最后一张打出的牌）。
    简化判定：河中该席舍牌数 = 该席应打总数 - 1。
    """
    # 简化：检查 discard_seat 的河牌数是否为最后一张
    river_count = sum(1 for e in board.river if e.seat == discard_seat)
    # 标准局：每家应打 13-14 张，这里简化为河底 = 最后一张舍牌
    # 更精确的判定需要跟踪该局已进行的巡目
    return river_count >= 17  # 近似判定


def settle_ron_table(
    table: TableSnapshot,
    board: BoardState,
    *,
    ron_winners: frozenset[int],
    discard_seat: int,
    win_tile: Tile,
    ura_indicators: tuple[Tile, ...] = (),
    allow_open_tanyao: bool = True,
    is_chankan: bool = False,
    continue_dealer: bool = False,  # 新增：连庄判定结果
) -> TableSnapshot:
    """
    一炮多响：每位和了者从放铳家收取完整荣和点（含本场）；供托清零并按席位数整数分给和了者。
    里宝仅在和了者已立直时计入（``ura_indicators`` 非空时生效）。
    抢杠：``is_chankan=True`` 时计抢杠役。

    **连庄判定**：
    - ``continue_dealer=True``：本场 +1（亲家和了或流局亲听牌）
    - ``continue_dealer=False``：本场重置为 0（亲流）
    """
    if not ron_winners:
        msg = "ron_winners must be non-empty"
        raise ValueError(msg)
    if not 0 <= discard_seat <= 3:
        msg = "discard_seat must be 0..3"
        raise ValueError(msg)

    scores = list(table.scores)
    winners_sorted = tuple(sorted(ron_winners))

    for w in winners_sorted:
        if not 0 <= w <= 3:
            msg = "winner seat must be 0..3"
            raise ValueError(msg)
        menzen = len(board.melds[w]) == 0
        rw = _prevailing_wind_tile(table.prevailing_wind)
        sw = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, w))

        # 检测七对子
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

        # 使用完整符计算
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

        # 河底捞鱼判定
        is_hotei = _is_hotei(board, discard_seat)

        han = count_yaku_han(
            board,
            table,
            w,
            for_ron=True,
            win_tile=win_tile,
            concealed=board.hands[w],
            melds=board.melds[w],
            allow_open_tanyao=allow_open_tanyao,
            last_draw_was_rinshan=False,  # 荣和不是岭上
            is_haitei=False,  # 荣和不是海底
            is_hotei=is_hotei,
            is_chankan=is_chankan,
            is_tsumo=False,  # 荣和
        )
        han += count_dora_total(
            board.hands[w],
            board.melds[w],
            win_tile,
            for_ron=True,
            revealed_indicators=board.revealed_indicators,
        )
        if board.riichi[w] and ura_indicators:
            han += count_ura_dora_total(
                board.hands[w],
                board.melds[w],
                win_tile,
                for_ron=True,
                ura_indicators=ura_indicators,
            )
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

    kt = table.kyoutaku
    if kt:
        n = len(winners_sorted)
        base = kt // n
        rem = kt % n
        for i, w in enumerate(winners_sorted):
            scores[w] += base + (1 if i < rem else 0)

    # 本场更新：连庄时 +1，亲流时重置
    new_honba = table.honba + 1 if continue_dealer else 0

    return replace(table, scores=tuple(scores), kyoutaku=0, honba=new_honba)


def settle_tsumo_table(
    table: TableSnapshot,
    board: BoardState,
    *,
    winner: int,
    win_tile: Tile,
    ura_indicators: tuple[Tile, ...] = (),
    allow_open_tanyao: bool = True,
    continue_dealer: bool = False,  # 新增：连庄判定结果
) -> TableSnapshot:
    """自摸：三家点棒按子/亲公式；供托归和了者（整数根按席均分余数）。

    **连庄判定**：
    - ``continue_dealer=True``：本场 +1（亲家和了）
    - ``continue_dealer=False``：本场重置为 0（亲流）
    """
    if not 0 <= winner <= 3:
        msg = "winner must be 0..3"
        raise ValueError(msg)

    menzen = len(board.melds[winner]) == 0
    rw = _prevailing_wind_tile(table.prevailing_wind)
    sw = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, winner))

    # 检测七对子
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

    # 使用完整符计算
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

    # 岭上/海底判定
    is_rinshan = board.last_draw_was_rinshan
    is_haitei = _is_haitei(board)

    han = count_yaku_han(
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
        is_hotei=False,  # 自摸不是河底
        is_chankan=False,  # 自摸不是抢杠
        is_tsumo=True,  # 自摸
    )
    han += count_dora_total(
        board.hands[winner],
        board.melds[winner],
        win_tile,
        for_ron=False,
        revealed_indicators=board.revealed_indicators,
    )
    if board.riichi[winner] and ura_indicators:
        han += count_ura_dora_total(
            board.hands[winner],
            board.melds[winner],
            win_tile,
            for_ron=False,
            ura_indicators=ura_indicators,
        )

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

    # 本场更新：连庄时 +1，亲流时重置
    new_honba = table.honba + 1 if continue_dealer else 0

    return replace(table, scores=tuple(scores), kyoutaku=0, honba=new_honba)
