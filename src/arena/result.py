"""EngineStepResult: 包装 kernel ApplyOutcome 的结果结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from kernel.event_log import GameEvent


@dataclass(frozen=True, slots=True)
class EngineStepResult:
    """GameEngine.step() 的返回结果。

    Attributes:
        new_state: 推进后的新 GameState
        events: 本动作生成的结构化事件日志
        drained_pass_calls: CALL_PASS_DRAIN 内连续 PASS_CALL 次数
    """

    new_state: "GameState"
    events: tuple["GameEvent", ...]
    drained_pass_calls: int = 0