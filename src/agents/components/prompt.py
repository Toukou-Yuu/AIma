"""PromptRenderer - 提示词渲染组件.

职责：
- 将 DecisionContext 渲染为 ChatMessage 列表
- 使用 prompts/renderer.py 的真正实现
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llm.protocol import ChatMessage
from prompts.loader import load_template
from prompts.renderer import PromptRenderer as RealPromptRenderer

if TYPE_CHECKING:
    from agents.runtime import PromptRuntime
    from arena.policy import DecisionContext
    from prompts.schema import PromptSpec


class PromptRenderer:
    """提示词渲染器.

    将决策上下文渲染为 LLM 消息列表。
    使用 prompts/renderer.py 的真正实现。
    """

    def __init__(
        self,
        template_id: str = "riichi_json_action_v1",
        *,
        prompt_spec: "PromptSpec | None" = None,
    ) -> None:
        """初始化提示词渲染器.

        Args:
            template_id: 模板ID（默认 riichi_json_action_v1）
            prompt_spec: AgentSpec 中的 prompt 配置；sections 为空时使用模板默认。
        """
        base_spec = prompt_spec or load_template(template_id, use_cache=True)
        if prompt_spec is not None and not prompt_spec.sections:
            base_spec = load_template(prompt_spec.template_id, use_cache=True).model_copy(
                update={
                    "version": prompt_spec.version,
                    "output_format": prompt_spec.output_format,
                    "budget": prompt_spec.budget,
                },
                deep=True,
            )
        else:
            base_spec = base_spec.model_copy(deep=True)

        self._template_id = base_spec.template_id
        self._spec = base_spec
        self._renderer = RealPromptRenderer(self._spec)

    def render(
        self,
        ctx: "DecisionContext",
        runtime: "PromptRuntime | None" = None,
    ) -> list[ChatMessage]:
        """渲染提示词.

        Args:
            ctx: 决策上下文
            runtime: AgentPipeline 构建的 observation/context/memory 运行时数据

        Returns:
            包含 system 和 user 消息的列表
        """
        result = self._renderer.render(ctx, runtime=runtime)
        return list(result.messages)
