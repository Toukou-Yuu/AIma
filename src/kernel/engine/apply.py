"""统一 ``apply``：合法推进；非法阶段/动作抛出 ``IllegalActionError``。"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.engine.actions import Action, ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState


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

    K4 转移表：
    - ``PRE_DEAL`` + ``BEGIN_ROUND_STUB`` → ``IN_ROUND``（场况不变）
    - ``IN_ROUND`` + ``NOOP`` → 恒等
    其余组合抛 ``IllegalActionError``。
    """
    _validate_action_seat(action)
    phase = state.phase
    kind = action.kind

    if phase == GamePhase.PRE_DEAL:
        if kind == ActionKind.BEGIN_ROUND_STUB:
            new_state = GameState(phase=GamePhase.IN_ROUND, table=state.table)
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
