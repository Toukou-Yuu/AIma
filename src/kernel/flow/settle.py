"""流局结算：听牌判定、供托处理、本场数更新、连庄/亲流判定。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel.flow.model import TenpaiResult
from kernel.riichi.tenpai import is_tenpai_default
from kernel.table.model import TableSnapshot

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


# 听牌支付点数（默认 1000 点）
TENPAI_PAYMENT_POINTS = 1000


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
) -> tuple[TableSnapshot, TenpaiResult]:
    """
    流局综合结算。

    1. 计算听牌结果
    2. 听牌支付结算
    3. 连庄/亲流判定
    4. 本场数更新

    返回： ``(new_table, tenpai_result)``

    注意：供托 ``kyoutaku`` 保留至下一局（不结算）。
    """
    # 1. 计算听牌结果
    tenpai_result = compute_tenpai_result(board)

    # 2. 听牌支付结算
    new_table = settle_tenpai(table, tenpai_result)

    # 3. 连庄/亲流判定
    continue_dealer = should_continue_dealer(
        new_table,
        tenpai_result,
        winner_seat=winner_seat,
    )

    # 4. 本场数更新
    new_table = update_honba(new_table, continue_dealer)

    return new_table, tenpai_result
