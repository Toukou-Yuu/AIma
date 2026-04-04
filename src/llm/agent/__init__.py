"""Agent 包 - LLM 玩家代理封装."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.engine.state import GameState
    from llm.agent.context import EpisodeContext
    from llm.protocol import ChatMessage, CompletionClient

log = logging.getLogger(__name__)


@dataclass
class Decision:
    """Agent 决策结果."""

    action: "LegalAction"
    why: str | None
    history: list["ChatMessage"]


class PlayerAgent:
    """玩家代理 - 封装 LLM 调用和状态管理.

    设计原则：Agent 是无状态的"纯函数"，只保留长期状态（profile/memory/stats）。
    运行时状态（本局统计、本场统计、决策历史）存储在 EpisodeContext 中，
    由外部（runner）管理。
    """

    def __init__(
        self,
        player_id: str | None = None,
        profile: "PlayerProfile | None" = None,
        memory: "PlayerMemory | None" = None,
        stats: "PlayerStats | None" = None,
        max_history_rounds: int = 10,
    ):
        """初始化 Agent.

        Args:
            player_id: 玩家 ID（用于从文件加载长期状态）
            profile: 直接传入的 profile（优先级高于 player_id）
            memory: 直接传入的 memory（优先级高于 player_id）
            stats: 直接传入的 stats（优先级高于 player_id）
            max_history_rounds: 最大历史对话轮数
        """
        self.player_id = player_id
        self.max_history_rounds = max_history_rounds

        # 加载 profile（长期状态）
        if profile is not None:
            self.profile = profile
        elif player_id is not None:
            from llm.agent.profile import load_profile
            loaded = load_profile(player_id)
            self.profile = loaded if loaded is not None else self._default_profile()
        else:
            self.profile = self._default_profile()

        # 加载 memory（长期状态）
        if memory is not None:
            self.memory = memory
        elif player_id is not None:
            from llm.agent.memory import load_memory
            self.memory = load_memory(player_id)
        else:
            from llm.agent.memory import PlayerMemory
            self.memory = PlayerMemory()

        # 加载 stats（长期状态）
        if stats is not None:
            self.stats = stats
        elif player_id is not None:
            from llm.agent.stats import load_stats
            self.stats = load_stats(player_id)
        else:
            from llm.agent.stats import PlayerStats
            self.stats = PlayerStats()

    def _default_profile(self) -> "PlayerProfile":
        """返回默认 profile."""
        from llm.agent.profile import PlayerProfile
        return PlayerProfile(
            id="default",
            name="DefaultBot",
            model="gpt-4o-mini",
            provider="openai",
            temperature=0.7,
            max_tokens=1024,
            timeout_sec=120.0,
            persona_prompt="",
            strategy_prompt="",
        )

    def decide(
        self,
        state: GameState,
        seat: int,
        *,
        episode_ctx: EpisodeContext,
        client: CompletionClient | None,
        dry_run: bool = False,
        session_audit: bool = False,
        request_delay_seconds: float = 0.0,
    ) -> Decision:
        """根据当前局面做出决策.

        Args:
            state: 当前游戏状态
            seat: 玩家座位
            episode_ctx: 本局运行时上下文（包含统计、历史等）
            client: LLM 客户端（dry_run 时可为 None）
            dry_run: 是否跳过 LLM 调用，直接选第一个合法动作
            session_audit: 是否记录审计日志
            request_delay_seconds: LLM 调用前延迟

        Returns:
            Decision: 包含选择的动作、原因说明和更新后的历史
        """
        # 延迟导入避免循环依赖
        from kernel.api.legal_actions import legal_actions
        from kernel.api.observation import observation
        from kernel.engine.actions import ActionKind
        from llm.agent.prompt_builder import build_decision_prompt, build_system_prompt
        from llm.parse import extract_json_object
        from llm.protocol import ChatMessage
        from llm.validate import explain_text_from_choice, find_matching_legal_action
        from llm.wire import legal_action_to_wire

        # 1. 获取合法动作
        acts = legal_actions(state, seat)
        if not acts:
            msg = f"no legal_actions for seat {seat}"
            raise RuntimeError(msg)

        # 2. 唯一合法动作为「过」或「摸牌」时跳过 LLM（无需决策）
        if len(acts) == 1 and acts[0].kind in (ActionKind.PASS_CALL, ActionKind.DRAW):
            if session_audit:
                log.info("llm_skipped singleton %s seat=%s", acts[0].kind.value, seat)
            return Decision(acts[0], None, episode_ctx.decision_history)

        # 3. dry_run 模式
        if dry_run or client is None:
            return Decision(acts[0], None, episode_ctx.decision_history)

        # 4. 构建 observation 和 prompt
        obs = observation(state, seat, mode="human")
        user_content = build_decision_prompt(obs, acts)
        current_user_msg = ChatMessage(role="user", content=user_content)

        # 5. 拼装消息（使用 profile 的 persona/strategy + memory + stats）
        messages = [ChatMessage(role="system", content=build_system_prompt(self.profile, self.memory, self.stats))]

        # 注入本局决策历史（纯文本格式）
        if episode_ctx.decision_history:
            history_text = episode_ctx.format_history_for_prompt()
            if history_text:
                history_msg = ChatMessage(
                    role="user",
                    content=f"本局前期决策历史：\n{history_text}\n---"
                )
                messages.append(history_msg)

        messages.append(current_user_msg)

        # DEBUG: 记录完整 prompt
        if session_audit:
            full_prompt = "\n\n".join([f"[{m.role}]\n{m.content}" for m in messages])
            log.debug("llm_full_prompt seat=%s:\n%s", seat, full_prompt)
            # 同时写入文件确保能看到
            debug_file = Path("logs/debug/last_prompt.txt")
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            debug_file.write_text(full_prompt, encoding="utf-8")
        if request_delay_seconds > 0:
            time.sleep(request_delay_seconds)
        raw = client.complete(messages)
        if session_audit:
            head = raw if len(raw) <= 600 else raw[:600] + "…"
            log.debug("llm raw_head seat=%s %r", seat, head)
            # 记录历史消息数量
            hist_len = len(episode_ctx.decision_history)
            log.debug("llm_history seat=%s history_msgs=%s", seat, hist_len)

        # 7. 解析和校验
        try:
            choice = extract_json_object(raw)
        except (ValueError, TypeError) as e:
            log.warning("parse failed, fallback first legal: %s", e)
            return Decision(acts[0], None, episode_ctx.decision_history)

        why = explain_text_from_choice(choice)
        la = find_matching_legal_action(acts, choice)

        # 8. 构建 assistant 消息内容
        assistant_content = json.dumps(choice, ensure_ascii=False)

        # 9. 处理匹配失败的情况（仍记录历史）
        if la is None:
            log.warning("choice not in legal_actions, fallback first: %s", choice)
            episode_ctx.record_decision(Decision(acts[0], None, []))
            return Decision(acts[0], None, episode_ctx.decision_history)

        # 10. 记录审计日志
        if session_audit:
            log.info(
                "llm_choice seat=%s %s",
                seat,
                json.dumps(legal_action_to_wire(la), ensure_ascii=False),
            )

        # 11. 更新历史
        episode_ctx.record_decision(Decision(la, why, []))

        return Decision(la, why, episode_ctx.decision_history)

    def update_memory(
        self,
        episode_ctx: EpisodeContext,
        client: CompletionClient | None = None,
    ) -> None:
        """局结束后更新 memory.

        Args:
            episode_ctx: 本局运行时上下文
            client: 可选的 LLM 客户端（启用 LLM 润色）
        """
        if self.player_id is None:
            return

        # 更新 memory
        if client is not None:
            from llm.agent.llm_summarizer import LLMSummarizer
            from llm.agent.memory import save_memory
            summarizer = LLMSummarizer(client)
            new_memory = summarizer.polish(self.memory, episode_ctx.episode_stats)
        else:
            from llm.agent.memory import EpisodeSummarizer, save_memory
            summarizer = EpisodeSummarizer()
            new_memory = summarizer.summarize(episode_ctx.episode_stats, self.memory)

        self.memory = new_memory
        save_memory(self.player_id, new_memory)

    def update_stats(self, episode_ctx: EpisodeContext, placement: int) -> None:
        """比赛结束后更新 stats.

        Args:
            episode_ctx: 本局运行时上下文（包含本场统计）
            placement: 最终排名（1-4）
        """
        if self.player_id is None:
            return

        from llm.agent.stats import StatsAggregator, save_stats

        episode_ctx.match_stats.placement = placement
        aggregator = StatsAggregator()
        new_stats = aggregator.update(self.stats, episode_ctx.match_stats)
        self.stats = new_stats
        save_stats(self.player_id, new_stats)
