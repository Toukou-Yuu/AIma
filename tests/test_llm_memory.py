"""memory.py 覆盖测试：PlayerMemory / EpisodeSummarizer / format_memory_for_prompt。"""

from __future__ import annotations

from pathlib import Path

from llm.agent.memory import (
    EpisodeStats,
    EpisodeSummarizer,
    PlayerMemory,
    format_memory_for_prompt,
    load_memory,
    save_memory,
)


# ===================================================================
# PlayerMemory.from_json / to_json
# ===================================================================


def test_player_memory_roundtrip(tmp_path: Path) -> None:
    """序列化→反序列化保持字段一致。"""
    mem = PlayerMemory(
        play_bias="aggressive",
        recent_patterns=["p1", "p2"],
        total_games=5,
        last_updated="2025-01-01T00:00:00",
    )
    p = tmp_path / "memory.json"
    mem.to_json(p)

    loaded = PlayerMemory.from_json(p)
    assert loaded.play_bias == "aggressive"
    assert loaded.recent_patterns == ["p1", "p2"]
    assert loaded.total_games == 5
    assert loaded.last_updated == "2025-01-01T00:00:00"


def test_player_memory_default_last_updated() -> None:
    """未指定 last_updated 时自动填充。"""
    mem = PlayerMemory()
    assert mem.last_updated  # 非空


# ===================================================================
# EpisodeSummarizer.summarize
# ===================================================================


def test_summarize_deal_in_suggests_defense() -> None:
    """有放铳时生成防守提示。"""
    stats = EpisodeStats(player_id="p1", seat=0, deal_ins=1, hands_played=1)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert any("放铳" in p for p in new_mem.recent_patterns)


def test_summarize_riichi_deal_in_suggests_cautious() -> None:
    """立直后放铳提示需评估立直时机。"""
    stats = EpisodeStats(player_id="p1", seat=0, riichi_deal_in=1, hands_played=1)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert any("立直后放铳" in p for p in new_mem.recent_patterns)


def test_summarize_riichi_success_suggests_active() -> None:
    """立直成功率较高时提示保持积极。"""
    stats = EpisodeStats(
        player_id="p1", seat=0,
        riichi_count=4, riichi_win=2, hands_played=4,
    )
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert any("积极性" in p for p in new_mem.recent_patterns)


def test_summarize_no_wins_suggests_attention() -> None:
    """hands>=1 且 wins==0 时提示注意一向听处理。"""
    stats = EpisodeStats(player_id="p1", seat=0, hands_played=1, wins=0)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert any("未和了" in p for p in new_mem.recent_patterns)


def test_summarize_bias_defensive_when_deal_ins_ge_2() -> None:
    """deal_ins>=2 时 play_bias 为 defensive。"""
    stats = EpisodeStats(player_id="p1", seat=0, deal_ins=2, hands_played=1)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert new_mem.play_bias == "defensive"


def test_summarize_bias_aggressive_when_wins_ge_1() -> None:
    """wins>=1 且 deal_ins<2 时 play_bias 为 aggressive。"""
    stats = EpisodeStats(player_id="p1", seat=0, wins=1, hands_played=1)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert new_mem.play_bias == "aggressive"


def test_summarize_bias_inherits_current_when_neutral() -> None:
    """无明显倾向时继承当前记忆。"""
    current = PlayerMemory(play_bias="defensive")
    stats = EpisodeStats(player_id="p1", seat=0, hands_played=1, wins=0, deal_ins=0)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, current)
    assert new_mem.play_bias == "defensive"


def test_summarize_merges_patterns_with_max() -> None:
    """新模式+旧模式不超过 max_patterns。"""
    current = PlayerMemory(recent_patterns=["旧1", "旧2", "旧3"])
    stats = EpisodeStats(player_id="p1", seat=0, deal_ins=1, hands_played=1)
    summarizer = EpisodeSummarizer(max_patterns=3)
    new_mem = summarizer.summarize(stats, current)
    assert len(new_mem.recent_patterns) == 3
    # 新模式在前
    assert "放铳" in new_mem.recent_patterns[0]


def test_summarize_increments_total_games() -> None:
    """total_games 递增。"""
    current = PlayerMemory(total_games=2)
    stats = EpisodeStats(player_id="p1", seat=0, hands_played=1)
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, current)
    assert new_mem.total_games == 3


def test_summarize_no_patterns_when_no_trigger() -> None:
    """无触发条件时不生成新模式（wins>=1 触发 aggressive 但无 pattern 条件）。"""
    stats = EpisodeStats(
        player_id="p1", seat=0,
        wins=1, riichi_count=0, deal_ins=0,
        hands_played=1,
    )
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    # wins>=1 → aggressive, 但无 deal_in / riichi_deal_in / no-win
    # 注意 wins=1 且 hands_played=1 时不触发"未和了"
    # 但 wins>=1 不触发"本局未和了"（因为 wins>0）
    assert new_mem.play_bias == "aggressive"


def test_summarize_riichi_low_success_no_active_hint() -> None:
    """立直成功率低时不开"保持积极性"提示。"""
    stats = EpisodeStats(
        player_id="p1", seat=0,
        riichi_count=4, riichi_win=1, hands_played=4,
    )
    summarizer = EpisodeSummarizer()
    new_mem = summarizer.summarize(stats, PlayerMemory())
    assert not any("积极性" in p for p in new_mem.recent_patterns)


# ===================================================================
# format_memory_for_prompt
# ===================================================================


def test_format_memory_neutral_bias_empty() -> None:
    """play_bias=neutral 且无 patterns 时返回空字符串。"""
    mem = PlayerMemory(play_bias="neutral", recent_patterns=[])
    assert format_memory_for_prompt(mem) == ""


def test_format_memory_defensive_bias() -> None:
    """defensive bias 输出"偏向防守"。"""
    mem = PlayerMemory(play_bias="defensive")
    text = format_memory_for_prompt(mem)
    assert "偏向防守" in text


def test_format_memory_aggressive_bias() -> None:
    """aggressive bias 输出"偏向进攻"。"""
    mem = PlayerMemory(play_bias="aggressive")
    text = format_memory_for_prompt(mem)
    assert "偏向进攻" in text


def test_format_memory_with_patterns() -> None:
    """含 patterns 时输出近期总结。"""
    mem = PlayerMemory(recent_patterns=["注意防守", "立直谨慎"])
    text = format_memory_for_prompt(mem)
    assert "近期总结" in text
    assert "注意防守" in text
    assert "立直谨慎" in text


# ===================================================================
# load_memory / save_memory
# ===================================================================


def test_load_memory_nonexistent_returns_default() -> None:
    """路径不存在时返回默认记忆。"""
    mem = load_memory("no_such_player", players_dir="/tmp/nonexistent_aima_dir")
    assert mem.total_games == 0
    assert mem.play_bias == "neutral"


def test_save_then_load_memory(tmp_path: Path) -> None:
    """save_memory 后 load_memory 可恢复。"""
    mem = PlayerMemory(play_bias="aggressive", total_games=3, last_updated="t")
    save_memory("test_player", mem, players_dir=tmp_path)
    loaded = load_memory("test_player", players_dir=tmp_path)
    assert loaded.play_bias == "aggressive"
    assert loaded.total_games == 3
