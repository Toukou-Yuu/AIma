"""开局配牌：本墙 53 张分配、首张表宝指示牌。"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from kernel.deal.model import (
    FIRST_DORA_INDICATOR_INDEX,
    INITIAL_DEAL_TILES,
    BoardState,
)
from kernel.play.model import TurnPhase
from kernel.tiles.deck import build_deck
from kernel.tiles.model import Tile
from kernel.wall.split import LIVE_WALL_SIZE, WallSplit


def assert_wall_is_standard_deck(tiles: Sequence[Tile], *, red_fives: bool = True) -> None:
    """断言 ``tiles`` 与 ``build_deck(red_fives=...)`` 多重集合一致且长度为 136。"""
    if len(tiles) != 136:
        msg = f"wall must have length 136, got {len(tiles)}"
        raise ValueError(msg)
    c = Counter(tiles)
    ref = Counter(build_deck(red_fives=red_fives))
    if c != ref:
        msg = "wall multiset does not match standard deck for given red_fives option"
        raise ValueError(msg)


def build_board_after_split(wall_split: WallSplit, dealer_seat: int) -> BoardState:
    """
    对已切分的牌山做开局配牌。

    配牌顺序：从 ``live[0]`` 起按风位 ``dealer, dealer+1, …`` 循环；
    三轮每人 4 张，再每人 1 张，最后亲再多 1 张（共 53 张）。

    表宝指示牌：翻开 ``dead_wall.indicators[FIRST_DORA_INDICATOR_INDEX]``（当前为下标 0）。
    """
    if not 0 <= dealer_seat <= 3:
        msg = "dealer_seat must be 0..3"
        raise ValueError(msg)
    live = wall_split.live
    if len(live) != LIVE_WALL_SIZE:
        msg = f"live wall must have length {LIVE_WALL_SIZE}"
        raise ValueError(msg)

    idx = 0
    piles: list[list[Tile]] = [[], [], [], []]
    order = [(dealer_seat + i) % 4 for i in range(4)]

    for _ in range(3):
        for s in order:
            piles[s].extend(live[idx : idx + 4])
            idx += 4
    for s in order:
        piles[s].append(live[idx])
        idx += 1
    piles[dealer_seat].append(live[idx])
    idx += 1

    if idx != INITIAL_DEAL_TILES:
        msg = "internal deal index mismatch"
        raise RuntimeError(msg)

    live_tail = live[INITIAL_DEAL_TILES:]
    hands = tuple(Counter(p) for p in piles)
    ind = wall_split.dead.indicators[FIRST_DORA_INDICATOR_INDEX]
    revealed = (ind,)

    return BoardState(
        hands=hands,
        live_wall=tuple(live_tail),
        live_draw_index=0,
        dead_wall=wall_split.dead,
        revealed_indicators=revealed,
        current_seat=dealer_seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=(),
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=0,
    )
