"""局推进与终局判定：连庄/亲流、半庄/东风战终局、名次计算。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel.table.model import MatchPreset, PrevailingWind, RoundNumber, TableSnapshot

if TYPE_CHECKING:
    pass


def advance_round(
    table: TableSnapshot,
    continue_dealer: bool,
) -> TableSnapshot:
    """
    推进到下一局（更新场风、局序、亲席）。

    **注意**：本场数 ``honba`` 应由调用方预先更新（``settle_*_table`` 或 ``settle_flow``）。

    **连庄**（``continue_dealer=True``）:
    - 局序不变
    - 亲席不变
    - 场风不变

    **亲流**（``continue_dealer=False``）:
    - 局序 +1（若已到第四局则变更场风）
    - 亲席轮转（下家坐庄）
    - 场风可能变更（东四局→南一局）

    **场风流转移**:
    - 东四局 + 亲流 → 南一局
    - 南四局 + 亲流 → 终局（调用方应检查 ``should_match_end()``）
    """
    if continue_dealer:
        # 连庄：局序、亲席、场风均不变
        return table

    # 亲流：局序/场风/亲席变更
    new_round = table.round_number
    new_wind = table.prevailing_wind
    new_dealer = (table.dealer_seat + 1) % 4

    # 局序推进
    if table.round_number == RoundNumber.ONE:
        new_round = RoundNumber.TWO
    elif table.round_number == RoundNumber.TWO:
        new_round = RoundNumber.THREE
    elif table.round_number == RoundNumber.THREE:
        new_round = RoundNumber.FOUR
    elif table.round_number == RoundNumber.FOUR:
        # 第四局结束，考虑场风变更
        if table.prevailing_wind == PrevailingWind.EAST:
            # 东四局 → 南一局
            new_wind = PrevailingWind.SOUTH
            new_round = RoundNumber.ONE
        else:
            # 南四局 → 终局（调用方处理）
            new_round = RoundNumber.FOUR
            new_wind = PrevailingWind.SOUTH

    return replace(
        table,
        prevailing_wind=new_wind,
        round_number=new_round,
        dealer_seat=new_dealer,
    )


def should_match_end(table: TableSnapshot) -> bool:
    """
    判断是否满足终局条件。

    **半庄战**（``MatchPreset.HANCHAN``）:
    - 南四局结束（即当前为南四局且发生亲流）

    **东风战**（``MatchPreset.TONPUSEN``）:
    - 东四局结束（即当前为东四局且发生亲流）

    注意：本函数在**亲流后**调用，判断是否应终局。
    连庄时永不终局。
    """
    if table.match_preset == MatchPreset.TONPUSEN:
        # 东风战：东四局亲流后终局
        return (
            table.prevailing_wind == PrevailingWind.EAST and table.round_number == RoundNumber.FOUR
        )
    else:
        # 半庄战：南四局亲流后终局
        return (
            table.prevailing_wind == PrevailingWind.SOUTH and table.round_number == RoundNumber.FOUR
        )


def compute_match_ranking(table: TableSnapshot) -> tuple[int, ...]:
    """
    计算终局名次（按点棒排序）。

    返回 ``(1 位席次，2 位席次，3 位席次，4 位席次)``。

    **同分处理**：雀魂规则为并列（返回相同顺位）。
    例如：``scores = (25000, 25000, 20000, 30000)`` → ``(1, 1, 3, 0)``
    （席次 0 和 1 同分并列 1 位，席次 2 是 3 位，席次 3 是 4 位）

    算法：
    1. 按点棒降序排序席次
    2. 同分者赋予相同顺位
    """
    scores = table.scores

    # 创建 (分数，席次) 列表并按分数降序排序
    scored = [(scores[i], i) for i in range(4)]
    scored.sort(key=lambda x: (-x[0], x[1]))  # 分数降序，席次升序（break tie）

    # 计算顺位
    ranking = [0] * 4
    current_rank = 1
    prev_score = None

    for i, (score, seat) in enumerate(scored):
        if prev_score is not None and score < prev_score:
            current_rank = i + 1  # 顺位 = 当前索引 +1
        ranking[seat] = current_rank
        prev_score = score

    return tuple(ranking)


def final_settlement(
    table: TableSnapshot,
) -> tuple[tuple[int, ...], TableSnapshot]:
    """
    终局最终结算：计算名次并处理终局供托。

    **雀魂规则**：终局时供托归 1 位家。
    若 1 位多家并列，供托由并列者均分（向下取整，余数舍弃）。

    返回 ``(ranking, new_table)``：
    - ``ranking``: 名次元组（``compute_match_ranking()`` 结果）
    - ``new_table``: 供托处理后的场况

    注意：供托处理为可选规则，可通过配置禁用。
    """
    ranking = compute_match_ranking(table)

    # 确定 1 位
    first_place_rank = 1
    first_place_seats = [i for i, r in enumerate(ranking) if r == first_place_rank]

    # 供托均分给 1 位
    if first_place_seats and table.kyoutaku > 0:
        per_person = table.kyoutaku // len(first_place_seats)
        scores = list(table.scores)
        for seat in first_place_seats:
            scores[seat] += per_person
        table = replace(table, scores=tuple(scores), kyoutaku=0)

    return ranking, table
