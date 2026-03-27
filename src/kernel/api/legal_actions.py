"""合法动作生成：``legal_actions(state, seat)``。

K14 核心模块：枚举某席在当前局面下可执行的所有合法动作。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kernel.api.meld_candidates import (
    enumerate_ankan_melds,
    enumerate_call_response_open_melds,
    enumerate_shankuminkan_melds,
)
from kernel.call.win import can_ron_default, can_ron_seven_pairs
from kernel.deal.model import Meld
from kernel.engine.actions import ActionKind
from kernel.engine.state import GameState
from kernel.play.model import TurnPhase
from kernel.riichi.tenpai import is_tenpai_default
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, slots=True)
class LegalAction:
    """一个合法动作的描述。

    Attributes:
        kind: 动作类型
        seat: 执行者座位
        tile: 打出的牌（DISCARD 时必填）
        meld: 副露（OPEN_MELD/ANKAN/SHANKUMINKAN 时必填）
        declare_riichi: 是否立直宣言（DISCARD 时可选）
    """

    kind: ActionKind
    seat: int
    tile: Tile | None = None
    meld: Meld | None = None
    declare_riichi: bool = False


def legal_actions(state: GameState, seat: int) -> tuple[LegalAction, ...]:
    """
    返回某席在当前局面下可执行的所有合法动作。

    Args:
        state: 当前局面
        seat: 执行者座位

    Returns:
        合法动作列表

    Raises:
        ValueError: seat 不在 0..3 范围内
    """
    if not 0 <= seat <= 3:
        msg = "seat must be 0..3"
        raise ValueError(msg)

    phase = state.phase
    board = state.board

    # PRE_DEAL 阶段：只能 BEGIN_ROUND
    if phase.value == "pre_deal":
        return ()  # BEGIN_ROUND 由外部控制，不在此枚举

    # IN_ROUND 阶段
    if phase.value == "in_round":
        if board is None:
            return ()

        # CALL_RESPONSE 阶段：只能 PASS_CALL/RON/OPEN_MELD
        if board.turn_phase == TurnPhase.CALL_RESPONSE:
            return _legal_actions_call_response(state, seat)

        # MUST_DISCARD 阶段：只能 DISCARD/TSUMO/ANKAN/SHANKUMINKAN
        if board.turn_phase == TurnPhase.MUST_DISCARD:
            return _legal_actions_must_discard(state, seat)

        # NEED_DRAW 阶段：只能 DRAW
        if board.turn_phase == TurnPhase.NEED_DRAW:
            if seat == board.current_seat:
                return (LegalAction(kind=ActionKind.DRAW, seat=seat),)
            return ()

    # HAND_OVER / FLOWN / MATCH_END 阶段：只能 NOOP
    if phase.value in ("hand_over", "flown", "match_end"):
        return (LegalAction(kind=ActionKind.NOOP, seat=seat),)

    return ()


def _legal_actions_call_response(
    state: GameState,
    seat: int,
) -> tuple[LegalAction, ...]:
    """CALL_RESPONSE 阶段的合法动作。"""
    board = state.board
    if board is None:
        return ()

    cs = board.call_state
    if cs is None:
        return ()

    actions = []

    # 检查是否可以 PASS_CALL
    # 在 Ron 阶段：只有 Ron 剩余者可以 PASS
    # 在 Pon/Kan 阶段：只有 Pon/Kan 顺序中的当前索引可以 PASS
    # 在 Chi 阶段：只有上家可以 PASS
    if cs.stage == "ron":
        if seat in cs.ron_remaining:
            actions.append(LegalAction(kind=ActionKind.PASS_CALL, seat=seat))
    elif cs.stage == "pon_kan":
        if seat == cs.pon_kan_order[cs.pon_kan_idx]:
            actions.append(LegalAction(kind=ActionKind.PASS_CALL, seat=seat))
    elif cs.stage == "chi":
        from kernel.play.model import kamicha_seat

        if seat == kamicha_seat(cs.discard_seat):
            actions.append(LegalAction(kind=ActionKind.PASS_CALL, seat=seat))

    # 检查是否可以 RON
    if cs.stage == "ron":
        if seat in cs.ron_remaining:
            # 检查是否可以荣和
            concealed = board.hands[seat]
            melds = board.melds[seat]
            win_tile = cs.claimed_tile

            # 标准形或七对子
            if can_ron_default(concealed, melds, win_tile) or can_ron_seven_pairs(
                concealed, melds, win_tile
            ):
                actions.append(
                    LegalAction(
                        kind=ActionKind.RON,
                        seat=seat,
                        tile=win_tile,
                    )
                )

    # OPEN_MELD：碰 / 大明杠 / 吃（由 meld_candidates 全枚举，与 apply_open_meld 一致）
    for m in enumerate_call_response_open_melds(board, seat):
        actions.append(LegalAction(kind=ActionKind.OPEN_MELD, seat=seat, meld=m))

    return tuple(actions)


def _legal_actions_must_discard(
    state: GameState,
    seat: int,
) -> tuple[LegalAction, ...]:
    """MUST_DISCARD 阶段的合法动作。"""
    board = state.board
    if board is None:
        return ()

    if seat != board.current_seat:
        return ()

    actions = []
    concealed = board.hands[seat]
    melds = board.melds[seat]
    last_tile = board.last_draw_tile

    # DISCARD: 枚举所有手牌
    for tile in concealed.elements():
        # 检查是否可以立直
        if not board.riichi[seat] and not melds:
            # 检查立直条件：门清、听牌、有足够点数
            from kernel.hand.multiset import remove_tile
            from kernel.table.model import RIICHI_STICK_POINTS

            if state.table.scores[seat] >= RIICHI_STICK_POINTS:
                try:
                    hand_after = remove_tile(concealed, tile)
                    if is_tenpai_default(hand_after, melds):
                        actions.append(
                            LegalAction(
                                kind=ActionKind.DISCARD,
                                seat=seat,
                                tile=tile,
                                declare_riichi=True,
                            )
                        )
                except ValueError:
                    pass

        # 普通打牌
        actions.append(
            LegalAction(
                kind=ActionKind.DISCARD,
                seat=seat,
                tile=tile,
                declare_riichi=False,
            )
        )

    # TSUMO: 检查是否可以自摸
    if last_tile is not None:
        from kernel.call.win import can_tsumo_default

        if can_tsumo_default(
            concealed,
            melds,
            last_tile,
            last_draw_was_rinshan=board.last_draw_was_rinshan,
        ):
            actions.append(
                LegalAction(
                    kind=ActionKind.TSUMO,
                    seat=seat,
                    tile=last_tile,
                )
            )

    for m in enumerate_ankan_melds(board, seat):
        actions.append(LegalAction(kind=ActionKind.ANKAN, seat=seat, meld=m))

    for m in enumerate_shankuminkan_melds(board, seat):
        actions.append(LegalAction(kind=ActionKind.SHANKUMINKAN, seat=seat, meld=m))

    return tuple(actions)
