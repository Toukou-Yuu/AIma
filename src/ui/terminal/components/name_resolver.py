"""玩家名字解析组件：统一处理玩家名字和风位显示。

职责：
- 解析玩家名字（带默认值）
- 生成风位 + 名字的组合显示
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from ui.terminal.components.tiles import wind_with_seat

_WIND_NAMES = ["东", "南", "西", "北"]

if TYPE_CHECKING:
    pass


class NameResolver:
    """玩家名字解析组件。

    主要职责：
    - 解析玩家名字（提供默认值）
    - 生成风位 + 名字的组合显示
    """

    def __init__(self, seat_names: dict[int, str] | None = None) -> None:
        """初始化名字解析器。

        Args:
            seat_names: 玩家名字映射（可选）
        """
        self._seat_names = seat_names or {}

    def set_seat_names(self, names: dict[int, str]) -> None:
        """设置玩家名字。"""
        self._seat_names = names

    def get_name(self, seat: int, default: str | None = None) -> str:
        """获取玩家名字。

        Args:
            seat: 座位号
            default: 默认值（可选，默认为风位名称）

        Returns:
            玩家名字或默认值
        """
        if default is None:
            default = _WIND_NAMES[seat]
        return self._seat_names.get(seat, default)

    def get_name_or_seat(self, seat: int) -> str:
        """获取玩家名字或座位号格式。

        Args:
            seat: 座位号

        Returns:
            玩家名字或 "S{seat}"
        """
        return self._seat_names.get(seat, f"S{seat}")

    def with_wind(
        self,
        seat: int,
        dealer_seat: int,
        is_active: bool = False,
    ) -> Text:
        """生成风位 + 名字的组合显示。

        Args:
            seat: 座位号
            dealer_seat: 亲家座位
            is_active: 是否为当前操作席

        Returns:
            带样式的 Rich Text
        """
        rel_wind = (seat - dealer_seat) % 4
        player_name = self._seat_names.get(seat)
        return wind_with_seat(rel_wind, seat, is_active, player_name)

    def format_winners(self, winners: tuple[int, ...]) -> str:
        """格式化和了者列表。

        Args:
            winners: 和了者座位元组

        Returns:
            和了者名字列表（用顿号分隔）
        """
        return "、".join(self.get_name(w) for w in winners)