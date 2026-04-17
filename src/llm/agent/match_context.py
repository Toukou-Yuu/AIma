"""MatchContext - 本场比赛跨局状态管理（Context Object 模式）.

职责：
- 封装本场累积状态（match_stats）
- 创建 EpisodeContext（Factory 模式）
- 维护局间状态传递
- 管理对话记录器的生命周期

生命周期：一场比赛（多局）的全程
约束：禁止外部直接修改 match_stats（高内聚）

设计模式：
- Context Object Pattern：将跨局状态封装在独立对象中
- Factory Pattern：统一创建 EpisodeContext 的入口
"""

from __future__ import annotations

from uuid import uuid4

from typing import TYPE_CHECKING

from llm.agent.context import EpisodeContext
from llm.agent.event_journal import MatchJournal
from llm.agent.session import ConversationIdNamer
from llm.agent.stats import MatchStats

if TYPE_CHECKING:
    pass


class MatchContext:
    """管理一场比赛的跨局状态（Context Object 模式）.

    职责：
    - 封装本场累积状态（match_stats）
    - 创建 EpisodeContext（Factory 模式）
    - 维护局间状态传递
    - 管理对话记录器的生命周期

    生命周期：一场比赛（多局）的全程
    约束：禁止外部直接修改 match_stats（高内聚）
    """

    def __init__(
        self,
        seat: int,
        player_id: str | None = None,
        *,
        match_journal: MatchJournal | None = None,
    ) -> None:
        """初始化本场上下文.

        Args:
            seat: 玩家座位（0-3）
            player_id: 玩家 ID（可选，用于对话日志）
        """
        self._seat = seat
        self._player_id = player_id
        self._match_stats = MatchStats()  # 私有，确保高内聚
        self._episodes: list[EpisodeContext] = []
        self._hand_archives: list[str] = []
        self._match_journal = match_journal
        self._match_id = str(uuid4())[:8]
        self._log_namer = ConversationIdNamer(player_id)
        self._hand_number = 0  # 追踪当前局号

    @property
    def seat(self) -> int:
        """座位号（只读）."""
        return self._seat

    def create_episode(
        self,
        enable_conversation_logging: bool = False,
    ) -> EpisodeContext:
        """创建新局上下文（Factory 模式）.

        返回包含当前 match_stats 副本的新上下文，确保隔离。
        修改 EpisodeContext 的 match_stats 不影响 MatchContext。

        Args:
            enable_conversation_logging: 是否启用对话记录（需要 player_id）

        Returns:
            EpisodeContext: 新的本局上下文
        """
        self._hand_number += 1  # 局号递增
        ctx = EpisodeContext(
            self._seat,
            match_id=self._match_id,
            hand_number=self._hand_number,
            match_stats=self._match_stats.copy(),
            match_history_archive=tuple(self._hand_archives),
            match_journal=self._match_journal,
        )

        # 如果启用对话记录且有 player_id，创建 ConversationLogger
        if enable_conversation_logging and self._player_id is not None:
            from llm.agent.conversation_logger import ConversationLogger

            conversation_id = self._log_namer.build_conversation_id(
                self._seat,
                hand_number=self._hand_number,
            )
            ctx.conversation_logger = ConversationLogger(
                player_id=self._player_id,
                conversation_id=conversation_id,
                enabled=True,
            )

        return ctx

    def close_episode(self, episode_ctx: EpisodeContext) -> None:
        """关闭本局（更新本场统计）.

        通过显式方法调用，避免隐式状态共享。
        同时关闭对话记录器（如果存在）。

        Args:
            episode_ctx: 本局结束后的上下文
        """
        # 关闭对话记录器
        if episode_ctx.conversation_logger is not None:
            episode_ctx.conversation_logger.close()
            episode_ctx.conversation_logger = None

        self._match_stats = episode_ctx.match_stats
        hand_summary = episode_ctx.build_hand_summary()
        if hand_summary:
            self._hand_archives.append(hand_summary)
        self._episodes.append(episode_ctx)

    def reset(self) -> None:
        """重置本场状态（新比赛开始）."""
        self._match_stats = MatchStats()
        self._episodes = []
        self._hand_archives = []
        self._match_id = str(uuid4())[:8]
        self._hand_number = 0

    def get_stats(self) -> MatchStats:
        """获取本场统计（只读副本）.

        避免外部修改内部状态。

        Returns:
            MatchStats: 统计副本
        """
        return self._match_stats.copy()
