"""统一 ``apply``：合法推进；非法阶段/动作抛出 ``IllegalActionError``。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kernel.call import apply_open_meld, apply_pass_call, apply_ron, board_after_ron_winners
from kernel.call.win import can_tsumo_default
from kernel.deal import assert_wall_is_standard_deck, build_board_after_split
from kernel.engine.actions import Action, ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.flow import check_flow_kind, settle_flow
from kernel.hand.multiset import remove_tile
from kernel.kan import apply_ankan, apply_shankuminkan
from kernel.play import apply_discard, apply_draw, board_after_tsumo_win
from kernel.play.model import TurnPhase
from kernel.riichi.tenpai import is_tenpai_default
from kernel.scoring.dora import ura_indicators_for_settlement
from kernel.scoring.settle import settle_ron_table, settle_tsumo_table
from kernel.table.model import RIICHI_STICK_POINTS
from kernel.wall import split_wall


class EngineError(ValueError):
    """引擎相关输入或阶段错误基类。"""


class IllegalActionError(EngineError):
    """当前阶段不接受该动作，或阶段尚未接线。"""


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """``apply`` 的结果；``events`` 预留给结构化日志（当前为空元组）。"""

    new_state: GameState
    events: tuple[object, ...]


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
        - ``IN_ROUND`` 且 ``MUST_DISCARD`` + ``TSUMO``：自摸和了（须 ``last_draw_tile``；岭上则 ``can_tsumo_default`` 按 15 张路径）→ ``HAND_OVER`` 并结算点棒。
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
            )
            return ApplyOutcome(new_state=new_state, events=())
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
                    new_table = settle_ron_table(
                        state.table,
                        new_board,
                        ron_winners=cs_pb.ron_claimants,
                        discard_seat=cs_pb.discard_seat,
                        win_tile=cs_pb.claimed_tile,
                        ura_indicators=ura,
                        is_chankan=is_chankan,
                    )
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.HAND_OVER,
                            table=new_table,
                            board=settled,
                            ron_winners=cs_pb.ron_claimants,
                        ),
                        events=(),
                    )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=phase,
                        table=state.table,
                        board=new_board,
                        ron_winners=None,
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
                    new_table = settle_ron_table(
                        state.table,
                        new_board,
                        ron_winners=cs.ron_claimants,
                        discard_seat=cs.discard_seat,
                        win_tile=cs.claimed_tile,
                        ura_indicators=ura,
                        is_chankan=is_chankan,
                    )
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.HAND_OVER,
                            table=new_table,
                            board=settled,
                            ron_winners=cs.ron_claimants,
                        ),
                        events=(),
                    )
                return ApplyOutcome(
                    new_state=GameState(
                        phase=phase,
                        table=state.table,
                        board=new_board,
                        ron_winners=None,
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
                try:
                    new_board = apply_open_meld(board, action.seat, action.meld)
                except ValueError as e:
                    raise IllegalActionError(str(e)) from e
                return ApplyOutcome(
                    new_state=GameState(
                        phase=phase,
                        table=state.table,
                        board=new_board,
                        ron_winners=None,
                    ),
                    events=(),
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

            # 检测荒牌流局
            flow_result = check_flow_kind(
                new_board,
                riichi_state=tuple(board.riichi),
            )
            if flow_result is not None and flow_result.kind == FlowKind.EXHAUSTED:
                # 荒牌流局：进入 FLOWN 状态
                new_table, tenpai_result = settle_flow(state.table, new_board)
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.FLOWN,
                        table=new_table,
                        board=new_board,
                        flow_result=flow_result,
                        tenpai_result=tenpai_result,
                        ron_winners=None,
                    ),
                    events=(),
                )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                ),
                events=(),
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
                    return ApplyOutcome(
                        new_state=GameState(
                            phase=GamePhase.FLOWN,
                            table=new_table,
                            board=new_board,
                            flow_result=flow_result,
                            tenpai_result=tenpai_result,
                            ron_winners=None,
                        ),
                        events=(),
                    )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=new_table,
                    board=new_board,
                    ron_winners=None,
                ),
                events=(),
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
            settled = board_after_tsumo_win(board, winner=seat, win_tile=wt)
            ura = ura_indicators_for_settlement(
                board.dead_wall,
                len(board.revealed_indicators),
            )
            new_table = settle_tsumo_table(
                state.table,
                board,
                winner=seat,
                win_tile=wt,
                ura_indicators=ura,
            )
            return ApplyOutcome(
                new_state=GameState(
                    phase=GamePhase.HAND_OVER,
                    table=new_table,
                    board=settled,
                    ron_winners=frozenset({seat}),
                ),
                events=(),
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

            # 计算杠总数并检测四杠流局
            kan_count = sum(len(melds) for melds in new_board.melds)
            flow_result = check_flow_kind(new_board, kan_count=kan_count)
            if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                # 四杠流局：进入 FLOWN 状态
                new_table, tenpai_result = settle_flow(state.table, new_board)
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.FLOWN,
                        table=new_table,
                        board=new_board,
                        flow_result=flow_result,
                        tenpai_result=tenpai_result,
                        ron_winners=None,
                    ),
                    events=(),
                )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                ),
                events=(),
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

            # 计算杠总数并检测四杠流局
            kan_count = sum(len(melds) for melds in new_board.melds)
            flow_result = check_flow_kind(new_board, kan_count=kan_count)
            if flow_result is not None and flow_result.kind == FlowKind.FOUR_KANS:
                # 四杠流局：进入 FLOWN 状态
                new_table, tenpai_result = settle_flow(state.table, new_board)
                return ApplyOutcome(
                    new_state=GameState(
                        phase=GamePhase.FLOWN,
                        table=new_table,
                        board=new_board,
                        flow_result=flow_result,
                        tenpai_result=tenpai_result,
                        ron_winners=None,
                    ),
                    events=(),
                )

            return ApplyOutcome(
                new_state=GameState(
                    phase=phase,
                    table=state.table,
                    board=new_board,
                    ron_winners=None,
                ),
                events=(),
            )
        if kind in (ActionKind.PASS_CALL, ActionKind.RON, ActionKind.OPEN_MELD):
            msg = f"action {kind.value} only allowed during CALL_RESPONSE"
            raise IllegalActionError(msg)
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    msg = f"phase {phase.value} has no implemented transitions in this engine version"
    raise IllegalActionError(msg)
