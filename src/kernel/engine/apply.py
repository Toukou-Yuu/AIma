"""统一 ``apply``：合法推进；非法阶段/动作抛出 ``IllegalActionError``；生成结构化事件日志。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from kernel.call import apply_open_meld, apply_pass_call, apply_ron
from kernel.call.transitions import _replace_board  # P2-01: 用于设置振听
from kernel.call.win import (
    can_tsumo_default,
    can_win_seven_pairs_concealed_14,
)
from kernel.win_shape.std import can_win_standard_form_concealed_total
from kernel.deal import assert_wall_is_standard_deck, build_board_after_split
from kernel.board import BoardState
from kernel.engine.actions import Action, ActionKind
from kernel.engine.events import EventBuilder
from kernel.engine.flow import (
    advance_after_flow,
    apply_flow_transition,
    apply_three_ron_flow,
    detect_flow_after_kan,
    detect_flow_after_riichi,
    detect_flow_exhausted,
    detect_flow_four_winds,
)
from kernel.engine.phase import GamePhase
from kernel.engine.settlement import settle_ron, settle_tsumo
from kernel.engine.state import GameState
from kernel.event_log import GameEvent
from kernel.config import get_default_config, MahjongConfig, RonPolicy
from kernel.flow import FlowKind, FlowResult
from kernel.hand.multiset import remove_tile
from kernel.kan import apply_ankan, apply_kakan
from kernel.play import apply_discard, apply_draw
from kernel.board import TurnPhase, shimocha_seat
from kernel.riichi.tenpai import is_tenpai_default, _is_menzen
from kernel.table.model import get_riichi_stick_points
from kernel.table.transitions import advance_round, final_settlement, should_match_end
from kernel.wall import split_wall
from kernel.wall.split import split_wall as deal_split_wall, total_wall_remaining

if TYPE_CHECKING:
    from kernel.hand.melds import Meld
    from kernel.tiles.model import Tile


# P2-02: 役番门禁检查函数
def _is_haitei_for_scoring(board: BoardState) -> bool:
    """是否海底（本墙已摸完）。"""
    return board.live_draw_index >= len(board.live_wall)


def _is_hotei_for_scoring(board: BoardState, discard_seat: int) -> bool:
    """是否河底。"""
    return board.live_draw_index >= len(board.live_wall)


def _ron_non_dora_han(state: GameState, seat: int, win_tile: Tile) -> int:
    """荣和时ドラ以外の役番（P2-02: 一番起和门禁）。"""
    board = state.board
    if board is None:
        return 0
    cs = board.call_state
    if cs is None:
        return 0
    # 延迟导入避免循环依赖
    from kernel.scoring.yaku import non_dora_yaku_han_and_labels

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
        is_haitei=_is_haitei_for_scoring(board),
        is_hotei=_is_hotei_for_scoring(board, discard_seat),
        is_chankan=cs.chankan_rinshan_pending,
        is_tsumo=False,
    )
    return nd_han


def _tsumo_non_dora_han(state: GameState, seat: int, win_tile: Tile) -> int:
    """自摸时ドラ以外の役番（P2-02: 一番起和门禁）。"""
    board = state.board
    if board is None:
        return 0
    # 延迟导入避免循环依赖
    from kernel.scoring.yaku import non_dora_yaku_han_and_labels

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
        is_haitei=_is_haitei_for_scoring(board),
        is_hotei=False,
        is_chankan=False,
        is_tsumo=True,
    )
    return nd_han


class EngineError(ValueError):
    """引擎相关输入或阶段错误基类。"""


class IllegalActionError(EngineError):
    """当前阶段不接受该动作，或阶段尚未接线。"""


def atamahane_winner(ron_claimants: frozenset[int], discard_seat: int) -> int:
    """头跳：返回最靠近 discard_seat 的荣和者（下家优先）。

    Args:
        ron_claimants: 荣和申请者的座位集合
        discard_seat: 被荣和牌的打出者座位

    Returns:
        头跳胜者的座位

    Example:
        discard_seat=0, ron_claimants={1, 2, 3} -> return 1（下家）
        discard_seat=0, ron_claimants={2, 3} -> return 2（对家）
        discard_seat=1, ron_claimants={0, 2} -> return 2（对家优先于上家）
    """
    # (seat - discard_seat + 4) % 4 计算座位相对于打出者的顺位
    # 结果越小越优先：下家=1，对家=2，上家=3
    return min(ron_claimants, key=lambda s: (s - discard_seat + 4) % 4)


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """``apply`` 的结果；``events`` 包含本动作生成的结构化事件日志。"""

    new_state: GameState
    events: tuple[GameEvent, ...]
    drained_pass_calls: int = 0
    """``CALL_PASS_DRAIN`` 内部连续 ``PASS_CALL`` 的次数；其它动作为 0。"""


def _validate_action_seat(action: Action) -> None:
    if action.seat is None:
        return
    if not 0 <= action.seat <= 3:
        msg = "action.seat must be 0..3 when provided"
        raise IllegalActionError(msg)


def _create_event_builder(state: GameState) -> EventBuilder:
    """创建事件构建器，从 state.event_sequence 开始。"""
    return EventBuilder(start_sequence=state.event_sequence)


_CALL_PASS_DRAIN_MAX = 64


def _outcome_pass_call(state: GameState, seat: int, config: MahjongConfig | None = None) -> ApplyOutcome:
    """执行单次 ``PASS_CALL``（含荣和收集结束时的结算与事件，P2-01: 设置振听）。"""
    config = config or get_default_config()
    phase = state.phase
    board = state.board
    if board is None:
        msg = "IN_ROUND requires board"
        raise IllegalActionError(msg)

    # P2-01: 检查是否有合法荣和机会（用于设置振听）
    cs = board.call_state
    had_valid_ron = False
    if cs is not None and cs.stage == "ron" and seat in cs.ron_remaining:
        win_tile = cs.claimed_tile
        # 检查形状和役番
        from kernel.call.win import can_ron_default
        if can_ron_default(board.hands[seat], board.melds[seat], win_tile):
            if _ron_non_dora_han(state, seat, win_tile) >= 1:
                had_valid_ron = True

    try:
        new_board = apply_pass_call(board, seat)
    except ValueError as e:
        raise IllegalActionError(str(e)) from e

    # P2-01: 设置振听状态（如果有合法荣和机会但 pass）
    if had_valid_ron:
        if board.riichi[seat]:
            # 立直后见逃：本局振听
            new_furiten = frozenset(board.riichi_furiten | {seat})
            new_board = _replace_board(new_board, riichi_furiten=new_furiten)
        else:
            # 同巡振听：到下次摸牌前振听
            new_furiten = frozenset(board.temporary_furiten | {seat})
            new_board = _replace_board(new_board, temporary_furiten=new_furiten)

    cs_pb = new_board.call_state
    if cs_pb is not None and cs_pb.finished and cs_pb.ron_claimants:
        # 多家荣和策略判定
        if config.ron_policy == RonPolicy.TRIPLE_ABORTIVE_ONLY and len(cs_pb.ron_claimants) >= 3:
            # 三家和流局：仅 3 家荣和时触发流局
            eb = _create_event_builder(state)
            flow_state = apply_three_ron_flow(new_board, state.table, cs_pb.ron_claimants, eb)
            flow_event = eb.flow(
                flow_kind=FlowKind.THREE_RON,
                tenpai_seats=frozenset(),
            )
            hand_over_event = eb.hand_over(
                winners=(),
                payments=(0, 0, 0, 0),
                win_lines=(),
            )
            return ApplyOutcome(
                new_state=flow_state,
                events=(flow_event, hand_over_event),
            )
        # 选择荣和胜者集合
        ron_winners = cs_pb.ron_claimants
        if config.ron_policy == RonPolicy.ATAMAHANE:
            # 头跳：仅头跳胜者结算
            ron_winners = frozenset({atamahane_winner(cs_pb.ron_claimants, cs_pb.discard_seat)})
        eb = _create_event_builder(state)
        is_chankan = cs_pb.chankan_rinshan_pending
        new_table, settled, events = settle_ron(
            state.table,
            new_board,
            ron_winners=ron_winners,
            discard_seat=cs_pb.discard_seat,
            win_tile=cs_pb.claimed_tile,
            is_chankan=is_chankan,
            dealer_seat=state.table.dealer_seat,
            event_builder=eb,
        )
        return ApplyOutcome(
            new_state=GameState(
                phase=GamePhase.HAND_OVER,
                table=new_table,
                board=settled,
                ron_winners=ron_winners,
                event_sequence=eb._sequence,
            ),
            events=events,
        )
    # H-04: Finalize table-level riichi payment if pending was just finalized
    if board.pending_riichi is not None and new_board.pending_riichi is None and new_board.riichi[board.pending_riichi]:
        # Pending riichi was finalized - deduct points from table
        riichi_seat = board.pending_riichi
        riichi_points = get_riichi_stick_points()
        scores = list(state.table.scores)
        scores[riichi_seat] -= riichi_points
        new_table = replace(
            state.table,
            scores=tuple(scores),
            kyoutaku=state.table.kyoutaku + riichi_points,
        )
        # Continue with H-05 flow check using the updated table
        if new_board.turn_phase == TurnPhase.NEED_DRAW and new_board.call_state is None:
            flow_result = detect_flow_after_riichi(new_board, tuple(new_board.riichi))
            if flow_result is not None:
                eb = _create_event_builder(state)
                flown_state, flow_event = apply_flow_transition(
                    GameState(phase=phase, table=new_table, board=new_board, ron_winners=None, event_sequence=state.event_sequence),
                    flow_result,
                    eb,
                )
                return ApplyOutcome(new_state=flown_state, events=(flow_event,))
        # No flow - return with updated table
        return ApplyOutcome(
            new_state=GameState(
                phase=phase,
                table=new_table,
                board=new_board,
                ron_winners=None,
                event_sequence=state.event_sequence,
            ),
            events=(),
        )
    # H-05: Check for four-riichi flow after CALL_RESPONSE ends (no pending riichi case)
    if new_board.turn_phase == TurnPhase.NEED_DRAW and new_board.call_state is None:
        flow_result = detect_flow_after_riichi(new_board, tuple(new_board.riichi))
        if flow_result is not None:
            eb = _create_event_builder(state)
            flown_state, flow_event = apply_flow_transition(state, flow_result, eb)
            return ApplyOutcome(new_state=flown_state, events=(flow_event,))

    # H-08: Check for four winds flow after CALL_RESPONSE ends
    if new_board.turn_phase == TurnPhase.NEED_DRAW and new_board.call_state is None:
        four_winds_flow = detect_flow_four_winds(new_board)
        if four_winds_flow is not None:
            eb = _create_event_builder(state)
            flown_state, flow_event = apply_flow_transition(state, four_winds_flow, eb)
            return ApplyOutcome(new_state=flown_state, events=(flow_event,))

    # H-13: Check for exhausted flow after CALL_RESPONSE ends
    if new_board.turn_phase == TurnPhase.NEED_DRAW and new_board.call_state is None:
        exhausted_flow = detect_flow_exhausted(new_board)
        if exhausted_flow is not None:
            eb = _create_event_builder(state)
            flown_state, flow_event = apply_flow_transition(state, exhausted_flow, eb)
            return ApplyOutcome(new_state=flown_state, events=(flow_event,))

    # H-11: Check for four-kans flow after chankan window closes
    if new_board.turn_phase == TurnPhase.NEED_DRAW and new_board.call_state is None:
        four_kans_flow = detect_flow_after_kan(new_board)
        if four_kans_flow is not None and four_kans_flow.kind == FlowKind.FOUR_KANS:
            eb = _create_event_builder(state)
            flown_state, flow_event = apply_flow_transition(state, four_kans_flow, eb)
            return ApplyOutcome(new_state=flown_state, events=(flow_event,))

    return ApplyOutcome(
        new_state=GameState(
            phase=phase,
            table=state.table,
            board=new_board,
            ron_winners=None,
            event_sequence=state.event_sequence,
        ),
        events=(),
    )


def _call_response_active_seat(board: BoardState) -> int | None:
    """
    当前应答窗口轮到表态的席（荣和：``min(ron_remaining)``；碰杠：``pon_kan_order[idx]``；吃：下家）。
    与 ``CALL_PASS_DRAIN`` 及串行 ``PASS_CALL`` 对齐。
    """
    if board.turn_phase != TurnPhase.CALL_RESPONSE:
        return None
    cs = board.call_state
    if cs is None:
        return None
    if cs.stage == "ron":
        return min(cs.ron_remaining) if cs.ron_remaining else None
    if cs.stage == "pon_kan":
        return cs.pon_kan_order[cs.pon_kan_idx]
    if cs.stage == "chi":
        return shimocha_seat(cs.discard_seat)
    return None


def _apply_call_pass_drain(state: GameState, config: MahjongConfig | None = None) -> ApplyOutcome:
    """连续执行「当前先序席仅可过」的 ``PASS_CALL``，直至否则或离开应答。"""
    config = config or get_default_config()
    # 延迟导入，避免 ``apply`` ↔ ``legal_actions`` 与 ``engine.__init__`` 形成环
    from kernel.api.legal_actions import legal_actions

    drained = 0
    events_list: list[GameEvent] = []
    cur = state
    for _ in range(_CALL_PASS_DRAIN_MAX):
        board = cur.board
        if cur.phase != GamePhase.IN_ROUND or board is None:
            break
        if board.turn_phase != TurnPhase.CALL_RESPONSE:
            break
        seat = _call_response_active_seat(board)
        if seat is None:
            break
        acts = legal_actions(cur, seat)
        if len(acts) != 1 or acts[0].kind != ActionKind.PASS_CALL:
            break
        out = _outcome_pass_call(cur, seat, config=config)
        drained += 1
        events_list.extend(out.events)
        cur = out.new_state
    if drained == 0:
        msg = "CALL_PASS_DRAIN: first pending seat is not forced pass"
        raise IllegalActionError(msg)
    if (
        cur.phase == GamePhase.IN_ROUND
        and cur.board is not None
        and cur.board.turn_phase == TurnPhase.CALL_RESPONSE
    ):
        seat2 = _call_response_active_seat(cur.board)
        if seat2 is not None:
            acts2 = legal_actions(cur, seat2)
            if len(acts2) == 1 and acts2[0].kind == ActionKind.PASS_CALL:
                msg = "CALL_PASS_DRAIN: iteration limit exceeded"
                raise IllegalActionError(msg)
    return ApplyOutcome(
        new_state=cur,
        events=tuple(events_list),
        drained_pass_calls=drained,
    )


def apply(state: GameState, action: Action, config: MahjongConfig | None = None) -> ApplyOutcome:
    """
    唯一推荐的状态推进接口。

    K5 起转移表：
    - ``PRE_DEAL`` + ``BEGIN_ROUND``（附带合法 136 张 ``wall``）→ ``IN_ROUND`` 并写入 ``board``
    - ``IN_ROUND`` + ``NOOP`` → 恒等
    - ``IN_ROUND`` + ``DRAW`` / ``DISCARD`` → 摸打（``kernel.play``）
    - ``IN_ROUND`` + ``MUST_DISCARD`` + ``ANKAN`` / ``KAKAN`` → ``kernel.kan``
    - ``IN_ROUND`` 且 ``board.turn_phase == CALL_RESPONSE``：
      ``PASS_CALL`` / ``RON`` / ``OPEN_MELD``（``kernel.call``）；荣和成立时转 ``HAND_OVER``。
    - ``IN_ROUND`` 且 ``MUST_DISCARD`` + ``TSUMO``：自摸和了（须 ``last_draw_tile``；
      岭上则 ``can_tsumo_default`` 按 15 张路径）→ ``HAND_OVER`` 并结算点棒。
    其余组合抛 ``IllegalActionError``。
    """
    config = config or get_default_config()
    _validate_action_seat(action)
    phase = state.phase
    kind = action.kind

    if phase == GamePhase.PRE_DEAL:
        if kind == ActionKind.BEGIN_ROUND:
            w = action.wall
            if w is None or len(w) != 136:
                msg = "BEGIN_ROUND requires wall of length 136"
                raise IllegalActionError(msg)
            try:
                assert_wall_is_standard_deck(w)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e
            try:
                split = split_wall(w)
                board = build_board_after_split(split, state.table.dealer_seat)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e
            new_state = GameState(
                phase=GamePhase.IN_ROUND,
                table=state.table,
                board=board,
                ron_winners=None,
                event_sequence=state.event_sequence,
            )
            # 生成 RoundBeginEvent
            eb = _create_event_builder(state)
            dora_ind = board.revealed_indicators[0] if board.revealed_indicators else None
            # seeds: 各家初始手牌在 wall 中的索引（简化：用座位 * 13 作为种子索引）
            seeds = tuple(s * 13 for s in range(4))
            event = eb.round_begin(
                dealer_seat=state.table.dealer_seat,
                dora_indicator=dora_ind,
                seeds=seeds,
            )
            # 更新 event_sequence
            new_state = replace(new_state, event_sequence=eb._sequence)
            return ApplyOutcome(new_state=new_state, events=(event,))
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    if phase == GamePhase.IN_ROUND:
        if kind == ActionKind.NOOP:
            return ApplyOutcome(new_state=state, events=())
        board = state.board
        if board is None:
            msg = "IN_ROUND requires board"
            raise IllegalActionError(msg)

        if board.turn_phase == TurnPhase.CALL_RESPONSE:
            if kind == ActionKind.DRAW:
                msg = "DRAW not allowed during CALL_RESPONSE"
                raise IllegalActionError(msg)
            if kind == ActionKind.DISCARD:
                msg = "DISCARD not allowed during CALL_RESPONSE"
                raise IllegalActionError(msg)
            if kind == ActionKind.CALL_PASS_DRAIN:
                if action.seat is not None:
                    msg = "CALL_PASS_DRAIN does not use seat"
                    raise IllegalActionError(msg)
                return _apply_call_pass_drain(state, config=config)
            if kind == ActionKind.PASS_CALL:
                if action.seat is None:
                    msg = "PASS_CALL requires seat"
                    raise IllegalActionError(msg)
                return _outcome_pass_call(state, action.seat, config=config)
            if kind == ActionKind.RON:
                if action.seat is None:
                    msg = "RON requires seat"
                    raise IllegalActionError(msg)
                # P2-02: 一番起和门禁检查
                cs = board.call_state
                if cs is None:
                    msg = "RON requires call_state"
                    raise IllegalActionError(msg)
                win_tile = cs.claimed_tile
                if _ron_non_dora_han(state, action.seat, win_tile) < 1:
                    msg = "荣和须至少一番役（ドラ不可单独计和）"
                    raise IllegalActionError(msg)
                try:
                    new_board = apply_ron(board, action.seat)
                except ValueError as e:
                    raise IllegalActionError(str(e)) from e
                cs = new_board.call_state
                if cs is not None and cs.finished and cs.ron_claimants:
                    # 多家荣和策略判定
                    if config.ron_policy == RonPolicy.TRIPLE_ABORTIVE_ONLY and len(cs.ron_claimants) >= 3:
                        # 三家和流局：仅 3 家荣和时触发流局
                        eb = _create_event_builder(state)
                        flow_state = apply_three_ron_flow(new_board, state.table, cs.ron_claimants, eb)
                        flow_event = eb.flow(
                            flow_kind=FlowKind.THREE_RON,
                            tenpai_seats=frozenset(),
                        )
                        hand_over_event = eb.hand_over(
                            winners=(),
                            payments=(0, 0, 0, 0),
                            win_lines=(),
                        )
                        return ApplyOutcome(
                            new_state=flow_state,
                            events=(flow_event, hand_over_event),
                        )
                    # 选择荣和胜者集合
                    ron_winners = cs.ron_claimants
                    if config.ron_policy == RonPolicy.ATAMAHANE:
                        # 头跳：仅头跳胜者结算
                        ron_winners = frozenset({atamahane_winner(cs.ron_claimants, cs.discard_seat)})
                    eb = _create_event_builder(state)
                    is_chankan = cs.chankan_rinshan_pending
                    new_table, settled, events = settle_ron(
                        state.table,
                        new_board,
                        ron_winners=ron_winners,
                        discard_seat=cs.discard_seat,
                        win_tile=cs.claimed_tile,
                        is_chankan=is_chankan,
                        dealer_seat=state.table.dealer_seat,
                        event_builder=eb,
                    )
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.HAND_OVER,
                            table=new_table,
                            board=settled,
                            ron_winners=ron_winners,
                            event_sequence=eb._sequence,
                        ),
                        events=events,
                    )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=phase,
                        table=state.table,
                        board=new_board,
                        ron_winners=None,
                        event_sequence=state.event_sequence,  # RON 被 PASS 不增加事件
                    ),
                    events=(),
                )
            if kind == ActionKind.OPEN_MELD:
                if action.seat is None:
                    msg = "OPEN_MELD requires seat"
                    raise IllegalActionError(msg)
                if action.meld is None:
                    msg = "OPEN_MELD requires meld"
                    raise IllegalActionError(msg)
                # ``Meld.kind`` 为 ``MeldKind`` 枚举，须用 ``.value``（与 wire 小写串一致）
                call_kind = action.meld.kind.value
                try:
                    new_board = apply_open_meld(board, action.seat, action.meld)
                except ValueError as e:
                    raise IllegalActionError(str(e)) from e
                # 生成 CallEvent
                eb = _create_event_builder(state)
                call_event = eb.call(
                    seat=action.seat,
                    meld=action.meld,
                    call_kind=call_kind,
                )

                # H-12: 大明杠后检测四杠散了
                from kernel.hand.melds import MeldKind
                from kernel.kan.rinshan import apply_after_kan_rinshan_draw
                if action.meld.kind == MeldKind.DAIMINKAN:
                    flow_result = detect_flow_after_kan(new_board)
                    if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                        flown_state, flow_event = apply_flow_transition(
                            GameState(
                                phase=GamePhase.IN_ROUND,
                                table=state.table,
                                board=new_board,
                                ron_winners=None,
                                event_sequence=eb._sequence,
                            ),
                            flow_result,
                            eb,
                        )
                        return ApplyOutcome(
                            new_state=flown_state,
                            events=(call_event, flow_event),
                        )
                    # 无流局，岭上摸牌
                    after_rinshan = apply_after_kan_rinshan_draw(new_board, action.seat)
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=phase,
                            table=state.table,
                            board=after_rinshan,
                            ron_winners=None,
                            event_sequence=eb._sequence,
                        ),
                        events=(call_event,),
                    )

                return ApplyOutcome(
                    new_state=GameState(
                        phase=phase,
                        table=state.table,
                        board=new_board,
                        ron_winners=None,
                        event_sequence=eb._sequence,
                    ),
                    events=(call_event,),
                )
            msg = f"action {kind.value} not allowed during CALL_RESPONSE"
            raise IllegalActionError(msg)

        if kind == ActionKind.DRAW:
            seat = action.seat if action.seat is not None else board.current_seat
            if seat != board.current_seat:
                msg = "DRAW seat must match current_seat when provided"
                raise IllegalActionError(msg)

            # 检测四风连打流局（首巡无副露 + 四家第一舍为同风牌）
            four_winds_flow = detect_flow_four_winds(board)
            if four_winds_flow is not None:
                eb = _create_event_builder(state)
                flown_state, flow_event = apply_flow_transition(
                    state, four_winds_flow, eb
                )
                return ApplyOutcome(
                    new_state=flown_state,
                    events=(flow_event,),
                )

            # 检测牌山耗尽：触发荒牌流局而非抛出错误
            exhausted_flow = detect_flow_exhausted(board)
            if exhausted_flow is not None:
                # 牌山已耗尽，无法摸牌 → 荒牌流局
                eb = _create_event_builder(state)
                flown_state, flow_event = apply_flow_transition(
                    state, exhausted_flow, eb
                )
                return ApplyOutcome(
                    new_state=flown_state,
                    events=(flow_event,),
                )

            new_board = apply_draw(board, seat)

            # 生成 DrawTileEvent
            eb = _create_event_builder(state)
            drawn_tile = new_board.last_draw_tile
            is_rinshan = new_board.last_draw_was_rinshan
            wall_remaining = total_wall_remaining(
                len(new_board.live_wall),
                new_board.live_draw_index,
                new_board.rinshan_draw_index,
            )
            draw_event = eb.draw_tile(
                seat=seat,
                tile=drawn_tile,
                is_rinshan=is_rinshan,
                wall_remaining=wall_remaining,
            )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                    event_sequence=eb._sequence,
                ),
                events=(draw_event,),
            )
        if kind == ActionKind.DISCARD:
            if action.seat is None:
                msg = "DISCARD requires seat"
                raise IllegalActionError(msg)
            if action.seat != board.current_seat:
                msg = "DISCARD seat must equal current_seat"
                raise IllegalActionError(msg)
            if action.tile is None:
                msg = "DISCARD requires tile"
                raise IllegalActionError(msg)
            seat = action.seat
            riichi_points = get_riichi_stick_points()
            if action.declare_riichi:
                if board.riichi[seat]:
                    msg = "already riichi"
                    raise IllegalActionError(msg)
                if not _is_menzen(board.melds[seat]):
                    msg = "riichi requires menzen"
                    raise IllegalActionError(msg)
                if state.table.scores[seat] < riichi_points:
                    msg = "insufficient points for riichi stick"
                    raise IllegalActionError(msg)
                try:
                    hand_after = remove_tile(board.hands[seat], action.tile)
                except ValueError as e:
                    raise IllegalActionError(str(e)) from e
                if not is_tenpai_default(hand_after, board.melds[seat]):
                    msg = "not tenpai"
                    raise IllegalActionError(msg)
            try:
                new_board = apply_discard(
                    board,
                    seat,
                    action.tile,
                    declare_riichi=action.declare_riichi,
                )
            except ValueError as e:
                raise IllegalActionError(str(e)) from e

            # 生成 DiscardTileEvent
            eb = _create_event_builder(state)
            # 判断是否摸切：比较打出的牌与最后摸的牌
            is_tsumogiri = board.last_draw_tile is not None and action.tile == board.last_draw_tile
            discard_event = eb.discard_tile(
                seat=seat,
                tile=action.tile,
                is_tsumogiri=is_tsumogiri,
                declare_riichi=action.declare_riichi,
            )

            # H-04: 点数扣除移至 pending riichi finalize 时（CALL_RESPONSE 结束）
            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                    event_sequence=eb._sequence,
                ),
                events=(discard_event,),
            )
        if kind == ActionKind.TSUMO:
            if board.turn_phase != TurnPhase.MUST_DISCARD:
                msg = "TSUMO requires MUST_DISCARD"
                raise IllegalActionError(msg)
            if action.seat is None:
                msg = "TSUMO requires seat"
                raise IllegalActionError(msg)
            if action.seat != board.current_seat:
                msg = "TSUMO seat must equal current_seat"
                raise IllegalActionError(msg)

            seat = action.seat

            # H-14: 允许庄家配牌14张自摸（天和）
            if board.last_draw_tile is None:
                # 条件：庄家 + river为空 + 无鸣牌 + MUST_DISCARD
                if (
                    board.current_seat == state.table.dealer_seat
                    and len(board.river) == 0
                    and all(len(m) == 0 for m in board.melds)
                ):
                    # 检查14张手牌是否为和牌形
                    concealed = board.hands[seat]
                    melds = board.melds[seat]
                    is_seven_pairs = can_win_seven_pairs_concealed_14(concealed, melds)
                    is_standard = can_win_standard_form_concealed_total(concealed, melds)
                    if not is_seven_pairs and not is_standard:
                        msg = "Dealer initial 14 not winning shape"
                        raise IllegalActionError(msg)

                    # 从14张手牌中确定 win_tile（选择第一张非零牌）
                    for tile, count in concealed.items():
                        if count >= 1:
                            wt = tile
                            break

                    # P2-02: 天和役番门禁检查
                    if _tsumo_non_dora_han(state, seat, wt) < 1:
                        msg = "自摸须至少一番役（ドラ不可单独计和）"
                        raise IllegalActionError(msg)

                    eb = _create_event_builder(state)
                    new_table, settled, events = settle_tsumo(
                        state.table,
                        board,
                        winner=seat,
                        win_tile=wt,
                        is_rinshan=False,
                        dealer_seat=state.table.dealer_seat,
                        event_builder=eb,
                    )
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.HAND_OVER,
                            table=new_table,
                            board=settled,
                            ron_winners=frozenset({seat}),
                            event_sequence=eb._sequence,
                        ),
                        events=events,
                    )
                else:
                    msg = "TSUMO requires last_draw_tile"
                    raise IllegalActionError(msg)

            wt = board.last_draw_tile
            if not can_tsumo_default(
                board.hands[seat],
                board.melds[seat],
                wt,
                last_draw_was_rinshan=board.last_draw_was_rinshan,
            ):
                msg = "illegal tsumo shape"
                raise IllegalActionError(msg)

            # P2-02: 自摸役番门禁检查
            if _tsumo_non_dora_han(state, seat, wt) < 1:
                msg = "自摸须至少一番役（ドラ不可单独计和）"
                raise IllegalActionError(msg)

            eb = _create_event_builder(state)
            new_table, settled, events = settle_tsumo(
                state.table,
                board,
                winner=seat,
                win_tile=wt,
                is_rinshan=board.last_draw_was_rinshan,
                dealer_seat=state.table.dealer_seat,
                event_builder=eb,
            )
            return ApplyOutcome(
                new_state=GameState(
                    phase=GamePhase.HAND_OVER,
                    table=new_table,
                    board=settled,
                    ron_winners=frozenset({seat}),
                    event_sequence=eb._sequence,
                ),
                events=events,
            )
        if kind == ActionKind.ANKAN:
            if board.turn_phase != TurnPhase.MUST_DISCARD:
                msg = "ANKAN requires MUST_DISCARD"
                raise IllegalActionError(msg)
            if action.seat is None:
                msg = "ANKAN requires seat"
                raise IllegalActionError(msg)
            if action.meld is None:
                msg = "ANKAN requires meld"
                raise IllegalActionError(msg)
            try:
                new_board = apply_ankan(board, action.seat, action.meld)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e

            # 生成 CallEvent (ankan)
            eb = _create_event_builder(state)
            kan_event = eb.call(
                seat=action.seat,
                meld=action.meld,
                call_kind="ankan",
            )

            # H-11: 四杠散了检测须在抢杠窗口结束后执行
            # 若 apply_ankan 创建了 CALL_RESPONSE 窗口（kokushi-rob-ankan），跳过检测
            # 若无抢杠窗口，立即检测是正确的
            if new_board.turn_phase != TurnPhase.CALL_RESPONSE:
                flow_result = detect_flow_after_kan(new_board)
                if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                    flown_state, flow_event = apply_flow_transition(
                        GameState(
                            phase=GamePhase.IN_ROUND,
                            table=state.table,
                            board=new_board,
                            ron_winners=None,
                            event_sequence=eb._sequence,
                        ),
                        flow_result,
                        eb,
                    )
                    return ApplyOutcome(
                        new_state=flown_state,
                        events=(kan_event, flow_event),
                    )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                    event_sequence=eb._sequence,
                ),
                events=(kan_event,),
            )
        if kind == ActionKind.KAKAN:
            if board.turn_phase != TurnPhase.MUST_DISCARD:
                msg = "KAKAN requires MUST_DISCARD"
                raise IllegalActionError(msg)
            if action.seat is None:
                msg = "KAKAN requires seat"
                raise IllegalActionError(msg)
            if action.meld is None:
                msg = "KAKAN requires meld"
                raise IllegalActionError(msg)
            try:
                new_board = apply_kakan(board, action.seat, action.meld)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e

            # 生成 CallEvent (kakan)
            eb = _create_event_builder(state)
            kan_event = eb.call(
                seat=action.seat,
                meld=action.meld,
                call_kind="kakan",
            )

            # H-11: 加杠一定触发抢杠窗口，四杠散了检测须在窗口结束后执行
            # 移除过早检测，让 CALL_RESPONSE 正常处理

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                    event_sequence=eb._sequence,
                ),
                events=(kan_event,),
            )
        if kind == ActionKind.DECLARE_NINE_NINE:
            if board.turn_phase != TurnPhase.MUST_DISCARD:
                msg = "DECLARE_NINE_NINE requires MUST_DISCARD"
                raise IllegalActionError(msg)
            if action.seat is None:
                msg = "DECLARE_NINE_NINE requires seat"
                raise IllegalActionError(msg)
            if action.seat != board.current_seat:
                msg = "DECLARE_NINE_NINE seat must equal current_seat"
                raise IllegalActionError(msg)
            seat = action.seat

            # 验证九种九牌条件
            from kernel.flow import check_nine_nine_declaration

            if board.last_draw_tile is None:
                msg = "DECLARE_NINE_NINE requires last_draw_tile"
                raise IllegalActionError(msg)
            if not check_nine_nine_declaration(board.hands[seat]):
                msg = "not nine_nine declaration condition"
                raise IllegalActionError(msg)
            # 检查是否首巡：当前玩家无舍牌
            is_first_turn = len(board.all_discards_per_seat[seat]) == 0
            if not is_first_turn:
                msg = "not first turn for nine_nine declaration"
                raise IllegalActionError(msg)
            # 检查是否无副露
            no_melds = all(len(m) == 0 for m in board.melds)
            if not no_melds:
                msg = "nine_nine declaration requires no melds"
                raise IllegalActionError(msg)

            # 九种九牌流局：进入 FLOWN 状态
            eb = _create_event_builder(state)
            flow_result = FlowResult(kind=FlowKind.NINE_NINE)
            flown_state, flow_event = apply_flow_transition(
                GameState(
                    phase=GamePhase.IN_ROUND,
                    table=state.table,
                    board=board,
                    ron_winners=None,
                    event_sequence=eb._sequence,
                ),
                flow_result,
                eb,
            )
            return ApplyOutcome(
                new_state=flown_state,
                events=(flow_event,),
            )
        if kind in (
            ActionKind.PASS_CALL,
            ActionKind.CALL_PASS_DRAIN,
            ActionKind.RON,
            ActionKind.OPEN_MELD,
        ):
            msg = f"action {kind.value} only allowed during CALL_RESPONSE"
            raise IllegalActionError(msg)
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    # HAND_OVER 阶段：和了后等待下一局或终局
    if phase == GamePhase.HAND_OVER:
        if kind == ActionKind.NEXT_ROUND:  # H-24: 使用 NEXT_ROUND
            # 先判断是否连庄（亲家和了）
            continue_dealer = (
                state.ron_winners is not None and state.table.dealer_seat in state.ron_winners
            )

            if continue_dealer:
                # 连庄：不判断终局，直接推进
                new_table = advance_round(state.table, continue_dealer=True)
            elif should_match_end(state.table):
                # 亲流 + 终局条件满足：终局
                ranking, final_table = final_settlement(state.table)
                eb = _create_event_builder(state)
                end_ev = eb.match_end(
                    ranking=ranking,
                    final_scores=final_table.scores,
                )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.MATCH_END,
                        table=final_table,
                        board=state.board,
                        ron_winners=state.ron_winners,
                        event_sequence=eb._sequence,
                    ),
                    events=(end_ev,),
                )
            else:
                # 亲流但未达终局条件：推进下一局
                new_table = advance_round(state.table, continue_dealer=False)

            # 重新开局配牌
            w = action.wall if action.wall is not None else None
            if w is None:
                msg = "NEXT_ROUND requires wall"
                raise IllegalActionError(msg)
            try:
                assert_wall_is_standard_deck(w)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e
            try:
                split = deal_split_wall(w)
                board = build_board_after_split(split, new_table.dealer_seat)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e

            # 生成新局的 RoundBeginEvent
            eb = _create_event_builder(state)
            dora_ind = board.revealed_indicators[0] if board.revealed_indicators else None
            seeds = tuple(s * 13 for s in range(4))
            round_begin_event = eb.round_begin(
                dealer_seat=new_table.dealer_seat,
                dora_indicator=dora_ind,
                seeds=seeds,
            )

            return ApplyOutcome(
                new_state=GameState(
                    phase=GamePhase.IN_ROUND,
                    table=new_table,
                    board=board,
                    ron_winners=None,
                    event_sequence=eb._sequence,
                ),
                events=(round_begin_event,),
            )
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    # FLOWN 阶段：流局后等待下一局或终局
    if phase == GamePhase.FLOWN:
        if kind == ActionKind.NEXT_ROUND:  # H-24: 使用 NEXT_ROUND
            eb = _create_event_builder(state)
            new_state, events = advance_after_flow(
                state.table,
                state.tenpai_result,
                state.table.dealer_seat,
                action.wall,
                eb,
                flow_result=state.flow_result,
            )
            return ApplyOutcome(new_state=new_state, events=events)
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    msg = f"phase {phase.value} has no implemented transitions in this engine version"
    raise IllegalActionError(msg)
