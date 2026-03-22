"""统一 ``apply``：合法推进；非法阶段/动作抛出 ``IllegalActionError``。"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.deal import assert_wall_is_standard_deck, build_board_after_split
from kernel.engine.actions import Action, ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
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
            new_state = GameState(phase=GamePhase.IN_ROUND, table=state.table, board=board)
            return ApplyOutcome(new_state=new_state, events=())
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    if phase == GamePhase.IN_ROUND:
        if kind == ActionKind.NOOP:
            return ApplyOutcome(new_state=state, events=())
        msg = f"action {kind.value} not allowed in phase {phase.value}"
        raise IllegalActionError(msg)

    msg = f"phase {phase.value} has no implemented transitions in this engine version"
    raise IllegalActionError(msg)
