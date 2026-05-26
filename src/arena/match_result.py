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
        decision_count: 决策总数
        event_count: 事件总数
        hand_count: 局数（hand_over 事件计数）
        duration_ms: 对局执行时间（毫秒）
        final_phase: 最终阶段
        final_points: 各家最终点数
        point_delta: 各家点数变化（final_points - starting_points）
        rank: 各家顺位
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
    decision_count: int = 0
    event_count: int = 0
    hand_count: int = 0
    duration_ms: float = 0.0
    final_phase: str = ""
    final_points: tuple[int, int, int, int] = (25000, 25000, 25000, 25000)
    point_delta: tuple[int, int, int, int] = (0, 0, 0, 0)
    rank: tuple[int, int, int, int] = (1, 1, 1, 1)