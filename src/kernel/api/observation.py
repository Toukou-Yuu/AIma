"""观测信息生成：``observation(state, seat, mode)``。

K14 核心模块：返回某席的观测信息，支持人类可见/调试全知两种模式。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from kernel.engine.phase import GamePhase
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    from collections.abc import Counter

    from kernel.deal.model import Meld
    from kernel.engine.state import GameState


@dataclass(frozen=True, slots=True)
class RiverEntry:
    """河中的牌。

    Attributes:
        tile: 牌
        seat: 打牌者座位
        is_tsumogiri: 是否摸切
        is_riichi: 是否立直宣言
    """

    tile: Tile
    seat: int
    is_tsumogiri: bool
    is_riichi: bool


@dataclass(frozen=True, slots=True)
class Observation:
    """某席的观测信息。

    Attributes:
        seat: 观测者座位
        phase: 对局阶段（``IN_ROUND`` / ``HAND_OVER`` / ``MATCH_END`` 等）
        hand: 自家手牌（人类模式：门清时完整，副露后含副露；全知模式：完整）
        melds: 自家副露
        river: 全局河（按时间序）
        dora_indicators: 表宝指示牌
        ura_indicators: 里宝指示牌（仅全知模式或自家立直后）
        riichi_state: 各家立直状态
        scores: 各家得分
        honba: 本场数
        kyoutaku: 供托数
        turn_seat: 当前摸打席
        last_discard: 最后一张舍牌
        last_discard_seat: 最后舍牌者
        wall_remaining: 剩余牌数（仅全知模式）
        dead_wall: 王牌信息（仅全知模式）
        hands_by_seat: 四家门前手牌（仅 debug；human 为 None，不暴露他家）
    """

    seat: int
    phase: GamePhase
    hand: Counter[Tile] | None
    melds: tuple[Meld, ...]
    river: tuple[RiverEntry, ...]
    dora_indicators: tuple[Tile, ...]
    ura_indicators: tuple[Tile, ...] | None
    riichi_state: tuple[bool, ...]
    scores: tuple[int, ...]
    honba: int
    kyoutaku: int
    turn_seat: int
    last_discard: Tile | None
    last_discard_seat: int | None
    wall_remaining: int | None
    dead_wall: tuple[Tile, ...] | None
    hands_by_seat: tuple[Counter[Tile], Counter[Tile], Counter[Tile], Counter[Tile]] | None


def observation(
    state: GameState,
    seat: int,
    mode: Literal["human", "debug"] = "human",
) -> Observation:
    """
    返回某席的观测信息。

    Args:
        state: 当前局面
        seat: 观测者座位
        mode: 观测模式
            - "human": 仅人类可见信息（他家手牌不可见）
            - "debug": 全知视角（含他家手牌、牌山、王牌等）

    Returns:
        观测信息

    Raises:
        ValueError: seat 不在 0..3 范围内，或 mode 不合法
    """
    if not 0 <= seat <= 3:
        msg = "seat must be 0..3"
        raise ValueError(msg)

    if mode not in ("human", "debug"):
        msg = "mode must be 'human' or 'debug'"
        raise ValueError(msg)

    board = state.board
    table = state.table
    phase = state.phase

    # 手牌信息
    hand = None
    melds = ()
    hands_by_seat: tuple[Counter[Tile], Counter[Tile], Counter[Tile], Counter[Tile]] | None = None
    if board is not None:
        hand = Counter(board.hands[seat].elements())
        melds = tuple(board.melds[seat])
        if mode == "debug":
            hands_by_seat = tuple(Counter(board.hands[s].elements()) for s in range(4))

    # 河信息
    river = ()
    if board is not None:
        river_entries = []
        for entry in board.river:
            river_entries.append(
                RiverEntry(
                    tile=entry.tile,
                    seat=entry.seat,
                    is_tsumogiri=entry.tsumogiri,
                    is_riichi=entry.riichi,
                )
            )
        river = tuple(river_entries)

    # 宝牌指示牌
    dora_indicators = ()
    ura_indicators = None
    if board is not None:
        dora_indicators = tuple(board.revealed_indicators)
        if mode == "debug":
            # 全知模式：可见里宝
            ura_indicators = tuple(board.dead_wall.ura_bases[: len(board.revealed_indicators)])
        elif board.riichi[seat]:
            # 立直后：可见里宝（和了后）
            # 简化：立直后即可见
            ura_indicators = tuple(board.dead_wall.ura_bases[: len(board.revealed_indicators)])

    # 立直状态
    riichi_state = tuple(board.riichi) if board is not None else (False, False, False, False)

    # 场况信息
    scores = table.scores
    honba = table.honba
    kyoutaku = table.kyoutaku

    # 当前行动席
    turn_seat = board.current_seat if board is not None else seat

    # 最后打牌
    last_discard = None
    last_discard_seat = None
    if board is not None and board.river:
        last_entry = board.river[-1]
        last_discard = last_entry.tile
        last_discard_seat = last_entry.seat

    # 剩余牌数（仅全知模式）
    wall_remaining = None
    if mode == "debug" and board is not None:
        wall_remaining = len(board.live_wall)

    # 王牌信息（仅全知模式）
    dead_wall = None
    if mode == "debug" and board is not None:
        dead_wall = board.dead_wall.rinshan + board.dead_wall.ura_bases + board.dead_wall.indicators

    return Observation(
        seat=seat,
        phase=phase,
        hand=hand,
        melds=melds,
        river=river,
        dora_indicators=dora_indicators,
        ura_indicators=ura_indicators,
        riichi_state=riichi_state,
        scores=scores,
        honba=honba,
        kyoutaku=kyoutaku,
        turn_seat=turn_seat,
        last_discard=last_discard,
        last_discard_seat=last_discard_seat,
        wall_remaining=wall_remaining,
        dead_wall=dead_wall,
        hands_by_seat=hands_by_seat,
    )
