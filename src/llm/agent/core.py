"""AgentCore - 核心决策逻辑组件."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from llm.agent.context_store import PersistentState, TurnContext
from llm.agent.decision_parser import DecisionParser, DecisionParseResult
from llm.agent.prompt_builder import build_assistant_turn_message

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.engine.state import GameState
    from llm.agent.context import EpisodeContext
    from llm.agent.conversation_logger import ConversationLogger
    from llm.agent.profile import PlayerProfile
    from llm.agent.prompt import PromptProjector
    from llm.agent.token_budget import PromptDiagnostics
    from llm.protocol import ChatMessage, CompletionClient

log = logging.getLogger(__name__)


@dataclass
class Decision:
    """Agent 决策结果."""

    action: "LegalAction"
    why: str | None
    history: list[Decision]  # 本局决策历史（决策链）
    prompt_diagnostics: "PromptDiagnostics | None" = None


class AgentCore:
    """核心决策逻辑组件.

    负责将所有决策相关逻辑整合在一起，包括：
    - 判断是否需要 LLM（唯一合法动作）
    - dry-run 模式
    - 构建 prompt
    - 调用 LLM
    - 解析响应
    - 处理 fallback
    """

    def __init__(
        self,
        profile: "PlayerProfile",
        prompt_mode: str,
    ) -> None:
        """初始化核心决策组件.

        Args:
            profile: 玩家 profile（用于配置信息）
            prompt_mode: Prompt 投影模式
        """
        self.profile = profile
        self.prompt_mode = prompt_mode

    def decide(
        self,
        state: "GameState",
        seat: int,
        *,
        episode_ctx: "EpisodeContext",
        prompt_projector: "PromptProjector",
        persistent_state: PersistentState,
        client: "CompletionClient | None",
        conversation_logger: "ConversationLogger | None" = None,
        dry_run: bool = False,
        session_audit: bool = False,
        request_delay_seconds: float = 0.0,
    ) -> Decision:
        """执行决策.

        Args:
            state: 当前游戏状态
            seat: 玩家座位
            episode_ctx: 本局运行时上下文
            prompt_projector: Prompt 投影器
            persistent_state: 当前长期状态快照
            client: LLM 客户端（dry_run 时可为 None）
            conversation_logger: 对话记录器（可选，用于调试）
            dry_run: 是否跳过 LLM 调用
            session_audit: 是否记录审计日志
            request_delay_seconds: LLM 调用前延迟

        Returns:
            Decision: 包含选择的动作、原因说明和决策历史

        Raises:
            RuntimeError: 如果没有合法动作
        """
        # 延迟导入避免循环依赖
        from kernel.api.legal_actions import legal_actions
        from kernel.api.observation import observation
        from kernel.engine.actions import ActionKind

        # 1. 获取合法动作
        acts = legal_actions(state, seat)
        if not acts:
            raise RuntimeError(f"no legal_actions for seat {seat}")

        # 2. 唯一合法动作为「过」或「摸牌」时跳过 LLM
        if len(acts) == 1 and acts[0].kind in (ActionKind.PASS_CALL, ActionKind.DRAW):
            if session_audit:
                log.info("llm_skipped singleton %s seat=%s", acts[0].kind.value, seat)
            return Decision(acts[0], None, episode_ctx.decision_history)

        # 3. dry_run 模式
        if dry_run or client is None:
            return Decision(acts[0], None, episode_ctx.decision_history)

        # 4. 构建 observation
        obs = observation(state, seat, mode="human")

        turn_context = TurnContext(
            observation=obs,
            legal_actions=acts,
            turn_index=len(episode_ctx.decision_history) + 1,
        )

        # 6. 构建消息
        projection = prompt_projector.build_projection(
            turn_context,
            persistent_state=persistent_state,
            episode_ctx=episode_ctx,
            compaction_client=client,
        )
        messages = projection.messages

        # 8. 调用 LLM
        if request_delay_seconds > 0:
            time.sleep(request_delay_seconds)

        raw = client.complete(messages)

        if session_audit:
            head = raw if len(raw) <= 600 else raw[:600] + "…"
            log.debug("llm raw_head seat=%s %r", seat, head)
            log.debug(
                "llm_history seat=%s history_msgs=%s",
                seat,
                len(episode_ctx.message_ledger.messages),
            )

        # 11. DEBUG: 保存最后一次请求
        _debug_save_last_prompt(messages)

        # 12. 解析响应
        parse_result = DecisionParser.parse_llm_response_detail(raw, acts)
        la, why = parse_result.action, parse_result.why
        fallback: LegalAction | None = None
        if la is None:
            fallback = DecisionParser.fallback_action(acts)

        # 13. 记录对话（仅真实对局，用于调试）
        if conversation_logger is not None and not dry_run:
            conversation_logger.log_turn(
                turn_number=len(episode_ctx.decision_history) + 1,
                seat=seat,
                phase=state.phase.value,
                messages=messages,
                response=raw,
                parser_result=_parser_log_payload(parse_result, fallback),
            )

        # 14. 处理解析失败
        if la is None:
            log.warning("parse or match failed, fallback first legal")
            if fallback is None:
                fallback = DecisionParser.fallback_action(acts)
            episode_ctx.append_user_message(
                messages[-1].content,
                turn_index=turn_context.turn_index,
            )
            episode_ctx.append_assistant_message(
                build_assistant_turn_message(fallback, None),
                turn_index=turn_context.turn_index,
            )
            episode_ctx.record_decision(
                Decision(fallback, None, []),
                observation=obs,
                legal_actions=acts,
                phase=state.phase.value,
            )
            return Decision(fallback, None, episode_ctx.decision_history, projection.diagnostics)

        # 15. 记录审计日志
        if session_audit:
            from llm.wire import legal_action_to_wire

            log.info(
                "llm_choice seat=%s %s",
                seat,
                json.dumps(legal_action_to_wire(la), ensure_ascii=False),
            )

        # 16. 更新历史
        episode_ctx.append_user_message(
            messages[-1].content,
            turn_index=turn_context.turn_index,
        )
        episode_ctx.append_assistant_message(
            build_assistant_turn_message(la, why),
            turn_index=turn_context.turn_index,
        )
        episode_ctx.record_decision(
            Decision(la, why, []),
            observation=obs,
            legal_actions=acts,
            phase=state.phase.value,
        )

        return Decision(la, why, episode_ctx.decision_history, projection.diagnostics)


def _parser_log_payload(
    result: DecisionParseResult,
    fallback_action: "LegalAction | None",
) -> dict[str, object]:
    """将解析结果转换为 conversation 可持久化的诊断载荷。"""
    from llm.wire import legal_action_to_wire

    payload: dict[str, object] = {"status": result.status}
    if result.note is not None:
        payload["note"] = result.note
    if result.error is not None:
        payload["error"] = result.error
    if result.why is not None:
        payload["why"] = result.why
    if result.choice is not None:
        payload["choice"] = result.choice
    if result.action is not None:
        payload["matched_action"] = legal_action_to_wire(result.action)
    if fallback_action is not None:
        payload["fallback_action"] = legal_action_to_wire(fallback_action)
    return payload


def _debug_save_last_prompt(messages: list["ChatMessage"]) -> None:
    """保存最后一次请求到 logs/last_sent_prompt.log.

    Args:
        messages: 消息列表
    """
    try:
        log_path = Path("logs/last_sent_prompt.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        for msg in messages:
            lines.append(f"[{msg.role}]")
            lines.append(msg.content)
            lines.append("")

        log_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        # 调试功能失败不应影响主流程
        pass
