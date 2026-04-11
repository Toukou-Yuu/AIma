"""PersistenceManager - 持久化管理组件.

职责：
- 加载/保存 PlayerProfile
- 加载/保存 PlayerMemory
- 加载/保存 PlayerStats
- 更新长期状态（memory/stats）
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.agent.memory import EpisodeStats, PlayerMemory
    from llm.agent.profile import PlayerProfile
    from llm.agent.stats import MatchStats, PlayerStats
    from llm.protocol import CompletionClient

log = logging.getLogger(__name__)


class PersistenceManager:
    """持久化管理组件.

    管理玩家长期状态（profile/memory/stats）的加载和保存。
    """

    def __init__(
        self,
        player_id: str | None = None,
        players_dir: str = "configs/players",
    ) -> None:
        """初始化持久化管理器.

        Args:
            player_id: 玩家 ID（可选，无 ID 时使用默认状态）
            players_dir: players 配置目录
        """
        self.player_id = player_id
        self.players_dir = players_dir

    def load_profile(self) -> "PlayerProfile":
        """加载玩家 profile.

        Returns:
            PlayerProfile（如果 player_id 为 None 或文件不存在，返回默认）
        """
        from llm.agent.profile import PlayerProfile, load_profile

        if self.player_id is None:
            return self._default_profile()

        loaded = load_profile(self.player_id, self.players_dir)
        return loaded if loaded is not None else self._default_profile()

    def load_memory(self) -> "PlayerMemory":
        """加载玩家 memory.

        Returns:
            PlayerMemory（如果 player_id 为 None 或文件不存在，返回默认）
        """
        from llm.agent.memory import PlayerMemory, load_memory

        if self.player_id is None:
            return PlayerMemory()

        return load_memory(self.player_id, self.players_dir)

    def load_stats(self) -> "PlayerStats":
        """加载玩家 stats.

        Returns:
            PlayerStats（如果 player_id 为 None 或文件不存在，返回默认）
        """
        from llm.agent.stats import PlayerStats, load_stats

        if self.player_id is None:
            return PlayerStats()

        return load_stats(self.player_id, self.players_dir)

    def save_memory(self, memory: "PlayerMemory") -> None:
        """保存玩家 memory.

        Args:
            memory: 要保存的 PlayerMemory
        """
        if self.player_id is None:
            log.debug("跳过 memory 保存：player_id 为 None")
            return

        from llm.agent.memory import save_memory

        save_memory(self.player_id, memory, self.players_dir)
        log.info("已保存 memory: player_id=%s", self.player_id)

    def save_stats(self, stats: "PlayerStats") -> None:
        """保存玩家 stats.

        Args:
            stats: 要保存的 PlayerStats
        """
        if self.player_id is None:
            return

        from llm.agent.stats import save_stats

        save_stats(self.player_id, stats, self.players_dir)
        log.info("已保存 stats: player_id=%s", self.player_id)

    def update_memory(
        self,
        current_memory: "PlayerMemory",
        episode_stats: "EpisodeStats",
        client: "CompletionClient | None" = None,
    ) -> "PlayerMemory":
        """根据本局统计更新 memory.

        Args:
            current_memory: 当前 memory
            episode_stats: 本局统计
            client: 可选的 LLM 客户端（启用 LLM 润色）

        Returns:
            更新后的 PlayerMemory
        """
        if self.player_id is None:
            log.debug("跳过 memory 更新：player_id 为 None")
            return current_memory

        if client is not None:
            from llm.agent.llm_summarizer import LLMSummarizer

            summarizer = LLMSummarizer(client)
            new_memory = summarizer.polish(current_memory, episode_stats)
        else:
            from llm.agent.memory import EpisodeSummarizer

            summarizer = EpisodeSummarizer()
            new_memory = summarizer.summarize(episode_stats, current_memory)

        self.save_memory(new_memory)
        return new_memory

    def update_stats(
        self,
        current_stats: "PlayerStats",
        match_stats: "MatchStats",
        placement: int,
    ) -> "PlayerStats":
        """根据本场统计更新 stats.

        Args:
            current_stats: 当前 stats
            match_stats: 本场统计
            placement: 最终排名（1-4）

        Returns:
            更新后的 PlayerStats
        """
        if self.player_id is None:
            return current_stats

        from llm.agent.stats import StatsAggregator

        match_stats.placement = placement
        aggregator = StatsAggregator()
        new_stats = aggregator.update(current_stats, match_stats)

        self.save_stats(new_stats)
        return new_stats

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