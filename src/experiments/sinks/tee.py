"""TeeSink: Multiplexes events to multiple sinks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.match_result import MatchResult
    from arena.policy import DecisionContext, PolicyDecision
    from arena.result import EngineStepResult

    from . import EventSink


class TeeSink:
    """Multiplexes events to multiple sinks.

    将事件分发到多个 sink，实现日志的 tee 功能。
    """

    def __init__(self, sinks: list[EventSink]) -> None:
        """初始化 TeeSink。

        Args:
            sinks: 要分发事件的 sink 列表
        """
        self._sinks = sinks

    def on_step(
        self,
        ctx: DecisionContext,
        decision: PolicyDecision,
        result: EngineStepResult,
    ) -> None:
        """每步决策后调用，分发到所有 sink。

        Args:
            ctx: 决策上下文
            decision: 策略决策结果
            result: 引擎步进结果
        """
        for sink in self._sinks:
            sink.on_step(ctx, decision, result)

    def on_match_end(self, result: MatchResult) -> None:
        """对局结束时调用，分发到所有 sink。

        Args:
            result: 对局完整结果
        """
        for sink in self._sinks:
            sink.on_match_end(result)