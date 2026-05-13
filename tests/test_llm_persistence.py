"""llm.agent.persistence 覆盖缺口测试。

覆盖：None player_id 的 early-return 路径（load_memory, load_stats,
save_memory, save_stats, update_memory, update_stats）。"""

from __future__ import annotations

from llm.agent.memory import EpisodeStats, PlayerMemory
from llm.agent.persistence import PersistenceManager
from llm.agent.stats import MatchStats, PlayerStats


# --- None player_id early returns ---

class TestPersistenceManagerNoneId:
    def test_load_memory_returns_default(self) -> None:
        pm = PersistenceManager(player_id=None)
        memory = pm.load_memory()
        assert isinstance(memory, PlayerMemory)
        assert memory.play_bias == "neutral"
        assert memory.total_games == 0

    def test_load_stats_returns_default(self) -> None:
        pm = PersistenceManager(player_id=None)
        stats = pm.load_stats()
        assert isinstance(stats, PlayerStats)
        assert stats.total_games == 0

    def test_save_memory_noop(self) -> None:
        pm = PersistenceManager(player_id=None)
        memory = PlayerMemory()
        pm.save_memory(memory)  # should not raise

    def test_save_stats_noop(self) -> None:
        pm = PersistenceManager(player_id=None)
        stats = PlayerStats()
        pm.save_stats(stats)  # should not raise

    def test_update_memory_returns_current(self) -> None:
        pm = PersistenceManager(player_id=None)
        current = PlayerMemory()
        episode = EpisodeStats(player_id="", seat=0)
        result = pm.update_memory(current, episode, client=None)
        assert result is current

    def test_update_stats_returns_current(self) -> None:
        pm = PersistenceManager(player_id=None)
        current = PlayerStats()
        match = MatchStats()
        result = pm.update_stats(current, match, placement=1)
        assert result is current


# --- with player_id (file I/O via tmp_path) ---

class TestPersistenceManagerWithId:
    def test_save_and_load_memory(self, tmp_path) -> None:
        pm = PersistenceManager(player_id="test_player", players_dir=str(tmp_path))
        memory = PlayerMemory(play_bias="aggressive", total_games=5)
        pm.save_memory(memory)
        loaded = pm.load_memory()
        assert loaded.play_bias == "aggressive"
        assert loaded.total_games == 5

    def test_save_and_load_stats(self, tmp_path) -> None:
        pm = PersistenceManager(player_id="test_player", players_dir=str(tmp_path))
        stats = PlayerStats(total_games=10, wins=3, total_points=5000)
        pm.save_stats(stats)
        loaded = pm.load_stats()
        assert loaded.total_games == 10
        assert loaded.wins == 3
        assert loaded.total_points == 5000

    def test_load_memory_nonexistent(self, tmp_path) -> None:
        pm = PersistenceManager(player_id="nonexistent", players_dir=str(tmp_path))
        memory = pm.load_memory()
        assert isinstance(memory, PlayerMemory)
        assert memory.total_games == 0

    def test_load_stats_nonexistent(self, tmp_path) -> None:
        pm = PersistenceManager(player_id="nonexistent", players_dir=str(tmp_path))
        stats = pm.load_stats()
        assert isinstance(stats, PlayerStats)
        assert stats.total_games == 0

    def test_update_stats_with_id(self, tmp_path) -> None:
        pm = PersistenceManager(player_id="test_player", players_dir=str(tmp_path))
        current = PlayerStats()
        match = MatchStats(wins=1, deal_ins=0, riichi_count=1, riichi_wins=1, points=8000, hands=1)
        result = pm.update_stats(current, match, placement=1)
        assert result.total_games == 1
        assert result.wins == 1
        assert result.first_place_count == 1

    def test_update_memory_with_id_no_client(self, tmp_path) -> None:
        pm = PersistenceManager(player_id="test_player", players_dir=str(tmp_path))
        current = PlayerMemory()
        episode = EpisodeStats(player_id="test_player", seat=0, wins=1, total_points=5000)
        result = pm.update_memory(current, episode, client=None)
        assert result.total_games == 1
        # verify it was persisted
        loaded = pm.load_memory()
        assert loaded.total_games == 1
