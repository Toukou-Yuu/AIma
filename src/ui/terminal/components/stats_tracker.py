"""统计追踪组件：跟踪和渲染和了统计信息。

职责：
- 追踪各席位的和了次数
- 计算胜率
- 渲染统计面板
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

if TYPE_CHECKING:
    from kernel.event_log import GameEvent


class StatsTracker:
    """统计追踪组件。

    主要职责：
    - 从事件流更新和了统计
    - 渲染统计面板
    - 提供胜率查询
    """

    def __init__(self, seat_names: dict[int, str] | None = None) -> None:
        """初始化统计追踪器。

        Args:
            seat_names: 玩家名字映射（可选）
        """
        self._wins = [0, 0, 0, 0]
        self._rounds = 0
        self._seat_names = seat_names or {}

    def set_seat_names(self, names: dict[int, str]) -> None:
        """设置玩家名字。"""
        self._seat_names = names

    def update_from_events(self, events: tuple) -> None:
        """从事件更新统计。

        Args:
            events: GameEvent 元组
        """
        from kernel.event_log import HandOverEvent

        for ev in events:
            if isinstance(ev, HandOverEvent):
                self._rounds += 1
                if ev.winners:
                    for w in ev.winners:
                        self._wins[w] += 1

    def render_stats(self) -> Text:
        """渲染统计面板。

        Returns:
            统计信息 Text
        """
        from wcwidth import wcswidth

        lines = []
        for i in range(4):
            player_name = self._seat_names.get(i)
            if player_name:
                seat_label = player_name
            else:
                seat_label = f"S{i}"

            wins = self._wins[i]
            rate = f"{wins}/{self._rounds}" if self._rounds > 0 else "—"
            pct = f"({wins/max(self._rounds, 1)*100:.0f}%)" if self._rounds > 0 else "(—)"

            # 计算显示宽度并填充
            display_width = wcswidth(seat_label)
            padding = max(0, 8 - display_width)
            lines.append(f"{seat_label}{' ' * padding} {wins}    {rate} {pct}")

        return Text("\n".join(lines))

    def get_win_count(self, seat: int) -> int:
        """获取指定席位的和了次数。"""
        return self._wins[seat]

    def get_total_rounds(self) -> int:
        """获取总局数。"""
        return self._rounds

    def get_win_rate(self, seat: int) -> float:
        """获取指定席位的胜率。"""
        if self._rounds == 0:
            return 0.0
        return self._wins[seat] / self._rounds

    def reset(self) -> None:
        """重置统计。"""
        self._wins = [0, 0, 0, 0]
        self._rounds = 0