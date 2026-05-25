"""AgentPipeline - Agent决策流水线编排器.

职责：
- 编排6步决策流程：observation -> prompt -> call -> parse -> ground -> fallback
- 记录所有中间输出到 diagnostics
- 返回 PipelineResult
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from agents.pipeline_result import ParseStatus, PipelineResult
from llm.wire import legal_action_to_wire

if TYPE_CHECKING:
    from agents.components.factory import PipelineComponents
    from arena.policy import DecisionContext
    from kernel.api.legal_actions import LegalAction
    from llm.protocol import CompletionClient


class AgentPipeline:
    """Agent决策流水线编排器.

    编排6步决策流程，处理解析失败和接地失败，提供回退机制。
    """

    def __init__(
        self,
        components: "PipelineComponents",
        client: "CompletionClient",
    ) -> None:
        """初始化流水线.

        Args:
            components: 流水线组件容器
            client: LLM 补全客户端
        """
        self.components = components
        self.client = client

    def run(self, ctx: "DecisionContext") -> PipelineResult:
        """执行决策流水线.

        流程：
        1. observation: 构建观测描述
        2. prompt: 渲染提示词（使用真正的 prompts/renderer.py）
        3. call: 调用 LLM
        4. parse: 解析 LLM 响应
        5. ground: 接地到合法动作
        6. fallback: 必要时选择回退动作

        Args:
            ctx: 决策上下文（arena.policy.DecisionContext）

        Returns:
            PipelineResult 包含最终动作和诊断信息
        """
        start_time = time.perf_counter()
        diagnostics: dict[str, object] = {}

        # Step 1: observation
        observation_text = self.components.observation.build(ctx)
        diagnostics["observation"] = observation_text

        # Step 2: prompt（使用真正的 prompts/renderer.py）
        messages = self.components.prompt.render(ctx)
        diagnostics["messages"] = [(m.role, m.content) for m in messages]
        diagnostics["prompt_template"] = self.components.prompt._template_id

        # Step 3: call
        raw_output = self.client.complete(messages)
        diagnostics["raw_output"] = raw_output

        # Step 4: parse
        parse_result = self.components.parser.parse(raw_output, ctx.legal_actions)
        diagnostics["parse_result"] = {
            "choice": parse_result.choice,
            "why": parse_result.why,
            "status": parse_result.status,
            "error": parse_result.error,
        }
        parse_status: ParseStatus = parse_result.status

        # Step 5: ground
        legal_action: LegalAction | None = None
        fallback_used = False

        if parse_result.choice is not None:
            ground_result = self.components.grounder.ground(
                ctx.legal_actions,
                parse_result.choice,
            )
            diagnostics["ground_result"] = {
                "legal_action": legal_action_to_wire(ground_result.legal_action) if ground_result.legal_action else None,
                "status": ground_result.status,
            }
            if ground_result.legal_action is not None:
                legal_action = ground_result.legal_action
            else:
                parse_status = "match_failed"

        # Step 6: fallback
        if legal_action is None and self.components.fallback.should_fallback(parse_status):
            legal_action = self.components.fallback.select(ctx.legal_actions)
            fallback_used = True
            diagnostics["fallback_used"] = True

        # Calculate latency
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        return PipelineResult(
            action=legal_action,
            parse_status=parse_status,
            fallback_used=fallback_used,
            raw_output=raw_output,
            diagnostics=diagnostics,
            latency_ms=latency_ms,
        )