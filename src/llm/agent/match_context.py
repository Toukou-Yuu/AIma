"""MatchContext - 本场比赛跨局状态管理（Context Object 模式）.

职责：
- 封装本场累积状态（match_stats）
- 创建 EpisodeContext（Factory 模式）
- 维护局间状态传递

生命周期：一场比赛（多局）的全程
约束：禁止外部直接修改 match_stats（高内聚）

设计模式：
- Context Object Pattern：将跨局状态封装在独立对象中
- Factory Pattern：统一创建 EpisodeContext 的入口
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llm.agent.context import EpisodeContext
from llm.agent.stats import MatchStats

if TYPE_CHECKING:
    pass


class MatchContext:
    """管理一场比赛的跨局状态（Context Object 模式）.

    职责：
    - 封装本场累积状态（match_stats）
    - 创建 EpisodeContext（Factory 模式）
    - 维护局间状态传递

    生命周期：一场比赛（多局）的全程
    约束：禁止外部直接修改 match_stats（高内聚）
    """

    def __init__(self, seat: int) -> None:
        """初始化本场上下文.

        Args:
            seat: 玩家座位（0-3）
        """
        self._seat = seat
        self._match_stats = MatchStats()  # 私有，确保高内聚
        self._episodes: list[EpisodeContext] = []

    @property
    def seat(self) -> int:
        """座位号（只读）."""
        return self._seat

    def create_episode(self) -> EpisodeContext:
        """创建新局上下文（Factory 模式）.

        返回包含当前 match_stats 副本的新上下文，确保隔离。
        修改 EpisodeContext 的 match_stats 不影响 MatchContext。

        Returns:
            EpisodeContext: 新的本局上下文
        """
        return EpisodeContext(self._seat, match_stats=self._match_stats.copy())

    def close_episode(self, episode_ctx: EpisodeContext) -> None:
        """关闭本局（更新本场统计）.

        通过显式方法调用，避免隐式状态共享。

        Args:
            episode_ctx: 本局结束后的上下文
        """
        self._match_stats = episode_ctx.match_stats
        self._episodes.append(episode_ctx)

    def reset(self) -> None:
        """重置本场状态（新比赛开始）."""
        self._match_stats = MatchStats()
        self._episodes = []

    def get_stats(self) -> MatchStats:
        """获取本场统计（只读副本）.

        避免外部修改内部状态。

        Returns:
            MatchStats: 统计副本
        """
        return self._match_stats.copy()