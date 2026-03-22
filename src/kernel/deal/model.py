"""配牌后的牌桌子状态（手牌、剩余本墙、王牌、表宝指示牌）。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from kernel.hand.melds import Meld, meld_tile_count, validate_meld_shape
from kernel.hand.validate import validate_tile_conservation
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.tiles.model import Tile
from kernel.wall.split import LIVE_WALL_SIZE, DeadWall

# 开局从本墙取牌张数：三轮 16×3 + 一轮 4 + 亲多 1
INITIAL_DEAL_TILES = 53
# 配牌后本墙剩余：122 - 53
LIVE_WALL_AFTER_DEAL = LIVE_WALL_SIZE - INITIAL_DEAL_TILES

# 表宝指示牌：与 ``DeadWall.indicators`` 顺序一致，先翻开第 1 张（下标 0）
FIRST_DORA_INDICATOR_INDEX = 0


def _seat_meld_tile_sum(melds: tuple[Meld, ...]) -> int:
    return sum(meld_tile_count(m) for m in melds)


def _seat_total_tiles(concealed: Counter[Tile], melds: tuple[Meld, ...]) -> int:
    return sum(concealed.values()) + _seat_meld_tile_sum(melds)


@dataclass(frozen=True, slots=True)
class BoardState:
    """
    一局进行中与牌山相关的快照。

    ``live_wall`` 为配牌后剩余本墙；``live_draw_index`` 指向下一张要摸的牌。
    ``current_seat`` / ``turn_phase`` 描述摸打主循环；``river`` 为舍牌顺序。
    """

    hands: tuple[Counter[Tile], Counter[Tile], Counter[Tile], Counter[Tile]]
    live_wall: tuple[Tile, ...]
    live_draw_index: int
    dead_wall: DeadWall
    revealed_indicators: tuple[Tile, ...]
    current_seat: int
    turn_phase: TurnPhase
    river: tuple[RiverEntry, ...]
    melds: tuple[tuple[Meld, ...], tuple[Meld, ...], tuple[Meld, ...], tuple[Meld, ...]] = (
        (),
        (),
        (),
        (),
    )
    last_draw_tile: Tile | None = None
    """当前行动家上一张自摸（用于判定摸切）；非自摸后打牌阶段可为 ``None``。"""
    call_state: CallResolution | None = None
    """非空当且仅当 ``turn_phase == CALL_RESPONSE``。"""

    def __post_init__(self) -> None:
        validate_board_state(self)


def validate_board_state(board: BoardState) -> None:
    """校验张数守恒、本墙游标与门内+副露的 13/14 规则。"""
    if not 0 <= board.current_seat <= 3:
        msg = "current_seat must be 0..3"
        raise ValueError(msg)
    if len(board.live_wall) != LIVE_WALL_AFTER_DEAL:
        msg = f"live_wall must have length {LIVE_WALL_AFTER_DEAL}"
        raise ValueError(msg)
    if not 0 <= board.live_draw_index <= len(board.live_wall):
        msg = "live_draw_index out of range for live_wall"
        raise ValueError(msg)
    if len(board.revealed_indicators) < 1:
        msg = "revealed_indicators must be non-empty"
        raise ValueError(msg)

    for s in range(4):
        for m in board.melds[s]:
            validate_meld_shape(m)

    in_concealed = sum(sum(h.values()) for h in board.hands)
    in_melds = sum(_seat_meld_tile_sum(board.melds[s]) for s in range(4))
    river_n = len(board.river)
    live_remaining = len(board.live_wall) - board.live_draw_index
    dead_n = len(board.dead_wall.rinshan) + len(board.dead_wall.indicators)
    if in_concealed + in_melds + river_n + live_remaining + dead_n != 136:
        msg = "tile count conservation violated (expected 136 total)"
        raise ValueError(msg)

    if (board.turn_phase == TurnPhase.CALL_RESPONSE) != (board.call_state is not None):
        msg = "CALL_RESPONSE phase requires non-None call_state and vice versa"
        raise ValueError(msg)

    cur = board.current_seat
    if board.turn_phase == TurnPhase.NEED_DRAW:
        for s in range(4):
            validate_tile_conservation(board.hands[s], board.melds[s], 13)
        if board.last_draw_tile is not None:
            msg = "last_draw_tile must be None in NEED_DRAW"
            raise ValueError(msg)
    elif board.turn_phase == TurnPhase.MUST_DISCARD:
        for s in range(4):
            want: int = 14 if s == cur else 13
            validate_tile_conservation(board.hands[s], board.melds[s], want)
    elif board.turn_phase == TurnPhase.CALL_RESPONSE:
        cs = board.call_state
        assert cs is not None
        if not board.river:
            msg = "CALL_RESPONSE requires non-empty river"
            raise ValueError(msg)
        if cs.river_index != len(board.river) - 1:
            msg = "call_state.river_index must point to last river discard"
            raise ValueError(msg)
        if board.river[cs.river_index].tile != cs.claimed_tile:
            msg = "claimed_tile must match river at river_index"
            raise ValueError(msg)
        for s in range(4):
            validate_tile_conservation(board.hands[s], board.melds[s], 13)
        if board.last_draw_tile is not None:
            msg = "last_draw_tile must be None in CALL_RESPONSE"
            raise ValueError(msg)
        if cs.finished and not cs.ron_claimants:
            msg = "finished call_state requires non-empty ron_claimants"
            raise ValueError(msg)
    else:
        msg = f"unknown turn phase: {board.turn_phase!r}"
        raise ValueError(msg)
