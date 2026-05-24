"""Memory lifecycle management.

Manages memory lifecycle events: hand end, match end, etc.
"""

from __future__ import annotations

from typing import Any

from memory.schema import MemoryLayer, MemorySpec
from memory.stores import MemoryStore, create_store
from memory.writers import clear_hand_memory, clear_match_memory


class MemoryLifecycle:
    """Memory lifecycle manager.

    Handles memory creation, updates, and cleanup based on game events.
    """

    def __init__(
        self,
        spec: MemorySpec,
        store: MemoryStore | None = None,
        persist_dir: str = "configs/players",
    ) -> None:
        """Initialize lifecycle manager.

        Args:
            spec: Memory configuration
            store: Memory store (created based on spec if not provided)
            persist_dir: Directory for persistent storage
        """
        self._spec = spec
        self._persist = spec.persist

        if store is not None:
            self._store = store
        elif self._persist and spec.store == "json":
            self._store = create_store("json", base_dir=persist_dir)
        else:
            self._store = create_store("in_memory")

    @property
    def store(self) -> MemoryStore:
        """Get the underlying memory store."""
        return self._store

    @property
    def enabled(self) -> bool:
        """Check if memory is enabled (mode != 'off')."""
        return self._spec.mode != "off"

    @property
    def passive_mode(self) -> bool:
        """Check if memory is in passive mode."""
        return self._spec.mode == "passive"

    def on_hand_end(
        self,
        player_id: str,
        hand_summary: dict[str, Any] | None = None,
    ) -> None:
        """Handle end of a hand.

        - Updates hand memory with summary (if provided)
        - Clears hand memory for next hand

        Args:
            player_id: Player identifier
            hand_summary: Optional hand summary data
        """
        if not self.enabled:
            return

        if MemoryLayer.HAND in self._layers and hand_summary:
            from memory.writers import write_layer

            write_layer(self._store, player_id, MemoryLayer.HAND, hand_summary)

        clear_hand_memory(self._store, player_id)

    def on_match_end(
        self,
        player_id: str,
        match_summary: dict[str, Any] | None = None,
    ) -> None:
        """Handle end of a match.

        - Updates persistent memory with match summary
        - Clears match memory for next match

        Args:
            player_id: Player identifier
            match_summary: Optional match summary data
        """
        if not self.enabled:
            return

        if MemoryLayer.MATCH in self._layers and match_summary:
            from memory.writers import write_layer

            write_layer(self._store, player_id, MemoryLayer.MATCH, match_summary)

        clear_match_memory(self._store, player_id)

        if MemoryLayer.PERSISTENT in self._layers and match_summary:
            from memory.writers import update_persistent_memory

            update_persistent_memory(self._store, player_id, match_summary)

    def should_persist(self) -> bool:
        """Check if memory should be persisted.

        Returns:
            True if memory should be persisted to disk
        """
        return self._persist and self._spec.store == "json"

    @property
    def _layers(self) -> list[MemoryLayer]:
        """Get enabled memory layers."""
        return [MemoryLayer(layer) for layer in self._spec.layers]


def create_memory_lifecycle(
    spec: MemorySpec,
    persist_dir: str = "configs/players",
) -> MemoryLifecycle | None:
    """Create a memory lifecycle manager based on spec.

    Args:
        spec: Memory configuration
        persist_dir: Directory for persistent storage

    Returns:
        MemoryLifecycle instance, or None if memory is disabled
    """
    if spec.mode == "off":
        return None
    return MemoryLifecycle(spec, persist_dir=persist_dir)