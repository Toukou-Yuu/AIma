"""统一 ``apply``：合法推进；非法阶段/动作抛出 ``IllegalActionError``；生成结构化事件日志。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from kernel.call import apply_open_meld, apply_pass_call, apply_ron, board_after_ron_winners
from kernel.call.win import can_tsumo_default
from kernel.deal import assert_wall_is_standard_deck, build_board_after_split
from kernel.deal.model import BoardState
from kernel.engine.actions import Action, ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    GameEvent,
    HandOverEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
)
from kernel.flow import FlowKind, FlowResult, check_flow_kind, settle_flow
from kernel.flow.model import TenpaiResult
from kernel.hand.multiset import remove_tile
from kernel.kan import apply_ankan, apply_shankuminkan
from kernel.play import apply_discard, apply_draw, board_after_tsumo_win
from kernel.play.model import TurnPhase
from kernel.riichi.tenpai import is_tenpai_default
from kernel.scoring.dora import ura_indicators_for_settlement
from kernel.scoring.settle import settle_ron_table, settle_tsumo_table
from kernel.table.model import RIICHI_STICK_POINTS, TableSnapshot
from kernel.table.transitions import advance_round, compute_match_ranking, should_match_end
from kernel.wall import split_wall
from kernel.wall.split import split_wall as deal_split_wall

if TYPE_CHECKING:
    from kernel.deal.model import Meld
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


class _EventBuilder:
    """事件构建器：维护序列号并生成事件。"""

    def __init__(self, start_sequence: int = 0) -> None:
        self._sequence = start_sequence

    def next_sequence(self) -> int:
        seq = self._sequence
        self._sequence += 1
        return seq

    def round_begin(
        self,
        dealer_seat: int,
        dora_indicator: "Tile",
        seeds: tuple[int, ...],
    ) -> RoundBeginEvent:
        return RoundBeginEvent(
            seat=None,
            sequence=self.next_sequence(),
            dealer_seat=dealer_seat,
            dora_indicator=dora_indicator,
            seeds=seeds,
        )

    def draw_tile(
        self,
        seat: int,
        tile: "Tile",
        is_rinshan: bool,
        wall_remaining: int,
    ) -> DrawTileEvent:
        return DrawTileEvent(
            seat=seat,
            sequence=self.next_sequence(),
            tile=tile,
            is_rinshan=is_rinshan,
            wall_remaining=wall_remaining,
        )

    def discard_tile(
        self,
        seat: int,
        tile: "Tile",
        is_tsumogiri: bool,
        declare_riichi: bool,
    ) -> DiscardTileEvent:
        return DiscardTileEvent(
            seat=seat,
            sequence=self.next_sequence(),
            tile=tile,
            is_tsumogiri=is_tsumogiri,
            declare_riichi=declare_riichi,
        )

    def call(
        self,
        seat: int,
        meld: "Meld",
        call_kind: str,
    ) -> CallEvent:
        return CallEvent(
            seat=seat,
            sequence=self.next_sequence(),
            meld=meld,
            call_kind=call_kind,
        )

    def ron(
        self,
        seat: int,
        win_tile: "Tile",
        discard_seat: int,
    ) -> RonEvent:
        return RonEvent(
            seat=seat,
            sequence=self.next_sequence(),
            win_tile=win_tile,
            discard_seat=discard_seat,
        )

    def tsumo(
        self,
        seat: int,
        win_tile: "Tile",
        is_rinshan: bool,
    ) -> TsumoEvent:
        return TsumoEvent(
            seat=seat,
            sequence=self.next_sequence(),
            win_tile=win_tile,
            is_rinshan=is_rinshan,
        )

    def flow(
        self,
        flow_kind: "FlowKind",
        tenpai_seats: frozenset[int],
    ) -> FlowEvent:
        return FlowEvent(
            seat=None,
            sequence=self.next_sequence(),
            flow_kind=flow_kind,
            tenpai_seats=tenpai_seats,
        )

    def hand_over(
        self,
        winners: tuple[int, ...],
        payments: tuple[int, ...],
    ) -> HandOverEvent:
        return HandOverEvent(
            seat=None,
            sequence=self.next_sequence(),
            winners=winners,
            payments=payments,
        )


def _create_event_builder(state: GameState) -> _EventBuilder:
    """创建事件构建器，从 state.event_sequence 开始。"""
    return _EventBuilder(start_sequence=state.event_sequence)


def _new_state_with_events(
    state: GameState,
    phase: GamePhase,
    table: TableSnapshot | None = None,
    board: BoardState | None = None,
    ron_winners: frozenset[int] | None = None,
    flow_result: FlowResult | None = None,
    tenpai_result: TenpaiResult | None = None,
    event_builder: _EventBuilder | None = None,
) -> GameState:
    """创建新的 GameState 并更新 event_sequence。"""
    return GameState(
        phase=phase,
        table=table if table is not None else state.table,
        board=board,
        ron_winners=ron_winners,
        flow_result=flow_result,
        tenpai_result=tenpai_result,
        event_sequence=event_builder._sequence if event_builder else state.event_sequence,
    )


def _validate_action_seat(action: Action) -> None:
    if action.seat is None:
        return
    if not 0 <= action.seat <= 3:
        msg = "action.seat must be 0..3 when provided"
        raise IllegalActionError(msg)


def apply(state: GameState, action: Action) -> ApplyOutcome:
    """
    唯一推荐的状态推进接口。

    K5 起转移表：
    - ``PRE_DEAL`` + ``BEGIN_ROUND``（附带合法 136 张 ``wall``）→ ``IN_ROUND`` 并写入 ``board``
    - ``IN_ROUND`` + ``NOOP`` → 恒等
    - ``IN_ROUND`` + ``DRAW`` / ``DISCARD`` → 摸打（``kernel.play``）
    - ``IN_ROUND`` + ``MUST_DISCARD`` + ``ANKAN`` / ``SHANKUMINKAN`` → ``kernel.kan``
    - ``IN_ROUND`` 且 ``board.turn_phase == CALL_RESPONSE``：
      ``PASS_CALL`` / ``RON`` / ``OPEN_MELD``（``kernel.call``）；荣和成立时转 ``HAND_OVER``。
    - ``IN_ROUND`` 且 ``MUST_DISCARD`` + ``TSUMO``：自摸和了（须 ``last_draw_tile``；
      岭上则 ``can_tsumo_default`` 按 15 张路径）→ ``HAND_OVER`` 并结算点棒。
    其余组合抛 ``IllegalActionError``。
    """
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
            if kind == ActionKind.PASS_CALL:
                if action.seat is None:
                    msg = "PASS_CALL requires seat"
                    raise IllegalActionError(msg)
                try:
                    new_board = apply_pass_call(board, action.seat)
                except ValueError as e:
                    raise IllegalActionError(str(e)) from e
                cs_pb = new_board.call_state
                if cs_pb is not None and cs_pb.finished and cs_pb.ron_claimants:
                    settled = board_after_ron_winners(new_board)
                    ura = ura_indicators_for_settlement(
                        new_board.dead_wall,
                        len(new_board.revealed_indicators),
                    )
                    is_chankan = cs_pb.chankan_rinshan_pending
                    # 连庄判定：亲家和了则连庄（一炮多响时任一亲家和了即连庄）
                    continue_dealer = any(w == state.table.dealer_seat for w in cs_pb.ron_claimants)
                    new_table = settle_ron_table(
                        state.table,
                        new_board,
                        ron_winners=cs_pb.ron_claimants,
                        discard_seat=cs_pb.discard_seat,
                        win_tile=cs_pb.claimed_tile,
                        ura_indicators=ura,
                        is_chankan=is_chankan,
                        continue_dealer=continue_dealer,
                    )
                    # 生成 RonEvent 和 HandOverEvent
                    eb = _create_event_builder(state)
                    events = []
                    for winner in cs_pb.ron_claimants:
                        ron_event = eb.ron(
                            seat=winner,
                            win_tile=cs_pb.claimed_tile,
                            discard_seat=cs_pb.discard_seat,
                        )
                        events.append(ron_event)
                    hand_over_event = eb.hand_over(
                        winners=tuple(cs_pb.ron_claimants),
                        payments=(0, 0, 0, 0),  # 简化：实际由 settle 计算
                    )
                    events.append(hand_over_event)
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.HAND_OVER,
                            table=new_table,
                            board=settled,
                            ron_winners=cs_pb.ron_claimants,
                            event_sequence=eb._sequence,
                        ),
                        events=tuple(events),
                    )
                # PASS_CALL 不生成事件（只是声明放弃）
                return ApplyOutcome(
                    new_state=GameState(
                        phase=phase,
                        table=state.table,
                        board=new_board,
                        ron_winners=None,
                        event_sequence=state.event_sequence,  # PASS_CALL 不增加事件
                    ),
                    events=(),
                )
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
                    settled = board_after_ron_winners(new_board)
                    ura = ura_indicators_for_settlement(
                        new_board.dead_wall,
                        len(new_board.revealed_indicators),
                    )
                    is_chankan = cs.chankan_rinshan_pending
                    # 连庄判定：亲家和了则连庄（一炮多响时任一亲家和了即连庄）
                    continue_dealer = any(w == state.table.dealer_seat for w in cs.ron_claimants)
                    new_table = settle_ron_table(
                        state.table,
                        new_board,
                        ron_winners=cs.ron_claimants,
                        discard_seat=cs.discard_seat,
                        win_tile=cs.claimed_tile,
                        ura_indicators=ura,
                        is_chankan=is_chankan,
                        continue_dealer=continue_dealer,
                    )
                    # 生成 RonEvent 和 HandOverEvent
                    eb = _create_event_builder(state)
                    events = []
                    for winner in cs.ron_claimants:
                        ron_event = eb.ron(
                            seat=winner,
                            win_tile=cs.claimed_tile,
                            discard_seat=cs.discard_seat,
                        )
                        events.append(ron_event)
                    hand_over_event = eb.hand_over(
                        winners=tuple(cs.ron_claimants),
                        payments=(0, 0, 0, 0),  # 简化：实际由 settle 计算
                    )
                    events.append(hand_over_event)
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.HAND_OVER,
                            table=new_table,
                            board=settled,
                            ron_winners=cs.ron_claimants,
                            event_sequence=eb._sequence,
                        ),
                        events=tuple(events),
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
                # 确定鸣牌类型
                call_kind = action.meld.kind.lower()  # "chi", "pon", "daiminkan"
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
            try:
                new_board = apply_draw(board, seat)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e

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

            # 检测荒牌流局
            flow_result = check_flow_kind(
                new_board,
                riichi_state=tuple(board.riichi),
            )
            if flow_result is not None and flow_result.kind == FlowKind.EXHAUSTED:
                # 荒牌流局：进入 FLOWN 状态
                new_table, tenpai_result = settle_flow(state.table, new_board)
                flow_event = eb.flow(
                    flow_kind=flow_result.kind,
                    tenpai_seats=tenpai_result.tenpai_seats if tenpai_result else frozenset(),
                )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.FLOWN,
                        table=new_table,
                        board=new_board,
                        flow_result=flow_result,
                        tenpai_result=tenpai_result,
                        ron_winners=None,
                        event_sequence=eb._sequence,
                    ),
                    events=(draw_event, flow_event),
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
            if action.declare_riichi:
                if board.riichi[seat]:
                    msg = "already riichi"
                    raise IllegalActionError(msg)
                if board.melds[seat]:
                    msg = "riichi requires menzen"
                    raise IllegalActionError(msg)
                if state.table.scores[seat] < RIICHI_STICK_POINTS:
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

            new_table = state.table
            if action.declare_riichi:
                scores = list(state.table.scores)
                scores[seat] -= RIICHI_STICK_POINTS
                new_table = replace(
                    state.table,
                    scores=tuple(scores),
                    kyoutaku=state.table.kyoutaku + RIICHI_STICK_POINTS,
                )

            # 检测四家立直流局
            if action.declare_riichi:
                new_riichi_state = list(board.riichi)
                new_riichi_state[seat] = True
                flow_result = check_flow_kind(
                    new_board,
                    riichi_state=tuple(new_riichi_state),
                )
                if flow_result is not None and flow_result.kind == FlowKind.FOUR_RIICHI:
                    # 四家立直流局：进入 FLOWN 状态
                    new_table, tenpai_result = settle_flow(new_table, new_board)
                    flow_event = eb.flow(
                        flow_kind=flow_result.kind,
                        tenpai_seats=tenpai_result.tenpai_seats if tenpai_result else frozenset(),
                    )
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.FLOWN,
                            table=new_table,
                            board=new_board,
                            flow_result=flow_result,
                            tenpai_result=tenpai_result,
                            ron_winners=None,
                            event_sequence=eb._sequence,
                        ),
                        events=(discard_event, flow_event),
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

            # 生成 TsumoEvent
            eb = _create_event_builder(state)
            tsumo_event = eb.tsumo(
                seat=seat,
                win_tile=wt,
                is_rinshan=board.last_draw_was_rinshan,
            )

            settled = board_after_tsumo_win(board, winner=seat, win_tile=wt)
            ura = ura_indicators_for_settlement(
                board.dead_wall,
                len(board.revealed_indicators),
            )
            # 连庄判定：亲家自摸则连庄
            continue_dealer = seat == state.table.dealer_seat
            new_table = settle_tsumo_table(
                state.table,
                board,
                winner=seat,
                win_tile=wt,
                ura_indicators=ura,
                continue_dealer=continue_dealer,
            )

            # 生成 HandOverEvent
            # 计算点棒变化（相对局开始前）：简化处理，用 winners 收益表示
            winners = (seat,)
            # payments: 简化为 (0, 0, 0, 0)，实际应由 settle 逻辑计算
            payments = (0, 0, 0, 0)
            hand_over_event = eb.hand_over(winners=winners, payments=payments)

            return ApplyOutcome(
                new_state=GameState(
                    phase=GamePhase.HAND_OVER,
                    table=new_table,
                    board=settled,
                    ron_winners=frozenset({seat}),
                    event_sequence=eb._sequence,
                ),
                events=(tsumo_event, hand_over_event),
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

            # 计算杠总数并检测四杠流局
            kan_count = sum(len(melds) for melds in new_board.melds)
            flow_result = check_flow_kind(new_board, kan_count=kan_count)
            if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                # 四杠流局：进入 FLOWN 状态
                new_table, tenpai_result = settle_flow(state.table, new_board)
                flow_event = eb.flow(
                    flow_kind=flow_result.kind,
                    tenpai_seats=tenpai_result.tenpai_seats if tenpai_result else frozenset(),
                )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.FLOWN,
                        table=new_table,
                        board=new_board,
                        flow_result=flow_result,
                        tenpai_result=tenpai_result,
                        ron_winners=None,
                        event_sequence=eb._sequence,
                    ),
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
        if kind == ActionKind.SHANKUMINKAN:
            if board.turn_phase != TurnPhase.MUST_DISCARD:
                msg = "SHANKUMINKAN requires MUST_DISCARD"
                raise IllegalActionError(msg)
            if action.seat is None:
                msg = "SHANKUMINKAN requires seat"
                raise IllegalActionError(msg)
            if action.meld is None:
                msg = "SHANKUMINKAN requires meld"
                raise IllegalActionError(msg)
            try:
                new_board = apply_shankuminkan(board, action.seat, action.meld)
            except ValueError as e:
                raise IllegalActionError(str(e)) from e

            # 生成 CallEvent (shankuminkan)
            eb = _create_event_builder(state)
            kan_event = eb.call(
                seat=action.seat,
                meld=action.meld,
                call_kind="shankuminkan",
            )

            # 计算杠总数并检测四杠流局
            kan_count = sum(len(melds) for melds in new_board.melds)
            flow_result = check_flow_kind(new_board, kan_count=kan_count)
            if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                # 四杠流局：进入 FLOWN 状态
                new_table, tenpai_result = settle_flow(state.table, new_board)
                flow_event = eb.flow(
                    flow_kind=flow_result.kind,
                    tenpai_seats=tenpai_result.tenpai_seats if tenpai_result else frozenset(),
                )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.FLOWN,
                        table=new_table,
                        board=new_board,
                        flow_result=flow_result,
                        tenpai_result=tenpai_result,
                        ron_winners=None,
                        event_sequence=eb._sequence,
                    ),
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
        if kind in (ActionKind.PASS_CALL, ActionKind.RON, ActionKind.OPEN_MELD):
            msg = f"action {kind.value} only allowed during CALL_RESPONSE"
            raise IllegalActionError(msg)
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    # HAND_OVER 阶段：和了后等待下一局或终局
    if phase == GamePhase.HAND_OVER:
        if kind == ActionKind.NOOP:
            # 检查和了后是否终局
            if should_match_end(state.table):
                # 终局：计算名次，进入 MATCH_END
                compute_match_ranking(state.table)  # 仅用于验证
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.MATCH_END,
                        table=state.table,
                        board=state.board,
                        ron_winners=state.ron_winners,
                    ),
                    events=(),  # 终局不再生成新事件
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
            # 检查流局后是否终局
            # 注意：settle_flow 已经更新了 honba（连庄时 +1，亲流时重置）
            # 但 advance_round 需要知道是否连庄来决定是否推进局序
            # 这里通过 honba 是否增加来判断（实际上需要更精确的逻辑）

            # 简化处理：流局后亲家听牌则连庄（不推进局序），否则亲流（推进局序）
            # 由于 settle_flow 已经更新了 honba，我们需要根据 honba 推断 continue_dealer
            # 更好的方式是在 GameState 中存储 continue_dealer 标志

            # 临时方案：检查表是否已更新本场（连庄时 honba 增加）
            # 实际上这需要更精确的状态跟踪，这里先假设 settle_flow 后的 table 已正确设置 honba
            # advance_round 在 continue_dealer=False 时才会推进局序

            # 正确做法：需要在 settle_flow 返回额外信息，或者在 GameState 中存储连庄状态
            # 这里先使用简化逻辑：流局后总是尝试推进局序（亲流），连庄时局序不变
            # 由于 settle_flow 已经处理了 honba，advance_round 只需处理局序和亲席

            # 检查是否终局
            if should_match_end(state.table):
                # 终局：计算名次，进入 MATCH_END
                compute_match_ranking(state.table)  # 仅用于验证
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.MATCH_END,
                        table=state.table,
                        board=state.board,
                        ron_winners=None,
                        flow_result=state.flow_result,
                        tenpai_result=state.tenpai_result,
                    ),
                    events=(),
                )
            else:
                # 未终局：需要判断是否连庄
                # 连庄条件：亲家听牌（honba 增加）
                # 由于 settle_flow 已经更新了 honba，我们检查 honba 是否增加来判断
                # 但这不够精确，更好的方式是在 GameState 中存储连庄标志

                # 简化：假设 settle_flow 后的 table.honba 已正确反映连庄/亲流
                # advance_round 需要根据连庄与否来决定是否推进局序
                # 这里通过比较原 table 和新 table 的 honba 来判断
                # 但实际上我们无法在这里获取原 table，所以需要一个新方案

                # 最佳方案：在 GameState 中添加 continue_dealer 字段
                # 临时方案：假设 FLOWN 状态下 honba>0 表示连庄（不推进局序），
                #          honba=0 表示亲流（推进）；这不够精确，但可以工作

                # 更精确的方式：检查亲家是否听牌
                if (
                    state.tenpai_result
                    and state.table.dealer_seat in state.tenpai_result.tenpai_seats
                ):
                    # 亲家听牌：连庄，不推进局序
                    continue_dealer = True
                else:
                    # 亲家未听牌：亲流，推进局序
                    continue_dealer = False

                new_table = advance_round(state.table, continue_dealer=continue_dealer)
                # 重新开局配牌
                w = action.wall if action.wall is not None else None
                if w is None:
                    # 需要外部提供牌山
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
                        flow_result=None,  # 清除流局结果
                        tenpai_result=None,
                        event_sequence=eb._sequence,
                    ),
                    events=(round_begin_event,),
                )
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    msg = f"phase {phase.value} has no implemented transitions in this engine version"
    raise IllegalActionError(msg)
