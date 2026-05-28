"""Memory module tests: layers, injection, no_persist."""

from __future__ import annotations

from pathlib import Path

import pytest

from memory.manager import MemoryManager, create_memory_manager
from memory.readers import (
    format_memory_for_prompt,
    read_all_layers,
    read_layer,
)
from memory.schema import MemoryLayer, MemorySpec
from memory.stores import InMemoryStore, JsonFileStore, create_store
from memory.writers import (
    clear_hand_memory,
    clear_match_memory,
    delete_layer,
    update_opponent_memory,
    update_persistent_memory,
    write_layer,
)

# ===================================================================
# MemorySpec & MemoryLayer
# ===================================================================


def test_memory_spec_defaults() -> None:
    """MemorySpec 默认值为 mode=off, 空 layers, in_memory, persist=False."""
    spec = MemorySpec()
    assert spec.mode == "off"
    assert spec.layers == []
    assert spec.store == "in_memory"
    assert spec.persist is False


def test_memory_spec_passive_mode() -> None:
    """MemorySpec 支持 passive 模式."""
    spec = MemorySpec(mode="passive")
    assert spec.mode == "passive"


def test_memory_layer_enum() -> None:
    """MemoryLayer enum 包含四种 layer."""
    assert MemoryLayer.HAND.value == "hand"
    assert MemoryLayer.MATCH.value == "match"
    assert MemoryLayer.PERSISTENT.value == "persistent"
    assert MemoryLayer.OPPONENT.value == "opponent"


# ===================================================================
# InMemoryStore
# ===================================================================


def test_in_memory_store_roundtrip() -> None:
    """InMemoryStore 写入后读取一致."""
    store = InMemoryStore()
    store.write("player1/hand", {"action": "riichi"})
    data = store.read("player1/hand")
    assert data is not None
    assert data["action"] == "riichi"


def test_in_memory_store_read_nonexistent() -> None:
    """InMemoryStore 读取不存在的 key 返回 None."""
    store = InMemoryStore()
    data = store.read("nonexistent")
    assert data is None


def test_in_memory_store_delete() -> None:
    """InMemoryStore 删除后读取返回 None."""
    store = InMemoryStore()
    store.write("key", {"data": "value"})
    store.delete("key")
    assert store.read("key") is None


def test_in_memory_store_list_keys() -> None:
    """InMemoryStore list_keys 返回所有 key."""
    store = InMemoryStore()
    store.write("a", {})
    store.write("b", {})
    store.write("c", {})
    keys = store.list_keys()
    assert set(keys) == {"a", "b", "c"}


# ===================================================================
# JsonFileStore
# ===================================================================


def test_json_file_store_roundtrip(tmp_path: Path) -> None:
    """JsonFileStore 写入后读取一致."""
    store = JsonFileStore(tmp_path)
    store.write("player1/hand", {"action": "riichi"})

    # 验证文件存在
    expected_file = tmp_path / "player1" / "hand" / "memory.json"
    assert expected_file.exists()

    data = store.read("player1/hand")
    assert data is not None
    assert data["action"] == "riichi"


def test_json_file_store_read_nonexistent(tmp_path: Path) -> None:
    """JsonFileStore 读取不存在的 key 返回 None."""
    store = JsonFileStore(tmp_path)
    data = store.read("nonexistent")
    assert data is None


def test_json_file_store_delete(tmp_path: Path) -> None:
    """JsonFileStore 删除后文件不存在."""
    store = JsonFileStore(tmp_path)
    store.write("player1/hand", {"data": "value"})
    store.delete("player1/hand")
    assert store.read("player1/hand") is None


def test_json_file_store_list_keys(tmp_path: Path) -> None:
    """JsonFileStore list_keys 返回所有 key."""
    store = JsonFileStore(tmp_path)
    store.write("player1/hand", {})
    store.write("player1/match", {})
    store.write("player1/opponents/opp1", {})
    keys = store.list_keys()
    assert "player1/hand" in keys
    assert "player1/match" in keys


# ===================================================================
# SqliteStore stub
# ===================================================================


def test_sqlite_store_raises_not_implemented() -> None:
    """SqliteStore 初始化时抛出 NotImplementedError."""
    from memory.stores import SqliteStore

    with pytest.raises(NotImplementedError, match="not implemented"):
        SqliteStore("test.db")


def test_create_store_sqlite_raises_not_implemented() -> None:
    """create_store('sqlite') 抛出 NotImplementedError."""
    with pytest.raises(NotImplementedError, match="not implemented"):
        create_store("sqlite")


# ===================================================================
# create_store factory
# ===================================================================


def test_create_store_in_memory() -> None:
    """create_store('in_memory') 返回 InMemoryStore."""
    store = create_store("in_memory")
    assert isinstance(store, InMemoryStore)


def test_create_store_json_with_base_dir() -> None:
    """create_store('json', base_dir=...) 返回 JsonFileStore."""
    store = create_store("json", base_dir="/tmp/test_players")
    assert isinstance(store, JsonFileStore)


def test_create_store_unknown_raises() -> None:
    """create_store('unknown') 抛出 ValueError."""
    with pytest.raises(ValueError, match="Unknown store type"):
        create_store("unknown")


# ===================================================================
# Readers
# ===================================================================


def test_read_layer_hand() -> None:
    """read_layer 读取 hand layer."""
    store = InMemoryStore()
    store.write("player1/hand", {"tiles": "123m456p789s11z"})
    data = read_layer(store, "player1", MemoryLayer.HAND)
    assert data is not None
    assert data["tiles"] == "123m456p789s11z"


def test_read_layer_opponent() -> None:
    """read_layer 读取 opponent layer 需要 opponent_id."""
    store = InMemoryStore()
    store.write("player1/opponents/opp1", {"bias": "aggressive"})
    data = read_layer(store, "player1", MemoryLayer.OPPONENT, opponent_id="opp1")
    assert data is not None
    assert data["bias"] == "aggressive"


def test_read_layer_opponent_requires_id() -> None:
    """read_layer 对 opponent layer 无 opponent_id 抛出 ValueError."""
    store = InMemoryStore()
    with pytest.raises(ValueError, match="opponent_id is required"):
        read_layer(store, "player1", MemoryLayer.OPPONENT)


def test_read_all_layers() -> None:
    """read_all_layers 读取多个 layer."""
    store = InMemoryStore()
    store.write("player1/hand", {"tiles": "hand_data"})
    store.write("player1/match", {"score": 25000})
    store.write("player1/persistent", {"total_wins": 100})
    store.write("player1/opponents/opp1", {"bias": "defensive"})

    layer_data = read_all_layers(
        store,
        "player1",
        [MemoryLayer.HAND, MemoryLayer.MATCH, MemoryLayer.PERSISTENT],
    )

    assert layer_data[MemoryLayer.HAND]["tiles"] == "hand_data"
    assert layer_data[MemoryLayer.MATCH]["score"] == 25000
    assert layer_data[MemoryLayer.PERSISTENT]["total_wins"] == 100


def test_read_all_layers_with_opponents() -> None:
    """read_all_layers 包含 opponent layer."""
    store = InMemoryStore()
    store.write("player1/opponents/opp1", {"bias": "aggressive"})
    store.write("player1/opponents/opp2", {"bias": "defensive"})

    layer_data = read_all_layers(
        store,
        "player1",
        [MemoryLayer.OPPONENT],
        opponent_ids=["opp1", "opp2"],
    )

    assert "opp1" in layer_data[MemoryLayer.OPPONENT]
    assert "opp2" in layer_data[MemoryLayer.OPPONENT]


def test_read_all_layers_opponent_requires_ids() -> None:
    """read_all_layers 包含 opponent layer 时需要 opponent_ids."""
    store = InMemoryStore()
    with pytest.raises(ValueError, match="opponent_ids is required"):
        read_all_layers(store, "player1", [MemoryLayer.OPPONENT])


# ===================================================================
# Writers
# ===================================================================


def test_write_layer() -> None:
    """write_layer 写入数据包含 updated_at."""
    store = InMemoryStore()
    write_layer(store, "player1", MemoryLayer.HAND, {"tiles": "123m"})
    data = store.read("player1/hand")
    assert data is not None
    assert data["tiles"] == "123m"
    assert "updated_at" in data


def test_delete_layer() -> None:
    """delete_layer 删除数据."""
    store = InMemoryStore()
    store.write("player1/hand", {"tiles": "123m"})
    delete_layer(store, "player1", MemoryLayer.HAND)
    assert store.read("player1/hand") is None


def test_clear_hand_memory() -> None:
    """clear_hand_memory 清除 hand memory."""
    store = InMemoryStore()
    store.write("player1/hand", {"tiles": "123m"})
    clear_hand_memory(store, "player1")
    assert store.read("player1/hand") is None


def test_clear_match_memory() -> None:
    """clear_match_memory 清除 match memory."""
    store = InMemoryStore()
    store.write("player1/match", {"score": 25000})
    clear_match_memory(store, "player1")
    assert store.read("player1/match") is None


def test_update_persistent_memory() -> None:
    """update_persistent_memory 合并更新数据."""
    store = InMemoryStore()
    store.write("player1/persistent", {"total_wins": 10, "total_games": 20})
    updated = update_persistent_memory(store, "player1", {"total_wins": 11, "streak": 3})
    assert updated["total_wins"] == 11
    assert updated["total_games"] == 20
    assert updated["streak"] == 3


def test_update_opponent_memory() -> None:
    """update_opponent_memory 合并更新对手数据."""
    store = InMemoryStore()
    store.write("player1/opponents/opp1", {"riichi_count": 5})
    updated = update_opponent_memory(store, "player1", "opp1", {"riichi_count": 6, "deal_in": 2})
    assert updated["riichi_count"] == 6
    assert updated["deal_in"] == 2


# ===================================================================
# format_memory_for_prompt
# ===================================================================


def test_format_memory_empty() -> None:
    """format_memory_for_prompt 空数据返回空字符串."""
    result = format_memory_for_prompt({})
    assert result == ""


def test_format_memory_hand_layer() -> None:
    """format_memory_for_prompt 包含 hand section."""
    result = format_memory_for_prompt({
        MemoryLayer.HAND: {"tiles": "123m", "shanten": 1},
    })
    assert "## Memory" in result
    assert "### Current Hand" in result
    assert "tiles" in result
    assert "shanten" in result


def test_format_memory_match_layer() -> None:
    """format_memory_for_prompt 包含 match section."""
    result = format_memory_for_prompt({
        MemoryLayer.MATCH: {"score": 25000, "rounds": 4},
    })
    assert "### Current Match" in result
    assert "score" in result


def test_format_memory_persistent_layer() -> None:
    """format_memory_for_prompt 包含 long-term section."""
    result = format_memory_for_prompt({
        MemoryLayer.PERSISTENT: {"total_wins": 100, "bias": "aggressive"},
    })
    assert "### Long-term Memory" in result


def test_format_memory_opponent_layer() -> None:
    """format_memory_for_prompt 包含 opponent section."""
    result = format_memory_for_prompt({
        MemoryLayer.OPPONENT: {
            "opp1": {"bias": "aggressive"},
            "opp2": {"bias": "defensive"},
        },
    })
    assert "### Opponent Notes" in result
    assert "opp1" in result
    assert "opp2" in result


# ===================================================================
# MemoryManager
# ===================================================================


def test_memory_manager_disabled_when_off() -> None:
    """mode=off 时 MemoryManager.enabled=False."""
    spec = MemorySpec(mode="off")
    manager = MemoryManager(spec)
    assert manager.enabled is False


def test_memory_manager_passive_mode() -> None:
    """mode=passive 时 MemoryManager.passive_mode=True."""
    spec = MemorySpec(mode="passive", layers=["hand"])
    manager = MemoryManager(spec)
    assert manager.enabled is True
    assert manager.passive_mode is True


def test_memory_manager_no_layers_returns_empty_section() -> None:
    """layers 为空时 get_memory_section 返回空字符串."""
    spec = MemorySpec(mode="passive", layers=[])
    manager = MemoryManager(spec)
    result = manager.get_memory_section("player1")
    assert result == ""


def test_memory_manager_off_returns_empty_section() -> None:
    """mode=off 时 get_memory_section 返回空字符串."""
    spec = MemorySpec(mode="off", layers=["hand"])
    manager = MemoryManager(spec)
    result = manager.get_memory_section("player1")
    assert result == ""


def test_memory_manager_passive_includes_memory_section() -> None:
    """mode=passive 且有 layers 时 get_memory_section 返回内容."""
    spec = MemorySpec(mode="passive", layers=["hand", "match"])
    manager = MemoryManager(spec)
    # 先写入一些数据
    manager.update_hand_memory("player1", {"tiles": "123m"})
    result = manager.get_memory_section("player1")
    assert "## Memory" in result


def test_memory_manager_update_methods_no_error_when_disabled() -> None:
    """mode=off 时 update 方法不报错."""
    spec = MemorySpec(mode="off")
    manager = MemoryManager(spec)
    # 这些调用不应该报错
    manager.update_hand_memory("player1", {"tiles": "123m"})
    manager.update_match_memory("player1", {"score": 25000})
    manager.update_persistent_memory("player1", {"total_wins": 1})
    manager.update_opponent_memory("player1", "opp1", {"bias": "aggressive"})


def test_memory_manager_on_hand_end_clears_hand_memory() -> None:
    """on_hand_end 清除 hand memory."""
    spec = MemorySpec(mode="passive", layers=["hand"])
    manager = MemoryManager(spec)
    manager.update_hand_memory("player1", {"tiles": "123m"})
    manager.on_hand_end("player1")
    result = manager.get_memory_section("player1")
    assert result == ""


def test_memory_manager_on_match_end_clears_match_memory() -> None:
    """on_match_end 清除 match memory."""
    spec = MemorySpec(mode="passive", layers=["match", "persistent"])
    manager = MemoryManager(spec)
    manager.update_match_memory("player1", {"score": 25000})
    manager.on_match_end("player1", {"total_games": 1})
    # match memory 被清除，persistent memory 被更新
    store = manager.store
    assert store is not None
    assert store.read("player1/match") is None
    assert store.read("player1/persistent") is not None


# ===================================================================
# No persist (acceptance criteria)
# ===================================================================


def test_no_persist_uses_in_memory() -> None:
    """persist=False 时使用 InMemoryStore."""
    spec = MemorySpec(mode="passive", layers=["hand"], store="in_memory", persist=False)
    manager = MemoryManager(spec)
    assert isinstance(manager.store, InMemoryStore)


def test_persist_json_uses_json_store() -> None:
    """persist=True 且 store=json 时使用 JsonFileStore."""
    spec = MemorySpec(mode="passive", layers=["hand"], store="json", persist=True)
    manager = MemoryManager(spec, persist_dir="/tmp/test_players")
    assert isinstance(manager.store, JsonFileStore)


def test_no_persist_does_not_write_to_configs_players(tmp_path: Path) -> None:
    """persist=False 时不写入 configs/players 目录."""
    spec = MemorySpec(mode="passive", layers=["persistent"], store="in_memory", persist=False)
    manager = MemoryManager(spec, persist_dir=str(tmp_path))
    manager.update_persistent_memory("player1", {"total_wins": 1})

    # 确保没有写入文件系统
    memory_file = tmp_path / "player1" / "persistent" / "memory.json"
    assert not memory_file.exists()


def test_persist_json_writes_to_disk(tmp_path: Path) -> None:
    """persist=True 且 store=json 时写入磁盘."""
    spec = MemorySpec(mode="passive", layers=["persistent"], store="json", persist=True)
    manager = MemoryManager(spec, persist_dir=str(tmp_path))
    manager.update_persistent_memory("player1", {"total_wins": 1})

    # 验证文件被创建
    memory_file = tmp_path / "player1" / "persistent" / "memory.json"
    assert memory_file.exists()


def test_memory_manager_prompt_interface_returns_text_and_layers() -> None:
    """AgentPipeline 使用公开接口读取 prompt memory 和诊断层名。"""
    spec = MemorySpec(mode="passive", layers=["hand"])
    manager = MemoryManager(spec)
    player_id = manager.player_id_for_seat(2)
    manager.update_hand_memory(player_id, {"tiles": "123m"})

    text, layers = manager.get_memory_prompt(player_id)

    assert player_id == "seat2"
    assert layers == ("hand",)
    assert "123m" in text


# ===================================================================
# create_memory_manager factory
# ===================================================================


def test_create_memory_manager_off_returns_none() -> None:
    """create_memory_manager(mode='off') 返回 None."""
    spec = MemorySpec(mode="off")
    manager = create_memory_manager(spec)
    assert manager is None


def test_create_memory_manager_passive_returns_manager() -> None:
    """create_memory_manager(mode='passive') 返回 MemoryManager."""
    spec = MemorySpec(mode="passive", layers=["hand"])
    manager = create_memory_manager(spec)
    assert manager is not None
    assert isinstance(manager, MemoryManager)
