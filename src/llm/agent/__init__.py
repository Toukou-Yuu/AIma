"""Agent 包 - LLM 玩家代理封装."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm.agent.core import AgentCore, Decision
from llm.agent.context_store import PersistentState
from llm.agent.decision_parser import DecisionParser
from llm.agent.persistence import PersistenceManager
from llm.agent.prompt import PromptProjector
from llm.agent.session import ModelSessionPolicy, SessionScope

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from llm.agent.context import EpisodeContext
    from llm.agent.context_store import CompressionLevel
    from llm.agent.stats import MatchStats
    from llm.protocol import CompletionClient

log = logging.getLogger(__name__)

# 导出 Decision 供外部使用
__all__ = ["PlayerAgent", "Decision"]


class PlayerAgent:
    """玩家代理 - 协调类（组合模式，无状态纯函数）.

    设计原则：
    - Agent 是无状态的"纯函数"，只保留长期状态（profile/memory/stats）
    - 运行时状态存储在 EpisodeContext 中，由外部（runner）管理
    - 跨局状态由 MatchContext 管理（Context Object 模式）
    - 通过组合各组件实现职责分离

    组件：
    - _persistence: 持久化管理（load/save profile/memory/stats）
    - _session_policy: 模型会话策略（session_id 生成）
    - _prompt_projector: Prompt 投影（system + user prompt）
    - _core: 核心决策逻辑（LLM 调用 + 解析）
    """

    def __init__(
        self,
        player_id: str | None = None,
        profile: "PlayerProfile | None" = None,
        memory: "PlayerMemory | None" = None,
        stats: "PlayerStats | None" = None,
        max_history_rounds: int = 10,
        history_budget: int | None = None,
        system_prompt: str | None = None,
        prompt_mode: str = "natural",
        compression_level: "CompressionLevel" = "collapse",
        session_scope: SessionScope = "per_hand",
        use_delta: bool = True,
    ) -> None:
        """初始化 Agent.

        Args:
            player_id: 玩家 ID（用于从文件加载长期状态）
            profile: 直接传入的 profile（优先级高于 player_id）
            memory: 直接传入的 memory（优先级高于 player_id）
            stats: 直接传入的 stats（优先级高于 player_id）
            max_history_rounds: 旧版历史轮数预算（兼容别名）
            history_budget: 历史预算（默认回退到 max_history_rounds）
            system_prompt: 系统提示词（从配置文件读取）
            prompt_mode: Prompt 投影模式（natural/json）
            compression_level: 历史压缩级别
            session_scope: 模型会话作用域
            use_delta: 是否启用状态差异法（默认启用）
        """
        self.player_id = player_id
        self.max_history_rounds = max_history_rounds
        self.history_budget = max(0, history_budget if history_budget is not None else max_history_rounds)
        self.system_prompt = system_prompt
        self.prompt_mode = prompt_mode
        self.compression_level = compression_level
        self.session_scope = session_scope
        self.use_delta = use_delta

        # 1. 创建持久化管理器
        self._persistence = PersistenceManager(player_id)

        # 2. 加载长期状态（优先使用传入的）
        from llm.agent.memory import PlayerMemory
        from llm.agent.profile import PlayerProfile
        from llm.agent.stats import PlayerStats

        self.profile = profile if profile is not None else self._persistence.load_profile()
        self.memory = memory if memory is not None else self._persistence.load_memory()
        self.stats = stats if stats is not None else self._persistence.load_stats()

        # 3. 创建会话管理器
        self._session_policy = ModelSessionPolicy(player_id, scope=session_scope)

        # 4. 创建 Prompt 构建器
        self._prompt_projector = PromptProjector(
            self.profile,
            system_prompt_base=system_prompt,
            prompt_mode=prompt_mode,
            use_delta=use_delta,
            history_budget=self.history_budget,
            compression_level=compression_level,
        )

        # 5. 创建核心决策组件
        self._core = AgentCore(self.profile, prompt_mode=prompt_mode, use_delta=use_delta)

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
            episode_ctx: 本局运行时上下文（含对话记录器）
            client: LLM 客户端（dry_run 时可为 None）
            dry_run: 是否跳过 LLM 调用
            session_audit: 是否记录审计日志
            request_delay_seconds: LLM 调用前延迟

        Returns:
            Decision: 包含选择的动作、原因说明和决策历史
        """
        return self._core.decide(
            state,
            seat,
            episode_ctx=episode_ctx,
            prompt_projector=self._prompt_projector,
            session_policy=self._session_policy,
            persistent_state=PersistentState(self.memory, self.stats),
            client=client,
            conversation_logger=episode_ctx.conversation_logger,
            dry_run=dry_run,
            session_audit=session_audit,
            request_delay_seconds=request_delay_seconds,
        )

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
        self.memory = self._persistence.update_memory(
            self.memory,
            episode_ctx.episode_stats,
            client,
        )

    def update_stats(
        self,
        episode_ctx: EpisodeContext,
        placement: int,
    ) -> None:
        """比赛结束后更新 stats.

        Args:
            episode_ctx: 本局运行时上下文
            placement: 最终排名（1-4）
        """
        self.stats = self._persistence.update_stats(
            self.stats,
            episode_ctx.match_stats,
            placement,
        )
