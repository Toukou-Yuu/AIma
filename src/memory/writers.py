"""Memory layer writers.

Write layer data to memory stores.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from memory.schema import MemoryLayer
from memory.stores import MemoryStore


def write_layer(
    store: MemoryStore,
    player_id: str,
    layer: MemoryLayer,
    data: dict[str, Any],
    opponent_id: str | None = None,
) -> None:
    """Write memory data for a specific layer.

    Args:
        store: Memory store backend
        player_id: Player identifier
        layer: Memory layer to write
        data: Memory data to store
        opponent_id: Opponent ID (required for opponent layer)

    Raises:
        ValueError: If opponent_id is not provided for opponent layer
    """
    key = _build_key(player_id, layer, opponent_id)
    data["updated_at"] = datetime.now().isoformat()
    store.write(key, data)


def delete_layer(
    store: MemoryStore,
    player_id: str,
    layer: MemoryLayer,
    opponent_id: str | None = None,
) -> None:
    """Delete memory data for a specific layer.

    Args:
        store: Memory store backend
        player_id: Player identifier
        layer: Memory layer to delete
        opponent_id: Opponent ID (required for opponent layer)
    """
    key = _build_key(player_id, layer, opponent_id)
    store.delete(key)


def clear_hand_memory(store: MemoryStore, player_id: str) -> None:
    """Clear hand memory after a hand completes.

    Args:
        store: Memory store backend
        player_id: Player identifier
    """
    delete_layer(store, player_id, MemoryLayer.HAND)


def clear_match_memory(store: MemoryStore, player_id: str) -> None:
    """Clear match memory after a match completes.

    Args:
        store: Memory store backend
        player_id: Player identifier
    """
    delete_layer(store, player_id, MemoryLayer.MATCH)


def update_persistent_memory(
    store: MemoryStore,
    player_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update persistent memory with new data.

    Reads existing memory, merges updates, and writes back.

    Args:
        store: Memory store backend
        player_id: Player identifier
        updates: Data to merge into existing memory

    Returns:
        Updated memory data
    """
    from memory.readers import read_layer

    existing = read_layer(store, player_id, MemoryLayer.PERSISTENT)
    data = existing if existing is not None else {}
    data.update(updates)
    write_layer(store, player_id, MemoryLayer.PERSISTENT, data)
    return data


def update_opponent_memory(
    store: MemoryStore,
    player_id: str,
    opponent_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update opponent-specific memory with new data.

    Args:
        store: Memory store backend
        player_id: Player identifier
        opponent_id: Opponent identifier
        updates: Data to merge into existing memory

    Returns:
        Updated memory data
    """
    from memory.readers import read_layer

    existing = read_layer(store, player_id, MemoryLayer.OPPONENT, opponent_id)
    data = existing if existing is not None else {}
    data.update(updates)
    write_layer(store, player_id, MemoryLayer.OPPONENT, data, opponent_id)
    return data


def _build_key(
    player_id: str,
    layer: MemoryLayer,
    opponent_id: str | None = None,
) -> str:
    """Build storage key for a layer.

    Args:
        player_id: Player identifier
        layer: Memory layer
        opponent_id: Opponent ID (for opponent layer)

    Returns:
        Storage key string
    """
    if layer == MemoryLayer.OPPONENT:
        if not opponent_id:
            raise ValueError("opponent_id is required for opponent layer")
        return f"{player_id}/opponents/{opponent_id}"
    return f"{player_id}/{layer.value}"