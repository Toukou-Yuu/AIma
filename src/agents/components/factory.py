"""Pipeline components factory.

职责：
- 构建并组装所有 pipeline 组件
- 根据 AgentSpec 配置各组件
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agents.components.fallback import FallbackKind, FallbackStrategy
from agents.components.grounding import ActionGrounder
from agents.components.observation import ObservationBuilder
from agents.components.parser import OutputParser
from agents.components.prompt import PromptRenderer
from context.builders import ContextBuilder
from memory.manager import MemoryManager
from models.registry import build_backend

if TYPE_CHECKING:
    from agents.schema import AgentSpec
    from memory.stores import MemoryStore
    from models.backend import ModelBackend


@dataclass(frozen=True, slots=True)
class PipelineComponents:
    """Pipeline 组件容器.

    Attributes:
        parser: LLM 输出解析器
        grounder: 动作接地器
        fallback: 回退策略
        observation: 观测构建器
        prompt: 提示词渲染器
        context: 上下文构建器（可选）
        memory: 记忆管理器（可选）
        backend: 模型后端
    """

    parser: OutputParser
    grounder: ActionGrounder
    fallback: FallbackStrategy
    observation: ObservationBuilder
    prompt: PromptRenderer
    context: ContextBuilder | None = None
    memory: MemoryManager | None = None
    backend: "ModelBackend | None" = None


def build_components(
    spec: "AgentSpec",
    seed: int,
    *,
    memory_store: "MemoryStore | None" = None,
    memory_enabled: bool = True,
) -> PipelineComponents:
    """根据 AgentSpec 构建所有 pipeline 组件.

    Args:
        spec: Agent 配置规格
        seed: 随机种子
        memory_store: 可选的 job 级共享 MemoryStore。
        memory_enabled: 实验级 memory 总开关；False 时强制关闭 agent memory。

    Returns:
        组装好的 PipelineComponents
    """
    # 解析回退策略
    fallback_kind = FallbackKind(spec.fallback)

    # 构建上下文构建器（除非 scope=stateless）
    context_builder: ContextBuilder | None = None
    if spec.context.scope != "stateless":
        context_builder = ContextBuilder(spec.context)

    # 构建记忆管理器（除非 mode=off）
    memory_manager: MemoryManager | None = None
    if memory_enabled and spec.memory.mode != "off":
        if memory_store is not None:
            memory_manager = MemoryManager.with_store(spec.memory, memory_store)
        else:
            memory_manager = MemoryManager(spec.memory)

    # 使用 AgentSpec 中的 prompt 配置；sections 为空时回退到模板默认 sections。
    prompt_renderer = PromptRenderer(prompt_spec=spec.prompt)
    backend = build_backend(spec.model)

    return PipelineComponents(
        parser=OutputParser(),
        grounder=ActionGrounder(),
        fallback=FallbackStrategy(kind=fallback_kind, seed=seed),
        observation=ObservationBuilder(),
        prompt=prompt_renderer,
        context=context_builder,
        memory=memory_manager,
        backend=backend,
    )
