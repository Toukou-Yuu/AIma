"""profile.py 覆盖测试：PlayerProfile / load_profile / list_players。"""

from __future__ import annotations

from pathlib import Path

from llm.agent.profile import (
    PlayerProfile,
    list_players,
    load_profile,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _profile_data() -> dict:
    return {
        "id": "test_bot",
        "name": "测试牌手",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "temperature": 0.7,
        "max_tokens": 1024,
        "timeout_sec": 120.0,
        "persona_prompt": "我是一个测试牌手",
        "strategy_prompt": "优先防守",
    }


def _write_profile(path: Path, data: dict | None = None) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data or _profile_data(), ensure_ascii=False), encoding="utf-8")


# ===================================================================
# PlayerProfile.from_json / to_json
# ===================================================================


def test_profile_roundtrip(tmp_path: Path) -> None:
    """序列化→反序列化保持字段一致。"""
    prof = PlayerProfile(**_profile_data())
    p = tmp_path / "profile.json"
    prof.to_json(p)

    loaded = PlayerProfile.from_json(p)
    assert loaded.id == "test_bot"
    assert loaded.name == "测试牌手"
    assert loaded.model == "gpt-4o-mini"
    assert loaded.provider == "openai"
    assert loaded.temperature == 0.7
    assert loaded.max_tokens == 1024
    assert loaded.timeout_sec == 120.0
    assert loaded.persona_prompt == "我是一个测试牌手"
    assert loaded.strategy_prompt == "优先防守"


def test_profile_frozen() -> None:
    """PlayerProfile 是 frozen dataclass。"""
    prof = PlayerProfile(**_profile_data())
    try:
        prof.id = "changed"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("frozen dataclass 不允许修改属性")


def test_profile_to_json_content(tmp_path: Path) -> None:
    """to_json 写入的 JSON 包含所有字段。"""
    import json
    prof = PlayerProfile(**_profile_data())
    p = tmp_path / "profile.json"
    prof.to_json(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["id"] == "test_bot"
    assert data["provider"] == "openai"
    assert "persona_prompt" in data
    assert "strategy_prompt" in data


# ===================================================================
# load_profile
# ===================================================================


def test_load_profile_nonexistent_returns_none() -> None:
    """路径不存在时返回 None。"""
    result = load_profile("no_such_player", players_dir="/tmp/nonexistent_aima_dir")
    assert result is None


def test_load_profile_existing(tmp_path: Path) -> None:
    """路径存在时返回 PlayerProfile。"""
    player_dir = tmp_path / "existing_player"
    _write_profile(player_dir / "profile.json")
    result = load_profile("existing_player", players_dir=tmp_path)
    assert result is not None
    assert result.id == "test_bot"
    assert result.name == "测试牌手"


# ===================================================================
# list_players
# ===================================================================


def test_list_players_nonexistent_dir() -> None:
    """目录不存在时返回空列表。"""
    result = list_players(players_dir="/tmp/nonexistent_aima_dir")
    assert result == []


def test_list_players_empty_dir(tmp_path: Path) -> None:
    """空目录返回空列表。"""
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    result = list_players(players_dir=players_dir)
    assert result == []


def test_list_players_with_profiles(tmp_path: Path) -> None:
    """含 profile.json 的子目录被列出。"""
    _write_profile(tmp_path / "player_a" / "profile.json")
    _write_profile(tmp_path / "player_b" / "profile.json")
    result = list_players(players_dir=tmp_path)
    assert sorted(result) == ["player_a", "player_b"]


def test_list_players_skips_default(tmp_path: Path) -> None:
    """default 目录被跳过。"""
    _write_profile(tmp_path / "default" / "profile.json")
    _write_profile(tmp_path / "player_a" / "profile.json")
    result = list_players(players_dir=tmp_path)
    assert result == ["player_a"]


def test_list_players_skips_dirs_without_profile(tmp_path: Path) -> None:
    """没有 profile.json 的子目录被跳过。"""
    (tmp_path / "no_profile_dir").mkdir()
    _write_profile(tmp_path / "has_profile" / "profile.json")
    result = list_players(players_dir=tmp_path)
    assert result == ["has_profile"]


def test_list_players_skips_files(tmp_path: Path) -> None:
    """同级文件（非目录）被跳过。"""
    (tmp_path / "a_file.txt").write_text("not a dir", encoding="utf-8")
    _write_profile(tmp_path / "real_player" / "profile.json")
    result = list_players(players_dir=tmp_path)
    assert result == ["real_player"]
