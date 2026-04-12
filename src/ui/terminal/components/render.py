"""牌面渲染组件：统一处理牌的样式和格式。

将原来散落在 viewer.py 中的渲染逻辑集中管理，
提供可复用、可测试的渲染接口。
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from rich.text import Text

from kernel.replay_json import tile_from_code
from kernel.scoring.dora import dora_from_indicators
from ui.terminal.components.tiles import tile_to_rich

if TYPE_CHECKING:
    from kernel.tiles.model import Tile


class TileRenderer:
    """牌面渲染组件，统一处理牌的样式和格式。

    主要职责：
    - 渲染单张牌（带颜色和宝牌高亮）
    - 渲染手牌集合（排序 + 宝牌标记）
    - 渲染牌河（带立直标记）
    - 渲染宝牌指示器
    """

    def __init__(self) -> None:
        """初始化渲染器。"""
        pass

    def render_tile(self, tile_code: str, is_dora: bool = False) -> Text:
        """渲染单张牌。

        Args:
            tile_code: 牌码（如 '1m', '5sr', '7z'）
            is_dora: 是否为宝牌（使用红色背景高亮）

        Returns:
            带颜色的 Rich Text 对象
        """
        return tile_to_rich(tile_code, is_dora=is_dora)

    def render_hand(
        self,
        hand: Counter,
        dora_tiles: set | None = None,
    ) -> Text:
        """渲染手牌集合。

        Args:
            hand: 手牌 Counter
            dora_tiles: 宝牌集合（可选，用于高亮）

        Returns:
            排序后的手牌 Text，宝牌用红色背景标记
        """
        from llm.table_snapshot_text import _counter_sorted_str

        hand_str = _counter_sorted_str(hand)
        if not hand_str:
            return Text("（空）", style="dim")

        result = Text()
        i = 0
        first = True

        while i < len(hand_str):
            if hand_str[i] == " ":
                i += 1
                continue

            if i + 1 < len(hand_str) and hand_str[i + 1] in "mpsz":
                if i + 2 < len(hand_str) and hand_str[i + 2] == "r":
                    tile_code = hand_str[i:i + 3]
                    i += 3
                else:
                    tile_code = hand_str[i:i + 2]
                    i += 2

                if not first:
                    result.append(" ")
                first = False

                # 检查是否是宝牌
                is_dora = False
                if dora_tiles:
                    try:
                        tile = tile_from_code(tile_code)
                        is_dora = tile in dora_tiles
                    except (ValueError, KeyError):
                        pass

                result.append(tile_to_rich(tile_code, is_dora=is_dora))
            else:
                i += 1

        return result if result.plain else Text("（空）", style="dim")

    def render_river(
        self,
        river: tuple,
        seat: int,
        dora_tiles: set | None = None,
    ) -> Text:
        """渲染牌河。

        Args:
            river: RiverEntry 元组
            seat: 当前座位
            dora_tiles: 宝牌集合（可选，用于高亮）

        Returns:
            牌河 Text，立直打牌用方括号标记
        """
        result = Text()
        first = True

        for entry in river:
            if entry.seat != seat:
                continue

            if not first:
                result.append(" ")
            first = False

            tile_code = entry.tile.to_code()
            is_dora = dora_tiles and entry.tile in dora_tiles
            tile_text = tile_to_rich(tile_code, is_dora=is_dora)

            if entry.riichi:
                result.append("[", style="dim")
                result.append(tile_text)
                result.append("]", style="dim")
            else:
                result.append(tile_text)

        return result

    def render_dora_indicators(self, indicators: tuple) -> list[Text | tuple]:
        """渲染宝牌指示器列表。

        Args:
            indicators: Tile 元组

        Returns:
            Rich Text 列表（用于 Text.assemble）
        """
        result = []
        for i, tile in enumerate(indicators):
            if i > 0:
                result.append((" ", ""))
            result.append(tile_to_rich(tile.to_code()))
        return result

    def render_single_tile(self, tile: Tile) -> Text:
        """渲染单个 Tile 对象。

        Args:
            tile: Tile 对象

        Returns:
            带颜色的 Rich Text 对象
        """
        return tile_to_rich(tile.to_code())

    def compute_dora_tiles(self, revealed_indicators: tuple | None) -> set:
        """从指示器计算宝牌集合。

        Args:
            revealed_indicators: 已揭示的宝牌指示器

        Returns:
            宝牌 Tile 集合
        """
        if not revealed_indicators:
            return set()
        return set(dora_from_indicators(revealed_indicators))