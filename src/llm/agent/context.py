"""EpisodeContext - 本局运行时上下文（Agent 无状态化的关键）."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from llm.agent.memory import EpisodeStats
from llm.agent.stats import MatchStats

if TYPE_CHECKING:
    from llm.agent import Decision


@dataclass
class EpisodeContext:
    """本局运行时上下文.

    用于将 Agent 从"状态容器"改为"纯函数".
    运行时状态（本局统计、本场统计、决策历史）存储在此，
    Agent 只保留长期状态（profile/memory/stats）.
    """

    seat: int
    episode_stats: EpisodeStats = field(default_factory=lambda: EpisodeStats("", 0))
    match_stats: MatchStats = field(default_factory=MatchStats)
    decision_history: list[Decision] = field(default_factory=list)

    def __post_init__(self):
        """初始化后确保 episode_stats 的 seat 正确."""
        if self.episode_stats.seat != self.seat:
            self.episode_stats.seat = self.seat

    def record_win(self, win_tile: str) -> None:
        """记录和了."""
        self.episode_stats.wins += 1
        self.episode_stats.win_tiles.append(win_tile)
        if self.episode_stats.riichi_count > 0:
            self.episode_stats.riichi_win += 1

        self.match_stats.wins += 1
        if self.match_stats.riichi_count > 0:
            self.match_stats.riichi_wins += 1

    def record_deal_in(self, deal_in_tile: str) -> None:
        """记录放铳."""
        self.episode_stats.deal_ins += 1
        self.episode_stats.deal_in_tiles.append(deal_in_tile)
        if self.episode_stats.riichi_count > 0:
            self.episode_stats.riichi_deal_in += 1

        self.match_stats.deal_ins += 1
        if self.match_stats.riichi_count > 0:
            self.match_stats.riichi_deal_ins += 1

    def record_riichi(self) -> None:
        """记录立直宣言."""
        self.episode_stats.riichi_count += 1
        self.match_stats.riichi_count += 1

    def record_decision(self, decision: Decision) -> None:
        """记录决策到历史."""
        self.decision_history.append(decision)

    def end_episode(self, points: int) -> None:
        """结束本局，更新统计."""
        self.episode_stats.total_points = points
        self.episode_stats.hands_played = 1
        self.match_stats.points += points
        self.match_stats.hands += 1
