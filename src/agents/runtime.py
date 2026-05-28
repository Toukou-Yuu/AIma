"""PromptRuntime — AgentPipeline 运行时产物容器。

由 AgentPipeline 在每次决策时构建，将 ObservationBuilder / ContextBuilder / MemoryManager
的输出集中传给 PromptRenderer。

PromptRenderer 从 runtime 读取数据，不再从 spec.options["content"] 静态注入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arena.policy import DecisionContext


@dataclass(frozen=True, slots=True)
class BuiltObservation:
    """ObservationBuilder 的输出。

    Attributes:
        text: 渲染后的观测文本（供 prompt observation section 使用）
        diagnostics: 构建过程诊断信息
    """

    text: str
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BuiltContext:
    """ContextBuilder 的输出（对应 context/builders.py 的 BuiltContext，但作为 runtime 传递）。

    Attributes:
        text: 渲染后的历史事件文本（供 prompt public_history section 使用）
        raw_event_count: 筛选前事件数量
        rendered_event_count: 实际渲染事件数量
        scope: context scope 配置（stateless / per_hand / per_match / per_turn）
        truncated: 是否因 token 预算截断
        diagnostics: 构建过程诊断信息
    """

    text: str
    raw_event_count: int = 0
    rendered_event_count: int = 0
    scope: str = "stateless"
    truncated: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls, scope: str = "stateless") -> "BuiltContext":
        """构建空 context（stateless 模式使用）。"""
        return cls(text="", scope=scope)


@dataclass(frozen=True, slots=True)
class MemoryReadResult:
    """MemoryManager 的输出。

    Attributes:
        rendered_text: 格式化后的记忆文本（供 prompt memory section 使用）
        layers: 已读取的记忆层名称列表
        token_estimate: 文本 token 估算值
        diagnostics: 构建过程诊断信息
    """

    rendered_text: str
    layers: tuple[str, ...] = ()
    token_estimate: int = 0
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "MemoryReadResult":
        """构建空记忆结果（memory off 时使用）。"""
        return cls(rendered_text="")


@dataclass(frozen=True, slots=True)
class PromptRuntime:
    """AgentPipeline 传给 PromptRenderer 的运行时容器。

    Prompt DSL section 的数据来源固定为：
        observation    -> runtime.observation.text
        public_history -> runtime.context.text
        memory         -> runtime.memory.rendered_text
        legal_actions  -> runtime.decision.legal_actions
        output_schema  -> prompt spec

    Attributes:
        decision: 当前决策上下文（包含 legal_actions 等基础数据）
        observation: ObservationBuilder 输出
        context: ContextBuilder 输出（公共历史）
        memory: MemoryManager 输出（记忆注入）
    """

    decision: "DecisionContext"
    observation: BuiltObservation
    context: BuiltContext
    memory: MemoryReadResult
