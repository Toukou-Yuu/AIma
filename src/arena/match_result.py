"""MatchResult: 一局对局的完整结果记录。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.engine import GameState


@dataclass(frozen=True, slots=True)
class MatchResult:
    """一局对局的完整结果。

    Attributes:
        match_id: 对局唯一标识符
        job_id: 批处理任务标识符
        seed: 随机种子
        final_state: 对局结束时的最终 GameState
        step_count: 总步数
        events: 事件日志元组
        decisions: 决策记录元组
        stopped_reason: 停止原因（正常结束为 None，异常为错误描述）
        outcome: 对局结果类型（"completed" | "truncated" | "step_limit_reached"）
    """

    match_id: str
    job_id: str
    seed: int
    final_state: "GameState"
    step_count: int
    events: tuple[dict, ...]
    decisions: tuple[dict, ...]
    stopped_reason: str | None = None
    outcome: str = "completed"