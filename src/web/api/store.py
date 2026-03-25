"""内存对局存储（单进程 MVP）。"""

from __future__ import annotations

import uuid

from kernel.engine.state import GameState


class MatchStore:
    """``match_id`` → ``GameState``。"""

    def __init__(self) -> None:
        self._data: dict[str, GameState] = {}

    def create(self, state: GameState) -> str:
        mid = str(uuid.uuid4())
        self._data[mid] = state
        return mid

    def get(self, match_id: str) -> GameState | None:
        return self._data.get(match_id)

    def put(self, match_id: str, state: GameState) -> None:
        self._data[match_id] = state
