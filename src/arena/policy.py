"""Policy Protocol: 策略接口定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from context.events import ContextEvent
    from kernel import Action, GameState
    from kernel.api import LegalAction, Observation


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """决策上下文，包含策略做决策所需的所有信息。

    Attributes:
        match_id: 对局唯一标识符
        job_id: 批处理任务标识符
        hand_index: 当前手牌索引
        step_index: 当前步数
        seed: 随机种子
        seat: 玩家座位（0-3）
        phase: 当前阶段
        state: 完整游戏状态
        observation: 观测信息（部分观测）
        legal_actions: 合法动作列表
    """

    match_id: str
    job_id: str
    hand_index: int
    step_index: int
    seed: int
    seat: int
    phase: str
    state: GameState
    observation: Observation
    legal_actions: tuple[LegalAction, ...]
    event_history: "tuple[ContextEvent, ...]" = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """策略决策结果。

    Attributes:
        action: 选择的动作（必填）
        parse_status: 解析状态（默认 "ok"）
        fallback_used: 是否使用了 fallback 动作
        latency_ms: 决策耗时（毫秒）
        raw_output: 原始输出（如 LLM 响应文本）
        diagnostics: 诊断信息
    """

    action: Action
    parse_status: str = "ok"
    fallback_used: bool = False
    latency_ms: float | None = None
    raw_output: str | None = None
    diagnostics: dict = field(default_factory=dict)


class Policy(Protocol):
    """策略协议，定义所有策略必须实现的接口。

    Attributes:
        name: 策略名称（人类可读）
        policy_id: 策略唯一标识符
    """

    name: str
    policy_id: str

    def decide(self, ctx: DecisionContext) -> PolicyDecision:
        """根据上下文做出决策。

        Args:
            ctx: 决策上下文

        Returns:
            PolicyDecision: 决策结果
        """
        ...