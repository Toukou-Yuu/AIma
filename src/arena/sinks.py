"""EventSink: 事件接收器协议与实现。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from arena.hand_result import HandResult
    from arena.match_result import MatchResult
    from arena.policy import DecisionContext, PolicyDecision
    from arena.result import EngineStepResult


class EventSink(Protocol):
    """事件接收器协议，用于收集对局过程中的事件和决策。"""

    def on_step(
        self,
        ctx: DecisionContext,
        decision: PolicyDecision,
        result: EngineStepResult,
    ) -> None:
        """每步决策后调用。

        Args:
            ctx: 决策上下文
            decision: 策略决策结果
            result: 引擎步进结果
        """
        ...

    def on_hand_end(
        self,
        hand_index: int,
        result: HandResult,
    ) -> None:
        """每局结束时调用。

        Args:
            hand_index: 已完成的局号（0-indexed）
            result: 单局结果
        """
        ...

    def on_match_end(self, result: MatchResult) -> None:
        """对局结束时调用。

        Args:
            result: 对局完整结果
        """
        ...


class NullSink:
    """空 Sink，不做任何操作。"""

    def on_step(
        self,
        ctx: DecisionContext,
        decision: PolicyDecision,
        result: EngineStepResult,
    ) -> None:
        """不做任何操作。"""
        pass

    def on_hand_end(
        self,
        hand_index: int,
        result: HandResult,
    ) -> None:
        """不做任何操作。"""
        pass

    def on_match_end(self, result: MatchResult) -> None:
        """不做任何操作。"""
        pass


class InMemorySink:
    """内存 Sink，收集所有事件和决策。"""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.decisions: list[dict] = []
        self.hand_summaries: list[dict] = []

    def on_step(
        self,
        ctx: DecisionContext,
        decision: PolicyDecision,
        result: EngineStepResult,
    ) -> None:
        """收集决策和事件。"""
        # 收集决策记录
        self.decisions.append({
            "match_id": ctx.match_id,
            "step_index": ctx.step_index,
            "seat": ctx.seat,
            "action": decision.action,
        })
        # 收集事件
        for event in result.events:
            self.events.append({
                "match_id": ctx.match_id,
                "step_index": ctx.step_index,
                "event": event,
            })

    def on_hand_end(
        self,
        hand_index: int,
        result: HandResult,
    ) -> None:
        """记录局结束摘要。"""
        self.hand_summaries.append({
            "hand_index": hand_index,
            "match_id": result.match_id,
        })

    def on_match_end(self, result: MatchResult) -> None:
        """记录对局结束摘要。"""
        # InMemorySink 仅收集数据，不做额外处理
        pass