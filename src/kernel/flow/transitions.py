"""流局判定逻辑：荒牌、九种九牌、四风连打、四杠散、四家立直、三家和。"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from kernel.flow.model import FlowKind, FlowResult
from kernel.tiles.model import Suit, Tile

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


def is_exhausted_flow(board: "BoardState") -> bool:
    """
    荒牌流局判定：本墙已摸完（``live_draw_index >= len(live_wall)``）。
    注意：实际行牌中，荒牌时 ``live_draw_index`` 会等于 ``len(live_wall)``，
    下一家摸牌时会触发「无法摸牌」状态。
    """
    return board.live_draw_index >= len(board.live_wall)


def is_nine_nine_flow(concealed_13: Counter[Tile]) -> bool:
    """
    九种九牌判定：配牌后，门内幺九牌（1/9）+ 字牌的种类数≥9。

    注意：只计算种类（key 的数量），不计算总张数。
    赤五不算幺九牌。
    """
    kinds = set()
    for t in concealed_13.keys():
        if t.suit == Suit.HONOR:
            kinds.add(("honor", t.rank))
        elif t.rank in (1, 9):
            kinds.add((t.suit, t.rank))
    return len(kinds) >= 9


def is_four_winds_flow(river_tiles: list[Tile]) -> bool:
    """
    四风连打判定：开局 4 家连续打出相同的风牌。

    ``river_tiles``: 按顺序存储前 4 张舍牌的列表。
    条件：
    - 恰好 4 张牌
    - 全部为字牌
    - 全部为相同 rank（东/南/西/北）
    """
    if len(river_tiles) != 4:
        return False
    first = river_tiles[0]
    if first.suit != Suit.HONOR:
        return False
    if first.rank not in (1, 2, 3, 4):
        return False
    for t in river_tiles[1:]:
        if t.suit != Suit.HONOR or t.rank != first.rank:
            return False
    return True


def is_four_kans_flow(kan_counts: tuple[int, int, int, int] | int) -> bool:
    """
    四杠散了流局判定：不同玩家合计完成 4 个杠，且无单一玩家独占 4 杠。

    ``kan_counts``: 各家已完成的杠数元组（暗杠 + 大明杠 + 加杠）。

    规则：
    - 同一家开 4 杠 → 不流局（该玩家达成四杠子役满），其他人不能再杠
    - 不同家合计开杠达到 4 次 → 四杠散了流局
    """
    if isinstance(kan_counts, int):
        # 向后兼容：单一整数视为全局计数（无法区分一人四杠）
        return kan_counts >= 4
    total = sum(kan_counts)
    if total < 4:
        return False
    # 任何一家达到 4 杠 → 一人四杠（役满），不流局
    if any(count >= 4 for count in kan_counts):
        return False
    return True


def is_four_riichi_flow(riichi_state: tuple[bool, bool, bool, bool]) -> bool:
    """
    四家立直判定：4 家均已宣言立直。

    ``riichi_state``: 长度为 4 的布尔元组，表示各家立直状态。
    """
    return all(riichi_state)


def is_three_ron_flow(ron_claimants: frozenset[int]) -> bool:
    """
    三家和流局判定：同张舍牌被 3 家同时荣和。

    ``ron_claimants``: 荣和者集合。
    """
    return len(ron_claimants) == 3


def check_flow_kind(
    board: "BoardState",
    kan_count: int = 0,
    kan_counts: tuple[int, int, int, int] = (0, 0, 0, 0),
    ron_claimants: frozenset[int] = frozenset(),
    riichi_state: tuple[bool, bool, bool, bool] = (False, False, False, False),
    first_4_river: list[Tile] | None = None,
) -> FlowResult | None:
    """
    综合检查当前状态是否流局，返回流局种类。

    优先级（按检测顺序）：
    1. 三家和（荣和结算时发现 3 家）
    2. 四家立直（第 4 家立直后）
    3. 四杠散（第 4 个杠完成后）
    4. 四风连打（开局前 4 张舍牌）
    5. 九种九牌（配牌后宣言，需外部调用）
    6. 荒牌（本墙摸完）

    若未流局，返回 ``None``。
    """
    # 三家和
    if is_three_ron_flow(ron_claimants):
        return FlowResult(
            kind=FlowKind.THREE_RON,
            ron_claimants=ron_claimants,
        )

    # 四家立直
    if is_four_riichi_flow(riichi_state):
        return FlowResult(kind=FlowKind.FOUR_RIICHI)

    # 四杠散（优先使用 per-seat 计数，向后兼容 kan_count）
    effective_kan_counts = kan_counts if any(kan_counts) else (kan_count, 0, 0, 0)
    if is_four_kans_flow(effective_kan_counts):
        return FlowResult(kind=FlowKind.FOUR_KANS, kan_count=sum(effective_kan_counts))

    # 四风连打
    if first_4_river and is_four_winds_flow(first_4_river):
        return FlowResult(kind=FlowKind.FOUR_WINDS)

    # 荒牌
    if is_exhausted_flow(board):
        return FlowResult(kind=FlowKind.EXHAUSTED)

    return None


def check_nine_nine_declaration(concealed_13: Counter[Tile]) -> bool:
    """
    九种九牌宣言检测：配牌后，门内幺九牌 + 字牌≥9 种时可宣言流局。

    由外部（如引擎）在配牌后、亲家第 1 摸前调用。
    """
    return is_nine_nine_flow(concealed_13)
