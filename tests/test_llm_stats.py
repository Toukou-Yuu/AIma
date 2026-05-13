"""stats.py 覆盖测试：PlayerStats 计算属性 / MatchStats / format_stats_for_prompt。"""

from __future__ import annotations

from pathlib import Path

from llm.agent.stats import (
    MatchStats,
    PlayerStats,
    StatsAggregator,
    format_stats_for_prompt,
    load_stats,
    save_stats,
)


# ===================================================================
# PlayerStats 计算属性
# ===================================================================


def test_riichi_success_rate_normal() -> None:
    """riichi_count>0 时返回正确比率。"""
    s = PlayerStats(riichi_count=10, riichi_wins=4)
    assert s.riichi_success_rate == 0.4


def test_riichi_success_rate_zero_count() -> None:
    """riichi_count=0 时返回 0.0。"""
    s = PlayerStats(riichi_count=0, riichi_wins=0)
    assert s.riichi_success_rate == 0.0


def test_riichi_deal_in_rate_normal() -> None:
    """riichi_count>0 时返回正确放铳率。"""
    s = PlayerStats(riichi_count=8, riichi_deal_ins=2)
    assert s.riichi_deal_in_rate == 0.25


def test_riichi_deal_in_rate_zero_count() -> None:
    """riichi_count=0 时返回 0.0。"""
    s = PlayerStats(riichi_count=0, riichi_deal_ins=0)
    assert s.riichi_deal_in_rate == 0.0


def test_avg_placement_normal() -> None:
    """有顺位记录时返回加权平均。"""
    s = PlayerStats(
        first_place_count=2,
        second_place_count=3,
        third_place_count=1,
        fourth_place_count=0,
    )
    # (2*1 + 3*2 + 1*3 + 0*4) / 6 = 11/6
    assert abs(s.avg_placement - 11 / 6) < 1e-9


def test_avg_placement_zero_games() -> None:
    """无顺位记录时返回 0.0。"""
    s = PlayerStats()
    assert s.avg_placement == 0.0


def test_avg_points_per_game_normal() -> None:
    """total_games>0 时返回场均得点。"""
    s = PlayerStats(total_games=4, total_points=12000)
    assert s.avg_points_per_game == 3000.0


def test_avg_points_per_game_zero_games() -> None:
    """total_games=0 时返回 0.0。"""
    s = PlayerStats(total_games=0, total_points=0)
    assert s.avg_points_per_game == 0.0


def test_win_rate() -> None:
    """和了率计算。"""
    s = PlayerStats(total_hands=20, wins=5)
    assert s.win_rate == 0.25


def test_win_rate_zero_hands() -> None:
    """total_hands=0 时返回 0.0。"""
    s = PlayerStats()
    assert s.win_rate == 0.0


def test_deal_in_rate() -> None:
    """放铳率计算。"""
    s = PlayerStats(total_hands=20, deal_ins=4)
    assert s.deal_in_rate == 0.2


def test_riichi_rate() -> None:
    """立直率计算。"""
    s = PlayerStats(total_hands=20, riichi_count=6)
    assert s.riichi_rate == 0.3


def test_default_last_updated() -> None:
    """未指定 last_updated 时自动填充。"""
    s = PlayerStats()
    assert s.last_updated


# ===================================================================
# PlayerStats JSON 往返
# ===================================================================


def test_player_stats_roundtrip(tmp_path: Path) -> None:
    """序列化→反序列化保持字段一致。"""
    s = PlayerStats(
        total_games=10, total_hands=80, wins=20, deal_ins=10,
        riichi_count=15, riichi_wins=6, riichi_deal_ins=3,
        total_points=50000,
        first_place_count=3, second_place_count=4,
        third_place_count=2, fourth_place_count=1,
        last_updated="2025-01-01",
    )
    p = tmp_path / "stats.json"
    s.to_json(p)
    loaded = PlayerStats.from_json(p)
    assert loaded.total_games == 10
    assert loaded.wins == 20
    assert loaded.first_place_count == 3
    assert loaded.last_updated == "2025-01-01"


# ===================================================================
# MatchStats.copy
# ===================================================================


def test_match_stats_copy_is_independent() -> None:
    """copy 返回独立副本。"""
    m = MatchStats(wins=2, deal_ins=1, riichi_count=3, points=5000, hands=4, placement=1)
    c = m.copy()
    assert c.wins == 2
    assert c.points == 5000
    # 修改副本不影响原件
    c.wins = 99
    assert m.wins == 2


def test_match_stats_copy_default() -> None:
    """默认 MatchStats 的 copy 也是默认值。"""
    m = MatchStats()
    c = m.copy()
    assert c.wins == 0
    assert c.placement == 0


# ===================================================================
# StatsAggregator.update
# ===================================================================


def test_stats_aggregator_update() -> None:
    """StatsAggregator 正确累加统计。"""
    agg = StatsAggregator()
    current = PlayerStats(total_games=5, wins=10, total_hands=40)
    match = MatchStats(wins=1, hands=8, placement=2, points=3000)
    result = agg.update(current, match)
    assert result.total_games == 6
    assert result.wins == 11
    assert result.total_hands == 48
    assert result.second_place_count == 1
    assert result.total_points == 3000


def test_stats_aggregator_placement_counts() -> None:
    """各顺位正确累加。"""
    agg = StatsAggregator()
    current = PlayerStats()
    for placement in [1, 2, 3, 4]:
        match = MatchStats(placement=placement)
        current = agg.update(current, match)
    assert current.first_place_count == 1
    assert current.second_place_count == 1
    assert current.third_place_count == 1
    assert current.fourth_place_count == 1


# ===================================================================
# format_stats_for_prompt
# ===================================================================


def test_format_stats_empty() -> None:
    """total_games=0 时返回空字符串。"""
    assert format_stats_for_prompt(PlayerStats()) == ""


def test_format_stats_normal() -> None:
    """有统计时输出格式化文本。"""
    s = PlayerStats(
        total_games=10, total_hands=80, wins=20,
        deal_ins=8, riichi_count=12, riichi_wins=5,
        first_place_count=3, second_place_count=4,
        third_place_count=2, fourth_place_count=1,
    )
    text = format_stats_for_prompt(s)
    assert "累计对局: 10场" in text
    assert "和了率: 25.0%" in text
    assert "放铳率: 10.0%" in text
    assert "立直率: 15.0%" in text
    assert "立直成功率: 41.7%" in text
    assert "平均顺位" in text


def test_format_stats_no_riichi_count_omits_success_rate() -> None:
    """riichi_count=0 时不显示立直成功率。"""
    s = PlayerStats(total_games=5, total_hands=40, riichi_count=0)
    text = format_stats_for_prompt(s)
    assert "立直成功率" not in text


# ===================================================================
# load_stats / save_stats
# ===================================================================


def test_load_stats_nonexistent_returns_default() -> None:
    """路径不存在时返回默认统计。"""
    s = load_stats("no_such_player", players_dir="/tmp/nonexistent_aima_dir")
    assert s.total_games == 0


def test_save_then_load_stats(tmp_path: Path) -> None:
    """save_stats 后 load_stats 可恢复。"""
    s = PlayerStats(total_games=3, wins=1, last_updated="t")
    save_stats("test_player", s, players_dir=tmp_path)
    loaded = load_stats("test_player", players_dir=tmp_path)
    assert loaded.total_games == 3
    assert loaded.wins == 1
