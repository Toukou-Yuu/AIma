"""Memory prompt injection contract tests."""

from __future__ import annotations

from memory.manager import MemoryManager
from memory.schema import MemoryLayer, MemorySpec
from memory.stores import InMemoryStore


class TestMemoryPromptInjectionContract:
    """Tests for memory prompt injection contract."""

    def test_memory_off_no_injection(self) -> None:
        """memory.mode = 'off' should not inject memory section into prompt."""
        spec = MemorySpec(mode="off", layers=[], store="in_memory")
        manager = MemoryManager(spec)

        player_id = MemoryManager.player_id_for_seat(0)
        memory_section, layers = manager.get_memory_prompt(player_id)

        assert memory_section == ""
        assert layers == ()

    def test_memory_passive_injection(self) -> None:
        """memory.mode = 'passive' should inject memory section into prompt."""
        spec = MemorySpec(
            mode="passive",
            layers=["hand", "match", "persistent"],
            store="in_memory",
        )
        store = InMemoryStore()
        from memory.lifecycle import MemoryLifecycle

        lifecycle = MemoryLifecycle(spec, store=store)
        manager = MemoryManager(spec, lifecycle=lifecycle)

        # Write some data to each layer
        from memory.writers import write_layer

        write_layer(store, "seat0", MemoryLayer.HAND, {"current_strategy": "attack"})
        write_layer(store, "seat0", MemoryLayer.MATCH, {"hands_played": 3})
        write_layer(store, "seat0", MemoryLayer.PERSISTENT, {"player_style": "aggressive"})

        player_id = MemoryManager.player_id_for_seat(0)
        memory_section, layers = manager.get_memory_prompt(player_id)

        assert "## Memory" in memory_section
        assert "hand" in layers
        assert "match" in layers
        assert "persistent" in layers

    def test_memory_section_format(self) -> None:
        """Memory section should be formatted correctly for LLM prompts."""
        spec = MemorySpec(
            mode="passive",
            layers=["match"],
            store="in_memory",
        )
        store = InMemoryStore()
        from memory.lifecycle import MemoryLifecycle

        lifecycle = MemoryLifecycle(spec, store=store)
        manager = MemoryManager(spec, lifecycle=lifecycle)

        # Write match data
        from memory.writers import write_layer

        write_layer(
            store,
            "seat0",
            MemoryLayer.MATCH,
            {"hands_played": 2, "wins": 1, "points_delta": 5000},
        )

        player_id = MemoryManager.player_id_for_seat(0)
        memory_section, _ = manager.get_memory_prompt(player_id)

        # Check format
        assert memory_section.startswith("## Memory")
        assert "### Current Match" in memory_section
        assert "hands_played" in memory_section.lower() or "Hands Played" in memory_section

    def test_memory_layers_in_diagnostics(self) -> None:
        """Decision diagnostics should record memory layers."""
        spec = MemorySpec(
            mode="passive",
            layers=["hand", "match"],
            store="in_memory",
        )
        store = InMemoryStore()
        from memory.lifecycle import MemoryLifecycle

        lifecycle = MemoryLifecycle(spec, store=store)
        manager = MemoryManager(spec, lifecycle=lifecycle)

        player_id = MemoryManager.player_id_for_seat(0)
        layers = manager.get_enabled_layer_names()

        assert len(layers) > 0
        assert "hand" in layers
        assert "match" in layers

    def test_empty_memory_returns_empty_section(self) -> None:
        """Empty memory store should return empty section."""
        spec = MemorySpec(
            mode="passive",
            layers=["hand", "match"],
            store="in_memory",
        )
        store = InMemoryStore()
        from memory.lifecycle import MemoryLifecycle

        lifecycle = MemoryLifecycle(spec, store=store)
        manager = MemoryManager(spec, lifecycle=lifecycle)

        player_id = MemoryManager.player_id_for_seat(0)
        memory_section, _ = manager.get_memory_prompt(player_id)

        # Empty store should return empty section
        assert memory_section == ""

    def test_opponent_memory_not_required(self) -> None:
        """Opponent memory layer should not be required for basic passive mode."""
        spec = MemorySpec(
            mode="passive",
            layers=["hand", "match"],
            store="in_memory",
        )
        store = InMemoryStore()
        from memory.lifecycle import MemoryLifecycle

        lifecycle = MemoryLifecycle(spec, store=store)
        manager = MemoryManager(spec, lifecycle=lifecycle)

        # Should work without opponent_ids
        player_id = MemoryManager.player_id_for_seat(0)
        memory_section, layers = manager.get_memory_prompt(player_id)

        assert memory_section == ""  # No data written
        assert "opponent" not in layers