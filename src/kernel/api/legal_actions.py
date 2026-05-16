"""合法动作生成：``legal_actions(state, seat)``。

K14 核心模块：枚举某席在当前局面下可执行的所有合法动作。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kernel.api.meld_candidates import (
    enumerate_ankan_melds,
    enumerate_call_response_open_melds,
    enumerate_kakan_melds,
)
from kernel.call.ron_rules import can_declare_ron
from kernel.config import get_default_config
from kernel.board import BoardState, TurnPhase
from kernel.engine.actions import ActionKind
from kernel.engine.state import GameState
from kernel.flow import check_nine_nine_declaration
from kernel.hand.melds import Meld
from kernel.riichi.tenpai import is_tenpai_default
from kernel.scoring.yaku import non_dora_yaku_han_and_labels
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    pass


def _scoring_is_haitei(board: BoardState) -> bool:
    """与 ``scoring.settle`` 一致：本墙已摸完。"""
    return board.live_draw_index >= len(board.live_wall)


def _scoring_is_hotei(board: BoardState, discard_seat: int) -> bool:
    """与 ``scoring.settle`` 一致：河底判定（本墙已摸完）。"""
    return board.live_draw_index >= len(board.live_wall)


def _legal_ron_non_dora_han(state: GameState, seat: int, win_tile: Tile) -> int:
    """荣和时ドラ以外の役番（日麻：无役则不可和）。"""
    board = state.board
    if board is None:
        return 0
    cs = board.call_state
    if cs is None:
        return 0
    table = state.table
    discard_seat = cs.discard_seat
    config = get_default_config()
    nd_han, _ = non_dora_yaku_han_and_labels(
        board,
        table,
        seat,
        for_ron=True,
        win_tile=win_tile,
        concealed=board.hands[seat],
        melds=board.melds[seat],
        allow_open_tanyao=config.allow_open_tanyao,
        last_draw_was_rinshan=False,
        is_haitei=_scoring_is_haitei(board),
        is_hotei=_scoring_is_hotei(board, discard_seat),
        is_chankan=cs.chankan_rinshan_pending,
        is_tsumo=False,
    )
    return nd_han


def _legal_tsumo_non_dora_han(state: GameState, seat: int, win_tile: Tile) -> int:
    """自摸时ドラ以外の役番（日麻：无役则不可自摸和了）。"""
    board = state.board
    if board is None:
        return 0
    table = state.table
    config = get_default_config()
    nd_han, _ = non_dora_yaku_han_and_labels(
        board,
        table,
        seat,
        for_ron=False,
        win_tile=win_tile,
        concealed=board.hands[seat],
        melds=board.melds[seat],
        allow_open_tanyao=config.allow_open_tanyao,
        last_draw_was_rinshan=board.last_draw_was_rinshan,
        is_haitei=_scoring_is_haitei(board),
        is_hotei=False,
        is_chankan=False,
        is_tsumo=True,
    )
    return nd_han


@dataclass(frozen=True, slots=True)
class LegalAction:
    """一个合法动作的描述。

    Attributes:
        kind: 动作类型
        seat: 执行者座位
        tile: 打出的牌（DISCARD 时必填）
        meld: 副露（OPEN_MELD/ANKAN/KAKAN 时必填）
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

        # MUST_DISCARD 阶段：只能 DISCARD/TSUMO/ANKAN/KAKAN
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
    # 在 Chi 阶段：只有下家可以 PASS
    if cs.stage == "ron":
        if seat in cs.ron_remaining:
            actions.append(LegalAction(kind=ActionKind.PASS_CALL, seat=seat))
    elif cs.stage == "pon_kan":
        if seat == cs.pon_kan_order[cs.pon_kan_idx]:
            actions.append(LegalAction(kind=ActionKind.PASS_CALL, seat=seat))
    elif cs.stage == "chi":
        from kernel.board import shimocha_seat

        if seat == shimocha_seat(cs.discard_seat):
            actions.append(LegalAction(kind=ActionKind.PASS_CALL, seat=seat))

    # 检查是否可以 RON
    if cs.stage == "ron":
        if seat in cs.ron_remaining:
            win_tile = cs.claimed_tile

            # BoardState 级门禁与 apply_ron 共用；役番检查依赖 GameState.table，留在此层。
            if can_declare_ron(board, seat).allowed:
                if _legal_ron_non_dora_han(state, seat, win_tile) >= 1:
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


def _is_ankan_tenpai_preserved(
    board: BoardState,
    seat: int,
    ankan_meld: Meld,
) -> bool:
    """立直后暗杠：校验暗杠前后听牌集合完全一致。

    前提条件（调用方保证）：
    - board.riichi[seat] is True
    - board.turn_phase == MUST_DISCARD
    - board.last_draw_tile is not None
    - ankan_meld 是有效的暗杠（4张同种牌，均在手牌中）
    """
    from kernel.hand.multiset import remove_tiles
    from kernel.riichi.tenpai import compute_waiting_tiles

    concealed_14 = board.hands[seat]
    melds_before = board.melds[seat]
    tsumogiri = board.last_draw_tile

    # 暗杠前听牌集合：摸切牌打出后 13 张手牌的听牌集合
    if tsumogiri is None or concealed_14.get(tsumogiri, 0) < 1:
        return False
    concealed_13 = Counter(concealed_14)
    concealed_13[tsumogiri] -= 1
    if concealed_13[tsumogiri] == 0:
        del concealed_13[tsumogiri]
    waiting_before = compute_waiting_tiles(concealed_13, melds_before)
    if not waiting_before:
        return False

    # 暗杠后听牌集合：移除暗杠 4 张后门内 + 暗杠副露
    try:
        concealed_after = remove_tiles(concealed_14, list(ankan_meld.tiles))
    except ValueError:
        return False
    melds_after = melds_before + (ankan_meld,)
    waiting_after = compute_waiting_tiles(concealed_after, melds_after)

    return waiting_before == waiting_after


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

    # 九种九牌：首巡、无副露、9 种以上幺九牌
    if last_tile is not None and check_nine_nine_declaration(concealed):
        # 检查是否首巡：亲家配牌后（无舍牌）或子家配牌后（只有庄家一张舍牌）
        total_discards = sum(len(river) for river in board.all_discards_per_seat)
        dealer_seat = state.table.dealer_seat
        is_first_turn = total_discards == 0 or (
            total_discards == 1 and len(board.all_discards_per_seat[dealer_seat]) == 1
        )
        # 检查是否无副露
        no_melds = all(len(m) == 0 for m in board.melds)
        if is_first_turn and no_melds:
            actions.append(LegalAction(kind=ActionKind.DECLARE_NINE_NINE, seat=seat))

    # 已立直：只能摸切（打出上一张自摸），与 ``play.apply_discard`` 一致
    if board.riichi[seat]:
        if last_tile is not None and concealed.get(last_tile, 0) >= 1:
            actions.append(
                LegalAction(
                    kind=ActionKind.DISCARD,
                    seat=seat,
                    tile=last_tile,
                    declare_riichi=False,
                )
            )
    else:
        # DISCARD: 枚举所有手牌
        for tile in concealed.elements():
            # 检查是否可以立直
            if not melds:
                # 检查立直条件：门清、听牌、有足够点数
                from kernel.hand.multiset import remove_tile
                from kernel.table.model import get_riichi_stick_points

                riichi_points = get_riichi_stick_points()
                if state.table.scores[seat] >= riichi_points:
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

    # TSUMO: 检查是否可以自摸（需同时满足和了形 + 至少 1 役）
    if last_tile is not None:
        from kernel.call.win import can_tsumo_default

        if can_tsumo_default(
            concealed,
            melds,
            last_tile,
            last_draw_was_rinshan=board.last_draw_was_rinshan,
        ):
            if _legal_tsumo_non_dora_han(state, seat, last_tile) >= 1:
                actions.append(
                    LegalAction(
                        kind=ActionKind.TSUMO,
                        seat=seat,
                        tile=last_tile,
                    )
                )

    for m in enumerate_ankan_melds(board, seat):
        # 立直后暗杠：须保证听牌集合不变
        if board.riichi[seat]:
            if not _is_ankan_tenpai_preserved(board, seat, m):
                continue
        actions.append(LegalAction(kind=ActionKind.ANKAN, seat=seat, meld=m))

    for m in enumerate_kakan_melds(board, seat):
        actions.append(LegalAction(kind=ActionKind.KAKAN, seat=seat, meld=m))

    return tuple(actions)
