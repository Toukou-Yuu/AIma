"""Agent 包 - LLM 玩家代理封装.

重构后的架构：
- PlayerAgent: 协调类，组合各组件（无状态纯函数）
- AgentCore: 核心决策逻辑
- SessionManager: 会话管理
- PromptBuilder: Prompt 构建
- DecisionParser: 决策解析
- PersistenceManager: 持久化管理
- MatchContext: 跨局状态管理（Context Object 模式）
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm.agent.core import AgentCore, Decision
from llm.agent.decision_parser import DecisionParser
from llm.agent.persistence import PersistenceManager
from llm.agent.prompt import PromptBuilder
from llm.agent.session import SessionManager

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from llm.agent.context import EpisodeContext
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
    - _session: 会话管理（session_id 生成）
    - _prompt_builder: Prompt 构建（system + user prompt）
    - _core: 核心决策逻辑（LLM 调用 + 解析）
    """

    def __init__(
        self,
        player_id: str | None = None,
        profile: "PlayerProfile | None" = None,
        memory: "PlayerMemory | None" = None,
        stats: "PlayerStats | None" = None,
        max_history_rounds: int = 10,
        system_prompt: str | None = None,
        use_compression: bool = True,
        use_delta: bool = True,
    ) -> None:
        """初始化 Agent.

        Args:
            player_id: 玩家 ID（用于从文件加载长期状态）
            profile: 直接传入的 profile（优先级高于 player_id）
            memory: 直接传入的 memory（优先级高于 player_id）
            stats: 直接传入的 stats（优先级高于 player_id）
            max_history_rounds: 最大历史对话轮数
            system_prompt: 系统提示词（从配置文件读取）
            use_compression: 是否启用上下文压缩（默认启用）
            use_delta: 是否启用状态差异法（默认启用）
        """
        self.player_id = player_id
        self.max_history_rounds = max_history_rounds
        self.system_prompt = system_prompt
        self.use_compression = use_compression
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
        self._session = SessionManager(player_id)

        # 4. 创建 Prompt 构建器
        self._prompt_builder = PromptBuilder(
            self.profile,
            self.memory,
            self.stats,
            system_prompt,
            use_compression,
            use_delta,
        )

        # 5. 创建核心决策组件
        self._core = AgentCore(self.profile, use_compression, use_delta)

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
            episode_ctx: 本局运行时上下文
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
            prompt_builder=self._prompt_builder,
            session_manager=self._session,
            client=client,
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