"""统计追踪组件：跟踪和渲染和了统计信息。"""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

_WIND_NAMES = ["东", "南", "西", "北"]


class StatsTracker:
    """从事件流更新和了统计，并提供多种渲染形式。"""

    def __init__(self, seat_names: dict[int, str] | None = None) -> None:
        self._wins = [0, 0, 0, 0]
        self._rounds = 0
        self._seat_names = seat_names or {}

    def set_seat_names(self, names: dict[int, str]) -> None:
        self._seat_names = names

    def update_from_events(self, events: tuple) -> None:
        from kernel.event_log import HandOverEvent

        for event in events:
            if isinstance(event, HandOverEvent):
                self._rounds += 1
                if event.winners:
                    for winner in event.winners:
                        self._wins[winner] += 1

    def render_compact(self) -> Text:
        parts = []
        for seat in range(4):
            if seat > 0:
                parts.append((" | ", "dim"))

            name = self._seat_names.get(seat) or f"S{seat}"
            wins = self._wins[seat]
            pct_str = f"{wins / self._rounds * 100:.0f}%" if self._rounds > 0 else "—"
            style = "bright_yellow" if wins > 0 else "white"
            parts.extend(
                [
                    (name, style),
                    (": ", "dim"),
                    (str(wins), "bold bright_cyan" if wins > 0 else "cyan"),
                    ("(", "dim"),
                    (pct_str, "yellow" if wins > 0 else "dim"),
                    (")", "dim"),
                ]
            )
        return Text.assemble(*parts)

    def render_sidebar(self, dealer_seat: int, compact: bool = False) -> Group:
        """渲染右栏用的紧凑和了统计。"""
        lines = []
        for seat in range(4):
            rel_wind = _WIND_NAMES[(seat - dealer_seat) % 4]
            wins = self._wins[seat]
            pct_str = f"{wins / self._rounds * 100:.0f}%" if self._rounds > 0 else "—"
            label = rel_wind if compact else f"{rel_wind}家"
            line = Text.assemble(
                (label, "bright_white"),
                ("  ", "dim"),
                (str(wins), "bold bright_cyan" if wins > 0 else "cyan"),
                (" 次", "dim"),
                ("  ", "dim"),
                (pct_str, "yellow" if wins > 0 else "dim"),
            )
            lines.append(line)
        return Group(*lines)

    def get_win_count(self, seat: int) -> int:
        return self._wins[seat]

    def get_total_rounds(self) -> int:
        return self._rounds

    def get_win_rate(self, seat: int) -> float:
        if self._rounds == 0:
            return 0.0
        return self._wins[seat] / self._rounds

    def reset(self) -> None:
        self._wins = [0, 0, 0, 0]
        self._rounds = 0
