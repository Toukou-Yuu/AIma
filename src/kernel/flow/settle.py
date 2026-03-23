"""流局结算：听牌判定、供托处理、本场数更新、连庄/亲流判定；流局满贯。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel.call.win import can_ron_default, can_ron_seven_pairs
from kernel.config import DEFAULT_CONFIG, MahjongConfig
from kernel.deal.model import BoardState
from kernel.flow.model import TenpaiResult
from kernel.riichi.tenpai import _iter_ron_candidate_tiles, is_tenpai_default
from kernel.scoring.yaku import count_yaku_han
from kernel.table.model import PrevailingWind, TableSnapshot, seat_wind_rank
from kernel.tiles.model import Suit, Tile

if TYPE_CHECKING:
    pass


# 听牌支付点数（默认 1000 点）
TENPAI_PAYMENT_POINTS = 1000


def _has_yaku_with_win_tile(
    board: BoardState,
    table: TableSnapshot,
    seat: int,
    win_tile: Tile,
) -> bool:
    """
    检查和了牌为 win_tile 时是否有役（至少 1 番）。

    流局满贯判定用：假设自摸/荣和 win_tile 时检查役种。
    """
    concealed = board.hands[seat]
    melds = board.melds[seat]

    # 临时 TableSnapshot 用于役判定
    rw = PrevailingWind.EAST  # 简化：场风默认东
    sw_tile = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, seat))

    # 检查七对子
    if can_ron_seven_pairs(concealed, melds, win_tile):
        han = count_yaku_han(
            board,
            table,
            seat,
            for_ron=True,
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=False,
        )
        return han >= 1

    # 检查标准形
    if can_ron_default(concealed, melds, win_tile):
        han = count_yaku_han(
            board,
            table,
            seat,
            for_ron=True,
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=False,
        )
        return han >= 1

    return False


def check_flow_mangan(
    board: BoardState,
    table: TableSnapshot,
    seat: int,
) -> bool:
    """
    流局满贯判定：荒牌流局时，听牌者手牌满足和了形（有役）。

    判定逻辑：
    1. 检查是否听牌
    2. 遍历所有待牌，检查是否存在至少一张牌使手牌「和了形 + 有役」

    返回：是否流局满贯。
    """
    # 1. 检查是否听牌
    if not is_tenpai_default(board.hands[seat], board.melds[seat]):
        return False

    # 2. 遍历待牌，检查是否有役
    for win_tile in _iter_ron_candidate_tiles():
        if _has_yaku_with_win_tile(board, table, seat, win_tile):
            return True

    return False


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
    流局满贯结算：听牌者中满足流局满贯条件者按满贯收取点数。

    规则：
    - 流局满贯者：从每个未听牌者收取满贯点数（8000/12000）
    - 未听牌者：支付给每个流局满贯者满贯点数
    - 听牌但未满贯者：不参与满贯结算（仅参与普通听牌结算）

    满贯点数：
    - 子家：8000 点
    - 亲家：12000 点

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
    noten_count = len(noten)

    for fm_seat in flow_mangan_seats:
        # 确定满贯点数（亲家 12000，子家 8000）
        mangan_points = 12_000 if fm_seat == table.dealer_seat else 8_000

        # 从每个未听牌者收取
        for n in noten:
            scores[n] -= mangan_points
            scores[fm_seat] += mangan_points

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
