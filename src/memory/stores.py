"""Memory store implementations.

Store types: "in_memory" | "json" | "sqlite"
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class MemoryStore(ABC):
    """Abstract base class for memory storage backends."""

    @abstractmethod
    def read(self, key: str) -> dict[str, Any] | None:
        """Read memory data for a given key.

        Args:
            key: Unique identifier for the memory entry

        Returns:
            Memory data dict, or None if not found
        """
        ...

    @abstractmethod
    def write(self, key: str, data: dict[str, Any]) -> None:
        """Write memory data for a given key.

        Args:
            key: Unique identifier for the memory entry
            data: Memory data to store
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete memory data for a given key.

        Args:
            key: Unique identifier for the memory entry
        """
        ...

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all keys in the store.

        Returns:
            List of all keys
        """
        ...


class InMemoryStore(MemoryStore):
    """In-memory store for testing and ephemeral memory.

    Store type: "in_memory"
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def read(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def write(self, key: str, data: dict[str, Any]) -> None:
        self._data[key] = data

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def list_keys(self) -> list[str]:
        return list(self._data.keys())


class JsonFileStore(MemoryStore):
    """JSON file-based store for persistent memory.

    Store type: "json"
    """

    def __init__(self, base_dir: Path | str = "configs/players") -> None:
        self._base_dir = Path(base_dir)

    def _get_file_path(self, key: str) -> Path:
        """Get the file path for a given key.

        Key format: "{player_id}/{layer}" or "{player_id}/opponents/{opponent_id}"
        """
        return self._base_dir / key / "memory.json"

    def read(self, key: str) -> dict[str, Any] | None:
        file_path = self._get_file_path(key)
        if not file_path.exists():
            return None
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def write(self, key: str, data: dict[str, Any]) -> None:
        file_path = self._get_file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete(self, key: str) -> None:
        file_path = self._get_file_path(key)
        if file_path.exists():
            file_path.unlink()

    def list_keys(self) -> list[str]:
        """List all keys based on directory structure.

        Keys are derived from directories containing memory.json files.
        """
        keys: list[str] = []
        if not self._base_dir.exists():
            return keys

        for memory_file in self._base_dir.rglob("memory.json"):
            relative = memory_file.parent.relative_to(self._base_dir)
            keys.append(str(relative).replace("/", "/"))

        return keys


class SqliteStore(MemoryStore):
    """SQLite-based store for persistent memory.

    Store type: "sqlite"

    Note: This is a stub implementation for v4.0.
    SQLite store is not yet implemented. Use JsonFileStore instead.
    """

    def __init__(self, db_path: Path | str = "configs/memory.db") -> None:
        self._db_path = Path(db_path)
        raise NotImplementedError(
            "SQLite memory store is not implemented in v4.0. "
            "Use 'json' store for persistent memory, or 'in_memory' for ephemeral memory."
        )

    def read(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError("SQLite store not implemented")

    def write(self, key: str, data: dict[str, Any]) -> None:
        raise NotImplementedError("SQLite store not implemented")

    def delete(self, key: str) -> None:
        raise NotImplementedError("SQLite store not implemented")

    def list_keys(self) -> list[str]:
        raise NotImplementedError("SQLite store not implemented")


def create_store(
    store_type: str,
    *,
    base_dir: Path | str | None = None,
) -> MemoryStore:
    """Factory function to create a memory store.

    Args:
        store_type: "in_memory" | "json" | "sqlite"
        base_dir: Base directory for JsonFileStore (defaults to "configs/players")

    Returns:
        MemoryStore instance

    Raises:
        ValueError: If store_type is unknown
        NotImplementedError: If store_type is "sqlite" (not yet implemented)
    """
    if store_type == "in_memory":
        return InMemoryStore()
    if store_type == "json":
        return JsonFileStore(base_dir or "configs/players")
    if store_type == "sqlite":
        raise NotImplementedError(
            "SQLite store is not implemented in v4.0. "
            "Use 'json' store for persistent memory."
        )
    raise ValueError(f"Unknown store type: {store_type!r}")