"""流局结算：听牌判定、供托处理、本场数更新、连庄/亲流判定；流局满贯。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel.config import DEFAULT_CONFIG, MahjongConfig
from kernel.deal.model import BoardState
from kernel.flow.model import TenpaiResult
from kernel.riichi.tenpai import is_tenpai_default
from kernel.scoring.points import nagashi_mangan_payments
from kernel.table.model import TableSnapshot
from kernel.tiles.model import Suit, Tile

if TYPE_CHECKING:
    pass


# 听牌支付点数（默认 1000 点）
TENPAI_PAYMENT_POINTS = 1000


def _is_yaochu_tile(t: Tile) -> bool:
    """幺九：字牌或数牌的一、九（非赤五）。"""
    if t.suit == Suit.HONOR:
        return True
    return t.rank in (1, 9)


def check_flow_mangan(
    board: BoardState,
    _table: TableSnapshot,
    seat: int,
) -> bool:
    """
    流し満貫（流局满贯）判定。

    与「听牌且存在带役待牌」无关；标准条件为：
    1. 荒牌流局时该席 **听牌**；
    2. 本局 **全部舍牌**（打牌）均为幺九（一・九・字）；
    3. **没有任何舍牌被他家吃/碰/大明杠** 鸣走（暗杠/加杠/荣和不计）。

    ``_table`` 保留参数以兼容调用方，当前判定不依赖场况表。
    """
    if not is_tenpai_default(board.hands[seat], board.melds[seat]):
        return False
    disc = board.all_discards_per_seat[seat]
    if not disc:
        return False
    if board.called_discard_indices[seat]:
        return False
    return all(_is_yaochu_tile(t) for t in disc)


def compute_tenpai_result(
    board: "BoardState",
) -> TenpaiResult:
    """
    计算听牌结果：返回听牌者集合。

    听牌判定：``is_tenpai_default``（标准形或七对子听牌）。
    """
    tenpai_seats = set()
    tenpai_types = ["", "", "", ""]
    for s in range(4):
        if is_tenpai_default(board.hands[s], board.melds[s]):
            tenpai_seats.add(s)
            # 简化：暂不区分听牌类型
            tenpai_types[s] = "tenpai"
        else:
            tenpai_types[s] = "noten"
    return TenpaiResult(
        tenpai_seats=frozenset(tenpai_seats),
        tenpai_types=tuple(tenpai_types),
    )


def settle_tenpai(
    table: TableSnapshot,
    tenpai_result: TenpaiResult,
) -> TableSnapshot:
    """
    听牌结算：听牌者从每人 1000 点收取（未听牌者支付）。

    规则：
    - 听牌者：从每个未听牌者收取 1000 点
    - 未听牌者：支付给每个听牌者 1000 点
    - 无人听牌：不结算
    - 全部听牌：不结算（互相抵消）

    供托：流局时供托保留至下一局（``kyoutaku`` 不变）。
    """
    tenpai = tenpai_result.tenpai_seats
    noten = frozenset(s for s in range(4) if s not in tenpai)

    if not tenpai or not noten:
        # 无人听牌或全部听牌，不结算
        return table

    scores = list(table.scores)
    tenpai_count = len(tenpai)
    noten_count = len(noten)

    # 听牌者收取
    for t in tenpai:
        scores[t] += TENPAI_PAYMENT_POINTS * noten_count

    # 未听牌者支付
    for n in noten:
        scores[n] -= TENPAI_PAYMENT_POINTS * tenpai_count

    return replace(table, scores=tuple(scores))


def settle_flow_mangan(
    table: TableSnapshot,
    board: BoardState,
    tenpai_result: TenpaiResult,
    config: MahjongConfig = DEFAULT_CONFIG,
) -> TableSnapshot:
    """
    流し満貫（流局满贯）结算：满足「幺九舍牌且未被鸣牌」且听牌者，按**满贯自摸**分摊。

    点棒与 ``child_tsumo_payments(..., fu=30, han=5, honba)`` 一致（子合计 8000、亲合计 12000，
    由亲/子三家**分开**支付，非每家各付满额）。

    听牌但非流し満貫者：仅参与普通听牌料（``settle_tenpai``）。

    Args:
        table: 牌桌快照
        board: 牌局状态
        tenpai_result: 听牌结果
        config: 规则配置（默认使用雀魂标准配置）

    返回：结算后的 TableSnapshot。
    """
    if not config.flow_mangan_enabled:
        return table

    # 找出流局满贯者
    flow_mangan_seats = set()
    for s in tenpai_result.tenpai_seats:
        if check_flow_mangan(board, table, s):
            flow_mangan_seats.add(s)

    if not flow_mangan_seats:
        return table

    noten = frozenset(s for s in range(4) if s not in tenpai_result.tenpai_seats)
    if not noten:
        # 全部听牌，无未听牌者
        return table

    scores = list(table.scores)

    for fm_seat in flow_mangan_seats:
        deltas = nagashi_mangan_payments(
            fm_seat,
            table.dealer_seat,
            table.honba,
            noten,
        )
        for s in range(4):
            scores[s] += deltas[s]

    return replace(table, scores=tuple(scores))


def should_continue_dealer(
    table: TableSnapshot,
    tenpai_result: TenpaiResult,
    winner_seat: int | None = None,
) -> bool:
    """
    是否连庄（亲家继续）。

    规则（雀魂常见）：
    - 亲家和了：连庄
    - 亲家听牌（流局）：连庄
    - 否则：亲流

    ``winner_seat``: 和了者（若本局有和了）。
    ``tenpai_result``: 听牌结果（流局时使用）。
    """
    dealer = table.dealer_seat

    # 有和了者
    if winner_seat is not None:
        return winner_seat == dealer

    # 流局：亲家听牌则连庄
    if dealer in tenpai_result.tenpai_seats:
        return True

    return False


def update_honba(
    table: TableSnapshot,
    continue_dealer: bool,
) -> TableSnapshot:
    """
    本场数更新。

    规则：
    - 连庄（亲家继续）：本场 +1
    - 亲流：本场重置为 0
    """
    if continue_dealer:
        return replace(table, honba=table.honba + 1)
    else:
        return replace(table, honba=0)


def settle_flow(
    table: TableSnapshot,
    board: "BoardState",
    winner_seat: int | None = None,
    config: MahjongConfig = DEFAULT_CONFIG,
) -> tuple[TableSnapshot, TenpaiResult]:
    """
    流局综合结算。

    1. 计算听牌结果
    2. 听牌支付结算
    3. 流局满贯结算
    4. 连庄/亲流判定
    5. 本场数更新

    返回： ``(new_table, tenpai_result)``

    注意：供托 ``kyoutaku`` 保留至下一局（不结算）。

    Args:
        table: 牌桌快照
        board: 牌局状态
        winner_seat: 和了者（若本局有和了）
        config: 规则配置（默认使用雀魂标准配置）
    """
    # 1. 计算听牌结果
    tenpai_result = compute_tenpai_result(board)

    # 2. 听牌支付结算
    new_table = settle_tenpai(table, tenpai_result)

    # 3. 流局满贯结算
    new_table = settle_flow_mangan(new_table, board, tenpai_result, config)

    # 4. 连庄/亲流判定
    continue_dealer = should_continue_dealer(
        new_table,
        tenpai_result,
        winner_seat=winner_seat,
    )

    # 5. 本场数更新
    new_table = update_honba(new_table, continue_dealer)

    return new_table, tenpai_result
