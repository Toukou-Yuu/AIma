"""配牌后的牌桌子状态（手牌、剩余本墙、王牌、表宝指示牌）。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import FrozenSet

from kernel.hand.melds import Meld, meld_tile_count, validate_meld_shape
from kernel.hand.validate import validate_tile_conservation
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.tiles.model import Tile
from kernel.wall.split import (
    DEAD_INDICATOR_STOCK,
    INDICATOR_COUNT,
    LIVE_WALL_SIZE,
    RINSHAN_COUNT,
    DeadWall,
)

# 开局从本墙取牌张数：三轮 16×3 + 一轮 4 + 亲多 1
INITIAL_DEAL_TILES = 53
# 配牌后本墙剩余：122 - 53
LIVE_WALL_AFTER_DEAL = LIVE_WALL_SIZE - INITIAL_DEAL_TILES

# 表宝指示牌：与 ``DeadWall.indicators`` 顺序一致，先翻开第 1 张（下标 0）
FIRST_DORA_INDICATOR_INDEX = 0


def _empty_discards_per_seat() -> tuple[tuple[Tile, ...], ...]:
    """本局各家舍牌列表初值（四席各空）。"""
    return ((), (), (), ())


def _empty_called_indices_per_seat() -> tuple[frozenset[int], ...]:
    """``流し満貫`` 用：被吃/碰/大明杠鸣走的舍牌下标。"""
    return (frozenset(), frozenset(), frozenset(), frozenset())


def _seat_meld_tile_sum(melds: tuple[Meld, ...]) -> int:
    return sum(meld_tile_count(m) for m in melds)


def _seat_total_tiles(concealed: Counter[Tile], melds: tuple[Meld, ...]) -> int:
    return sum(concealed.values()) + _seat_meld_tile_sum(melds)


def _validate_seat_13_or_post_kan_discard_14(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
) -> None:
    """
    通常：门内+副露合计 13。
    例外：副露中含 4 张杠（含暗杠/大明杠/加杠）且合计 14 —— 与 NEED_DRAW 注释一致，
    表示「杠后岭摸已打出一张」之后、轮到他家摸打前的暂态。
    """
    tot = _seat_total_tiles(concealed, melds)
    has_quad_meld = any(meld_tile_count(m) == 4 for m in melds)
    if tot == 13:
        return
    if tot == 14 and has_quad_meld:
        return
    validate_tile_conservation(concealed, melds, 13)


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
    last_draw_was_rinshan: bool = False
    """上一张自摸是否来自岭上（杠后）；为真时 ``MUST_DISCARD`` 当前家须 15 张（须再打出一）。"""
    rinshan_draw_index: int = 0
    """已从 ``dead_wall.rinshan`` 顺序摸走的张数，下一张为 ``rinshan[rinshan_draw_index]``。"""
    call_state: CallResolution | None = None
    """非空当且仅当 ``turn_phase == CALL_RESPONSE``。"""
    riichi: tuple[bool, bool, bool, bool] = (False, False, False, False)
    """各席是否已宣言立直（不可逆）。"""
    ippatsu_eligible: FrozenSet[int] = frozenset()
    """尚处于一发机会内的立直席（鸣牌或荣和结算后清空）；供后续点数模块消费。"""
    double_riichi: FrozenSet[int] = frozenset()
    """双立直席（本局该席第一打即立直）；须同时为已立直席。"""
    all_discards_per_seat: tuple[tuple[Tile, ...], ...] = field(
        default_factory=_empty_discards_per_seat
    )
    """本局各席按顺序打出的牌（含已被吃碰大明杠从河移走的那张，仍计入本列表）。"""
    called_discard_indices: tuple[frozenset[int], ...] = field(
        default_factory=_empty_called_indices_per_seat
    )
    """各席 ``all_discards_per_seat[seat]`` 的下标：被他家吃/碰/大明杠鸣走的舍牌。"""

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
    if len(board.revealed_indicators) > INDICATOR_COUNT:
        msg = f"revealed_indicators length cannot exceed {INDICATOR_COUNT}"
        raise ValueError(msg)
    if not 0 <= board.rinshan_draw_index <= RINSHAN_COUNT:
        msg = "rinshan_draw_index out of range"
        raise ValueError(msg)
    if board.last_draw_was_rinshan and board.last_draw_tile is None:
        msg = "last_draw_was_rinshan requires last_draw_tile"
        raise ValueError(msg)

    for s in range(4):
        for m in board.melds[s]:
            validate_meld_shape(m)

    in_concealed = sum(sum(h.values()) for h in board.hands)
    in_melds = sum(_seat_meld_tile_sum(board.melds[s]) for s in range(4))
    river_n = len(board.river)
    live_remaining = len(board.live_wall) - board.live_draw_index
    rinshan_remaining = RINSHAN_COUNT - board.rinshan_draw_index
    dead_remaining = rinshan_remaining + DEAD_INDICATOR_STOCK
    if in_concealed + in_melds + river_n + live_remaining + dead_remaining != 136:
        msg = "tile count conservation violated (expected 136 total)"
        raise ValueError(msg)

    if (board.turn_phase == TurnPhase.CALL_RESPONSE) != (board.call_state is not None):
        msg = "CALL_RESPONSE phase requires non-None call_state and vice versa"
        raise ValueError(msg)

    if len(board.riichi) != 4:
        msg = "riichi must be a 4-tuple"
        raise ValueError(msg)
    for s in board.ippatsu_eligible:
        if not 0 <= s <= 3:
            msg = "ippatsu_eligible seats must be 0..3"
            raise ValueError(msg)
    for s in board.double_riichi:
        if not 0 <= s <= 3:
            msg = "double_riichi seats must be 0..3"
            raise ValueError(msg)
        if not board.riichi[s]:
            msg = "double_riichi seat must be riichi"
            raise ValueError(msg)

    if len(board.all_discards_per_seat) != 4 or len(board.called_discard_indices) != 4:
        msg = "all_discards_per_seat / called_discard_indices must have length 4"
        raise ValueError(msg)
    for s in range(4):
        for i in board.called_discard_indices[s]:
            if i < 0 or i >= len(board.all_discards_per_seat[s]):
                msg = f"called_discard_indices[{s}] out of range for all_discards_per_seat"
                raise ValueError(msg)

    cur = board.current_seat
    if board.turn_phase == TurnPhase.NEED_DRAW:
        # 与 ``CALL_RESPONSE`` / ``MUST_DISCARD`` 一致：杠后已从岭上摸入并打出一张时，该席可暂为 14（门内+副露），
        # 下一轮摸牌前仍视为「待摸」；不能一律按 13 校验。
        for s in range(4):
            _validate_seat_13_or_post_kan_discard_14(board.hands[s], board.melds[s])
        if board.last_draw_tile is not None:
            msg = "last_draw_tile must be None in NEED_DRAW"
            raise ValueError(msg)
        if board.last_draw_was_rinshan:
            msg = "last_draw_was_rinshan must be False in NEED_DRAW"
            raise ValueError(msg)
    elif board.turn_phase == TurnPhase.MUST_DISCARD:
        for s in range(4):
            if s == cur:
                tot_cur = _seat_total_tiles(board.hands[s], board.melds[s])
                has_quad_meld = any(meld_tile_count(m) == 4 for m in board.melds[s])
                if board.last_draw_was_rinshan:
                    validate_tile_conservation(board.hands[s], board.melds[s], 15)
                elif tot_cur == 15 and has_quad_meld:
                    # 本墙摸牌：上一巡 NEED_DRAW 时该席仍为「杠后岭摸已打」的 14，本巡摸进后为 15（非岭摸）。
                    pass
                else:
                    validate_tile_conservation(board.hands[s], board.melds[s], 14)
            else:
                # 他家可能仍为杠后岭摸已打后的 14（含副露 4 张杠），与 NEED_DRAW 同规则。
                _validate_seat_13_or_post_kan_discard_14(board.hands[s], board.melds[s])
    elif board.turn_phase == TurnPhase.CALL_RESPONSE:
        cs = board.call_state
        assert cs is not None
        if cs.chankan_rinshan_pending:
            if cs.river_index != -1:
                msg = "chankan call_state requires river_index == -1"
                raise ValueError(msg)
        else:
            if not board.river:
                msg = "CALL_RESPONSE requires non-empty river"
                raise ValueError(msg)
            if cs.river_index != len(board.river) - 1:
                msg = "call_state.river_index must point to last river discard"
                raise ValueError(msg)
            if board.river[cs.river_index].tile != cs.claimed_tile:
                msg = "claimed_tile must match river at river_index"
                raise ValueError(msg)
        discard_seat = cs.discard_seat if cs.chankan_rinshan_pending else board.river[-1].seat
        for s in range(4):
            tot = _seat_total_tiles(board.hands[s], board.melds[s])
            if s == discard_seat:
                has_quad_meld = any(meld_tile_count(m) == 4 for m in board.melds[s])
                if tot == 13:
                    pass
                elif tot == 14 and has_quad_meld:
                    pass
                else:
                    msg = (
                        f"CALL_RESPONSE discard_seat {s}: concealed+melds must be 13, "
                        f"or 14 when seat has a 4-tile meld (post-kan discard); got {tot}"
                    )
                    raise ValueError(msg)
            else:
                _validate_seat_13_or_post_kan_discard_14(board.hands[s], board.melds[s])
        if board.last_draw_tile is not None:
            msg = "last_draw_tile must be None in CALL_RESPONSE"
            raise ValueError(msg)
        if board.last_draw_was_rinshan:
            msg = "last_draw_was_rinshan must be False in CALL_RESPONSE"
            raise ValueError(msg)
        if cs.finished and not cs.ron_claimants:
            msg = "finished call_state requires non-empty ron_claimants"
            raise ValueError(msg)
    else:
        msg = f"unknown turn phase: {board.turn_phase!r}"
        raise ValueError(msg)
