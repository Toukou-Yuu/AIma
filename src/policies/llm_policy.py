"""LLMPolicy: 使用 LLM Agent Pipeline 进行决策的策略。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.components.factory import build_components
from agents.pipeline import AgentPipeline
from arena.policy import DecisionContext, PolicyDecision
from policies.first_legal_policy import legal_action_to_action

if TYPE_CHECKING:
    from agents.schema import AgentSpec
    from memory.stores import MemoryStore


class LLMPolicy:
    """使用 LLM Agent Pipeline 进行决策的策略。

    通过 AgentPipeline 编排6步决策流程：
    observation -> prompt -> call -> parse -> ground -> fallback
    """

    name: str = "llm"

    def __init__(
        self,
        policy_id: str,
        spec: AgentSpec,
        seed: int,
        memory_store: "MemoryStore | None" = None,
        memory_enabled: bool = True,
    ) -> None:
        """初始化 LLM 策略。

        Args:
            policy_id: 策略唯一标识符
            spec: Agent 配置规格
            seed: 随机种子
            memory_store: 可选的 job 级共享 MemoryStore。
            memory_enabled: 实验级 memory 总开关。
        """
        self.policy_id = policy_id
        components = build_components(
            spec,
            seed,
            memory_store=memory_store,
            memory_enabled=memory_enabled,
        )
        self._pipeline = AgentPipeline(components)

    def decide(self, ctx: DecisionContext) -> PolicyDecision:
        """使用 AgentPipeline 执行决策。

        Args:
            ctx: 决策上下文

        Returns:
            PolicyDecision: 决策结果

        Raises:
            ValueError: 如果 pipeline 未产生合法动作
        """
        result = self._pipeline.run(ctx)

        if result.action is None:
            msg = f"LLMPolicy[{self.policy_id}]: pipeline returned no legal action"
            raise ValueError(msg)

        action = legal_action_to_action(result.action)
        return PolicyDecision(
            action=action,
            parse_status=result.parse_status,
            fallback_used=result.fallback_used,
            latency_ms=result.latency_ms,
            raw_output=result.raw_output,
            diagnostics=result.diagnostics,
        )
