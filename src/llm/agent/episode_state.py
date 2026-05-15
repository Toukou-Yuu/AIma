"""EpisodeState - 本局纯状态容器."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from llm.agent.memory import EpisodeStats
from llm.agent.stats import MatchStats

if TYPE_CHECKING:
    from llm.agent import Decision


@dataclass
class EpisodeState:
    """本局纯状态容器.

    不含业务逻辑，只存储状态数据。
    """

    seat: int
    match_id: str = ""
    hand_number: int = 1
    episode_stats: EpisodeStats = field(default_factory=lambda: EpisodeStats("", 0))
    match_stats: MatchStats = field(default_factory=MatchStats)
    match_history_archive: tuple[str, ...] = ()
    decision_history: list[Decision] = field(default_factory=list)

    def __post_init__(self):
        """初始化后确保 episode_stats 的 seat 正确."""
        if self.episode_stats.seat != self.seat:
            self.episode_stats.seat = self.seat