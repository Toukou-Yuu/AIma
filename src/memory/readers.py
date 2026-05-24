"""Memory layer readers.

Read layer data from memory stores for prompt injection.
"""

from __future__ import annotations

from typing import Any

from memory.schema import MemoryLayer
from memory.stores import MemoryStore


def read_layer(
    store: MemoryStore,
    player_id: str,
    layer: MemoryLayer,
    opponent_id: str | None = None,
) -> dict[str, Any] | None:
    """Read memory data for a specific layer.

    Args:
        store: Memory store backend
        player_id: Player identifier
        layer: Memory layer to read
        opponent_id: Opponent ID (required for opponent layer)

    Returns:
        Memory data dict, or None if not found

    Raises:
        ValueError: If opponent_id is not provided for opponent layer
    """
    key = _build_key(player_id, layer, opponent_id)
    return store.read(key)


def read_all_layers(
    store: MemoryStore,
    player_id: str,
    layers: list[MemoryLayer],
    opponent_ids: list[str] | None = None,
) -> dict[MemoryLayer, dict[str, Any]]:
    """Read memory data for multiple layers.

    Args:
        store: Memory store backend
        player_id: Player identifier
        layers: Memory layers to read
        opponent_ids: Opponent IDs (required if opponent layer is included)

    Returns:
        Dict mapping layers to their memory data (empty dict if not found)

    Raises:
        ValueError: If opponent layer is requested without opponent_ids
    """
    result: dict[MemoryLayer, dict[str, Any]] = {}

    for layer in layers:
        if layer == MemoryLayer.OPPONENT:
            if not opponent_ids:
                raise ValueError("opponent_ids is required for opponent layer")
            result[layer] = _read_opponent_memories(store, player_id, opponent_ids)
        else:
            data = read_layer(store, player_id, layer)
            result[layer] = data if data is not None else {}

    return result


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


def _read_opponent_memories(
    store: MemoryStore,
    player_id: str,
    opponent_ids: list[str],
) -> dict[str, Any]:
    """Read memories for multiple opponents.

    Args:
        store: Memory store backend
        player_id: Player identifier
        opponent_ids: List of opponent IDs

    Returns:
        Dict mapping opponent IDs to their memory data
    """
    result: dict[str, Any] = {}
    for opponent_id in opponent_ids:
        data = read_layer(store, player_id, MemoryLayer.OPPONENT, opponent_id)
        if data is not None:
            result[opponent_id] = data
    return result


def format_memory_for_prompt(
    layer_data: dict[MemoryLayer, dict[str, Any]],
) -> str:
    """Format memory data for prompt injection.

    Args:
        layer_data: Memory data by layer

    Returns:
        Formatted string for prompt, or empty string if no data
    """
    if not any(layer_data.values()):
        return ""

    sections: list[str] = ["## Memory"]

    if MemoryLayer.HAND in layer_data and layer_data[MemoryLayer.HAND]:
        hand_data = layer_data[MemoryLayer.HAND]
        sections.append("### Current Hand")
        sections.append(_format_dict_lines(hand_data))

    if MemoryLayer.MATCH in layer_data and layer_data[MemoryLayer.MATCH]:
        match_data = layer_data[MemoryLayer.MATCH]
        sections.append("### Current Match")
        sections.append(_format_dict_lines(match_data))

    if MemoryLayer.PERSISTENT in layer_data and layer_data[MemoryLayer.PERSISTENT]:
        persistent_data = layer_data[MemoryLayer.PERSISTENT]
        sections.append("### Long-term Memory")
        sections.append(_format_dict_lines(persistent_data))

    if MemoryLayer.OPPONENT in layer_data and layer_data[MemoryLayer.OPPONENT]:
        opponent_data = layer_data[MemoryLayer.OPPONENT]
        sections.append("### Opponent Notes")
        sections.append(_format_opponent_lines(opponent_data))

    return "\n\n".join(sections)


def _format_dict_lines(data: dict[str, Any]) -> str:
    """Format a dict as key-value lines."""
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            formatted = ", ".join(str(v) for v in value)
            lines.append(f"- {key}: {formatted}")
        elif isinstance(value, dict):
            lines.append(f"- {key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  - {sub_key}: {sub_value}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _format_opponent_lines(data: dict[str, Any]) -> str:
    """Format opponent memories as lines."""
    lines: list[str] = []
    for opponent_id, memory in data.items():
        lines.append(f"- {opponent_id}:")
        if isinstance(memory, dict):
            for key, value in memory.items():
                lines.append(f"  - {key}: {value}")
        else:
            lines.append(f"  - {memory}")
    return "\n".join(lines)