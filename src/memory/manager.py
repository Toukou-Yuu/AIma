"""Memory manager - main entry point for memory operations.

Usage:
    from memory.manager import MemoryManager

    manager = MemoryManager(spec)
    memory_section = manager.get_memory_section(player_id)
"""

from __future__ import annotations

from typing import Any

from memory.lifecycle import MemoryLifecycle, create_memory_lifecycle
from memory.readers import format_memory_for_prompt, read_all_layers
from memory.schema import MemoryLayer, MemorySpec
from memory.stores import MemoryStore


class MemoryManager:
    """Memory manager for player memory operations.

    Provides a unified interface for reading, writing, and formatting
    memory data for LLM prompts.
    """

    def __init__(
        self,
        spec: MemorySpec,
        lifecycle: MemoryLifecycle | None = None,
        persist_dir: str = "configs/players",
    ) -> None:
        """Initialize memory manager.

        Args:
            spec: Memory configuration
            lifecycle: Memory lifecycle manager (created from spec if not provided)
            persist_dir: Directory for persistent storage
        """
        self._spec = spec
        self._lifecycle = lifecycle or create_memory_lifecycle(spec, persist_dir)

    @property
    def enabled(self) -> bool:
        """Check if memory is enabled."""
        return self._lifecycle is not None and self._lifecycle.enabled

    @property
    def passive_mode(self) -> bool:
        """Check if memory is in passive mode."""
        return self._lifecycle is not None and self._lifecycle.passive_mode

    @property
    def store(self) -> MemoryStore | None:
        """Get the underlying memory store, or None if disabled."""
        return self._lifecycle.store if self._lifecycle else None

    def get_memory_section(
        self,
        player_id: str,
        opponent_ids: list[str] | None = None,
    ) -> str:
        """Get formatted memory section for prompt injection.

        Args:
            player_id: Player identifier
            opponent_ids: List of opponent IDs (for opponent memory)

        Returns:
            Formatted memory section string, or empty string if disabled/no data
        """
        if not self.enabled or self._lifecycle is None:
            return ""

        layers = self._get_enabled_layers()
        if not layers:
            return ""

        layer_data = read_all_layers(
            self._lifecycle.store,
            player_id,
            layers,
            opponent_ids,
        )

        return format_memory_for_prompt(layer_data)

    def update_hand_memory(
        self,
        player_id: str,
        data: dict[str, Any],
    ) -> None:
        """Update hand memory for a player.

        Args:
            player_id: Player identifier
            data: Memory data to store
        """
        if not self.enabled or self._lifecycle is None:
            return
        if MemoryLayer.HAND not in self._get_enabled_layers():
            return

        from memory.writers import write_layer

        write_layer(self._lifecycle.store, player_id, MemoryLayer.HAND, data)

    def update_match_memory(
        self,
        player_id: str,
        data: dict[str, Any],
    ) -> None:
        """Update match memory for a player.

        Args:
            player_id: Player identifier
            data: Memory data to store
        """
        if not self.enabled or self._lifecycle is None:
            return
        if MemoryLayer.MATCH not in self._get_enabled_layers():
            return

        from memory.writers import write_layer

        write_layer(self._lifecycle.store, player_id, MemoryLayer.MATCH, data)

    def update_persistent_memory(
        self,
        player_id: str,
        data: dict[str, Any],
    ) -> None:
        """Update persistent memory for a player.

        Args:
            player_id: Player identifier
            data: Memory data to merge
        """
        if not self.enabled or self._lifecycle is None:
            return
        if MemoryLayer.PERSISTENT not in self._get_enabled_layers():
            return

        from memory.writers import update_persistent_memory

        update_persistent_memory(self._lifecycle.store, player_id, data)

    def update_opponent_memory(
        self,
        player_id: str,
        opponent_id: str,
        data: dict[str, Any],
    ) -> None:
        """Update opponent-specific memory for a player.

        Args:
            player_id: Player identifier
            opponent_id: Opponent identifier
            data: Memory data to merge
        """
        if not self.enabled or self._lifecycle is None:
            return
        if MemoryLayer.OPPONENT not in self._get_enabled_layers():
            return

        from memory.writers import update_opponent_memory

        update_opponent_memory(self._lifecycle.store, player_id, opponent_id, data)

    def on_hand_end(
        self,
        player_id: str,
        hand_summary: dict[str, Any] | None = None,
    ) -> None:
        """Handle end of a hand.

        Args:
            player_id: Player identifier
            hand_summary: Optional hand summary data
        """
        if self._lifecycle:
            self._lifecycle.on_hand_end(player_id, hand_summary)

    def on_match_end(
        self,
        player_id: str,
        match_summary: dict[str, Any] | None = None,
    ) -> None:
        """Handle end of a match.

        Args:
            player_id: Player identifier
            match_summary: Optional match summary data
        """
        if self._lifecycle:
            self._lifecycle.on_match_end(player_id, match_summary)

    def should_persist(self) -> bool:
        """Check if memory should be persisted to disk."""
        return self._lifecycle.should_persist() if self._lifecycle else False

    def _get_enabled_layers(self) -> list[MemoryLayer]:
        """Get enabled memory layers from spec."""
        return [MemoryLayer(layer) for layer in self._spec.layers]


def create_memory_manager(
    spec: MemorySpec,
    persist_dir: str = "configs/players",
) -> MemoryManager | None:
    """Create a memory manager based on spec.

    Args:
        spec: Memory configuration
        persist_dir: Directory for persistent storage

    Returns:
        MemoryManager instance, or None if memory is disabled
    """
    if spec.mode == "off":
        return None
    return MemoryManager(spec, persist_dir=persist_dir)