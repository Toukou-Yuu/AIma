"""统一 ``apply``：合法推进；非法阶段/动作抛出 ``IllegalActionError``；生成结构化事件日志。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from kernel.call import apply_open_meld, apply_pass_call, apply_ron
from kernel.call.win import can_tsumo_default
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
from kernel.config import get_default_config, MahjongConfig
from kernel.flow import FlowKind, FlowResult
from kernel.hand.multiset import remove_tile
from kernel.kan import apply_ankan, apply_kakan
from kernel.play import apply_discard, apply_draw
from kernel.board import TurnPhase, shimocha_seat
from kernel.riichi.tenpai import is_tenpai_default, _is_menzen
from kernel.table.model import get_riichi_stick_points
from kernel.table.transitions import advance_round, final_settlement, should_match_end
from kernel.wall import split_wall
from kernel.wall.split import split_wall as deal_split_wall

if TYPE_CHECKING:
    from kernel.hand.melds import Meld
    from kernel.tiles.model import Tile


class EngineError(ValueError):
    """引擎相关输入或阶段错误基类。"""


class IllegalActionError(EngineError):
    """当前阶段不接受该动作，或阶段尚未接线。"""


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
    """执行单次 ``PASS_CALL``（含荣和收集结束时的结算与事件）。"""
    config = config or get_default_config()
    phase = state.phase
    board = state.board
    if board is None:
        msg = "IN_ROUND requires board"
        raise IllegalActionError(msg)
    try:
        new_board = apply_pass_call(board, seat)
    except ValueError as e:
        raise IllegalActionError(str(e)) from e
    cs_pb = new_board.call_state
    if cs_pb is not None and cs_pb.finished and cs_pb.ron_claimants:
        # 三家和流局判定：一炮多响=false 且 3 家荣和时触发流局
        if not config.allow_multiple_ron and len(cs_pb.ron_claimants) >= 3:
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
        eb = _create_event_builder(state)
        is_chankan = cs_pb.chankan_rinshan_pending
        new_table, settled, events = settle_ron(
            state.table,
            new_board,
            ron_winners=cs_pb.ron_claimants,
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
                ron_winners=cs_pb.ron_claimants,
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
                try:
                    new_board = apply_ron(board, action.seat)
                except ValueError as e:
                    raise IllegalActionError(str(e)) from e
                cs = new_board.call_state
                if cs is not None and cs.finished and cs.ron_claimants:
                    # 三家和流局判定：一炮多响=false 且 3 家荣和时触发流局
                    if not config.allow_multiple_ron and len(cs.ron_claimants) >= 3:
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
                    eb = _create_event_builder(state)
                    is_chankan = cs.chankan_rinshan_pending
                    new_table, settled, events = settle_ron(
                        state.table,
                        new_board,
                        ron_winners=cs.ron_claimants,
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
                            ron_winners=cs.ron_claimants,
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
            wall_remaining = len(new_board.live_wall) // 2  # 简化：剩余摸牌数
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

            riichi_points = get_riichi_stick_points()
            new_table = state.table
            if action.declare_riichi:
                scores = list(state.table.scores)
                scores[seat] -= riichi_points
                new_table = replace(
                    state.table,
                    scores=tuple(scores),
                    kyoutaku=state.table.kyoutaku + riichi_points,
                )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=new_table,
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
            if board.last_draw_tile is None:
                msg = "TSUMO requires last_draw_tile (e.g. 天和未接线)"
                raise IllegalActionError(msg)
            seat = action.seat
            wt = board.last_draw_tile
            if not can_tsumo_default(
                board.hands[seat],
                board.melds[seat],
                wt,
                last_draw_was_rinshan=board.last_draw_was_rinshan,
            ):
                msg = "illegal tsumo shape"
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

            # 检测四杠流局
            flow_result = detect_flow_after_kan(new_board)
            if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                # 四杠流局：进入 FLOWN 状态
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

            # 检测四杠流局
            flow_result = detect_flow_after_kan(new_board)
            if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                # 四杠流局：进入 FLOWN 状态
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
            # 检查是否首巡：亲家配牌后（无舍牌）或子家配牌后（只有庄家一张舍牌）
            total_discards = sum(len(river) for river in board.rivers)
            dealer_seat = state.table.dealer_seat
            is_first_turn = total_discards == 0 or (
                total_discards == 1 and len(board.rivers[dealer_seat]) == 1
            )
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
        if kind == ActionKind.NOOP:
            # 检查和了后是否终局
            if should_match_end(state.table):
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
                # 未终局：判断是否连庄
                continue_dealer = (
                    state.ron_winners is not None and state.table.dealer_seat in state.ron_winners
                )
                new_table = advance_round(state.table, continue_dealer=continue_dealer)
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
        if kind == ActionKind.NOOP:
            eb = _create_event_builder(state)
            new_state, events = advance_after_flow(
                state.table,
                state.tenpai_result,
                state.table.dealer_seat,
                action.wall,
                eb,
            )
            return ApplyOutcome(new_state=new_state, events=events)
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    msg = f"phase {phase.value} has no implemented transitions in this engine version"
    raise IllegalActionError(msg)
