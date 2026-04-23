"""统计追踪组件：跟踪和渲染和了统计信息。"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.text import Text

_WIND_NAMES = ["东", "南", "西", "北"]


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    """当前 live 对局的和了统计快照。"""

    wins: tuple[int, int, int, int]
    rounds: int

    def win_count(self, seat: int) -> int:
        return self.wins[seat]

    def win_rate(self, seat: int) -> float:
        if self.rounds == 0:
            return 0.0
        return self.wins[seat] / self.rounds


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
            pct_str = f"{wins / self._rounds * 100:.0f}%" if self._rounds > 0 else "--"
            style = "bright_yellow" if wins > 0 else "white"
            parts.extend(
                [
                    (name, style),
                    (" 和了 ", "dim"),
                    (f"{wins}/{self._rounds}局", "bold bright_cyan" if wins > 0 else "cyan"),
                    (" 和了率 ", "dim"),
                    (pct_str, "yellow" if wins > 0 else "dim"),
                ]
            )
        return Text.assemble(*parts)

    def render_sidebar(self, dealer_seat: int, compact: bool = False) -> Group:
        """渲染右栏用的紧凑和了统计。"""
        lines = []
        for seat in range(4):
            wins = self._wins[seat]
            pct_str = f"{wins / self._rounds * 100:.0f}%" if self._rounds > 0 else "--"
            label = self._seat_names.get(seat) or f"{_WIND_NAMES[(seat - dealer_seat) % 4]}家"
            separator = "  " if compact else "  "
            line = Text.assemble(
                (label, "bright_white"),
                (separator, "dim"),
                ("和了 ", "dim"),
                (f"{wins}/{self._rounds}局", "bold bright_cyan" if wins > 0 else "cyan"),
                ("  和了率 ", "dim"),
                (pct_str, "yellow" if wins > 0 else "dim"),
            )
            lines.append(line)
        return Group(*lines)

    def snapshot(self) -> StatsSnapshot:
        """返回只读统计快照，避免外部访问私有字段。"""
        return StatsSnapshot(
            wins=(
                self._wins[0],
                self._wins[1],
                self._wins[2],
                self._wins[3],
            ),
            rounds=self._rounds,
        )

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
