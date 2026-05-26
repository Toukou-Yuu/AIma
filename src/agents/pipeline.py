"""AgentPipeline - Agent决策流水线编排器.

职责：
- 编排完整决策流程：
  observation -> context -> memory -> prompt -> generate -> parse -> ground -> fallback
- 记录所有中间输出到 diagnostics
- 返回 PipelineResult

v4 改动：
- 显式调用 ContextBuilder（读取 ctx.event_history）
- 显式调用 MemoryManager（读取分层记忆）
- 构建 PromptRuntime，交给 PromptRenderer
- 调用 ModelBackend.generate() 替代旧 client.complete()
- diagnostics 包含 context / memory / token 信息
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from agents.pipeline_result import ParseStatus, PipelineResult
from agents.runtime import BuiltContext, BuiltObservation, MemoryReadResult, PromptRuntime
from llm.wire import legal_action_to_wire
from models.backend import ModelRequest, ModelResponse
from prompts.sections import estimate_tokens

if TYPE_CHECKING:
    from agents.components.factory import PipelineComponents
    from arena.policy import DecisionContext
    from kernel.api.legal_actions import LegalAction


class AgentPipeline:
    """Agent决策流水线编排器.

    编排完整决策流程，处理解析失败和接地失败，提供回退机制。
    """

    def __init__(
        self,
        components: "PipelineComponents",
        backend: Any | None = None,
    ) -> None:
        """初始化流水线.

        Args:
            components: 流水线组件容器
            backend: ModelBackend。保留该参数以兼容既有调用点。
        """
        self.components = components
        self.backend = backend

    def run(self, ctx: "DecisionContext") -> PipelineResult:
        """执行决策流水线.

        流程：
        1. observation: 构建观测描述（ObservationBuilder）
        2. context: 构建公共历史（ContextBuilder，读 ctx.event_history）
        3. memory: 读取分层记忆（MemoryManager）
        4. runtime: 组装 PromptRuntime
        5. prompt: 渲染提示词（PromptRenderer，从 runtime 读取）
        6. generate: 调用 ModelBackend.generate()
        7. parse: 解析 LLM 响应
        8. ground: 接地到合法动作
        9. fallback: 必要时选择回退动作

        Args:
            ctx: 决策上下文（arena.policy.DecisionContext，含 event_history）

        Returns:
            PipelineResult 包含最终动作和诊断信息
        """
        start_time = time.perf_counter()
        diagnostics: dict[str, Any] = {}

        # Step 1: observation
        observation_text = self.components.observation.build(ctx)
        built_observation = BuiltObservation(text=observation_text)
        diagnostics["observation"] = observation_text

        # Step 2: context（读取 ctx.event_history，构建公共历史）
        built_context = self._build_context(ctx)
        diagnostics["context"] = {
            "scope": built_context.scope,
            "raw_event_count": built_context.raw_event_count,
            "rendered_event_count": built_context.rendered_event_count,
            "truncated": built_context.truncated,
            "token_estimate": estimate_tokens(built_context.text),
        }
        diagnostics["context_scope"] = built_context.scope
        diagnostics["context_event_count"] = built_context.rendered_event_count
        diagnostics["context_truncated"] = built_context.truncated
        diagnostics["context_token_estimate"] = estimate_tokens(built_context.text)

        # Step 3: memory（读取分层记忆）
        memory_result = self._read_memory(ctx)
        diagnostics["memory"] = {
            "layers": list(memory_result.layers),
            "token_estimate": memory_result.token_estimate,
        }
        diagnostics["memory_layers"] = list(memory_result.layers)
        diagnostics["memory_injected_tokens"] = memory_result.token_estimate

        # Step 4: 组装 PromptRuntime
        runtime = PromptRuntime(
            decision=ctx,
            observation=built_observation,
            context=built_context,
            memory=memory_result,
        )

        # Step 5: prompt（使用 PromptRenderer，传入 runtime）
        messages = self.components.prompt.render(ctx, runtime)
        diagnostics["messages"] = [(m.role, m.content) for m in messages]
        diagnostics["prompt_template"] = self.components.prompt._template_id
        diagnostics["prompt_token_estimate"] = sum(
            estimate_tokens(m.content) for m in messages
        )

        # Step 6: generate（ModelBackend.generate，替代旧 client.complete）
        model_request = ModelRequest(messages=list(messages))
        model_response = self._generate(model_request)
        raw_output = model_response.text
        diagnostics["raw_output"] = raw_output
        diagnostics["prompt_tokens"] = (
            model_response.prompt_tokens
            if model_response.prompt_tokens is not None
            else diagnostics["prompt_token_estimate"]
        )
        diagnostics["completion_tokens"] = model_response.completion_tokens
        diagnostics["backend_name"] = model_response.backend_name
        diagnostics["model_name"] = model_response.model_name
        diagnostics["finish_reason"] = model_response.finish_reason
        diagnostics["model_latency_ms"] = model_response.latency_ms

        # Step 7: parse
        parse_result = self.components.parser.parse(raw_output, ctx.legal_actions)
        diagnostics["parse_result"] = {
            "choice": parse_result.choice,
            "why": parse_result.why,
            "status": parse_result.status,
            "error": parse_result.error,
        }
        parse_status: ParseStatus = parse_result.status

        # Step 8: ground
        legal_action: LegalAction | None = None
        fallback_used = False

        if parse_result.choice is not None:
            ground_result = self.components.grounder.ground(
                ctx.legal_actions,
                parse_result.choice,
            )
            diagnostics["ground_result"] = {
                "legal_action": (
                    legal_action_to_wire(ground_result.legal_action)
                    if ground_result.legal_action
                    else None
                ),
                "status": ground_result.status,
            }
            if ground_result.legal_action is not None:
                legal_action = ground_result.legal_action
            else:
                parse_status = "match_failed"

        # Step 9: fallback
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

    def _generate(self, request: ModelRequest) -> ModelResponse:
        """Call the configured backend through ModelBackend.generate().

        Older tests and adapters still provide only ``complete()``. Those are
        adapted at the boundary so the pipeline's main path still produces a
        full ModelResponse shape for diagnostics and metrics.
        """
        backend = self.backend or getattr(self.components, "backend", None)
        if backend is None:
            msg = "AgentPipeline requires a model backend"
            raise ValueError(msg)

        if hasattr(backend, "generate"):
            return backend.generate(request)

        if hasattr(backend, "complete"):
            start = time.perf_counter()
            text = backend.complete(request.messages)
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelResponse(
                text=text,
                finish_reason="stop",
                latency_ms=latency_ms,
                backend_name=backend.__class__.__name__,
                model_name="unknown",
            )

        msg = "Backend must implement generate() or complete()"
        raise TypeError(msg)

    def _build_context(self, ctx: "DecisionContext") -> BuiltContext:
        """调用 ContextBuilder 构建公共历史.

        Args:
            ctx: 决策上下文（含 event_history）

        Returns:
            BuiltContext，若无 ContextBuilder 则返回空 context
        """
        if self.components.context is None:
            return BuiltContext.empty(scope="stateless")

        # ContextBuilder.build() 接受 list[context.events.ContextEvent]
        # ctx.event_history 是 v4-native ContextEvent 元组
        from context.builders import ContextBuilder as _CB  # 本地导入避免循环
        builder: _CB = self.components.context
        events = list(ctx.event_history)
        current_turn_index = max(
            (
                ev.turn_index
                for ev in events
                if getattr(ev, "hand_index", ctx.hand_index) == ctx.hand_index
            ),
            default=0,
        )
        result = builder.build(
            events,
            current_hand_index=ctx.hand_index,
            current_turn_index=current_turn_index,
            self_seat=ctx.seat,
        )
        return BuiltContext(
            text=result.text,
            raw_event_count=result.raw_event_count,
            rendered_event_count=result.rendered_event_count,
            scope=builder.spec.scope,
            truncated=result.prompt_truncated,
        )

    def _read_memory(self, ctx: "DecisionContext") -> MemoryReadResult:
        """读取分层记忆.

        Args:
            ctx: 决策上下文

        Returns:
            MemoryReadResult，若无 MemoryManager 则返回空结果
        """
        if self.components.memory is None:
            return MemoryReadResult.empty()

        player_id = self.components.memory.player_id_for_seat(ctx.seat)
        rendered_text, layers = self.components.memory.get_memory_prompt(player_id)
        token_estimate = estimate_tokens(rendered_text) if rendered_text else 0

        return MemoryReadResult(
            rendered_text=rendered_text,
            layers=layers,
            token_estimate=token_estimate,
        )
