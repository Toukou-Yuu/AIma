"""事件格式化组件：统一处理游戏事件的显示格式。

职责：
- 格式化各类游戏事件为 Rich Text
- 渲染最近事件面板
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.text import Text

from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    GameEvent,
    HandOverEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
)
from kernel.flow.model import FlowKind
from ui.terminal.components.tiles import tile_code_to_display, tile_to_rich

if TYPE_CHECKING:
    from ui.terminal.components.name_resolver import NameResolver

_WIND_NAMES = ["东", "南", "西", "北"]


class EventFormatter:
    """事件格式化组件。

    主要职责：
    - 格式化各类游戏事件为 Rich Text
    - 渲染最近事件面板
    """

    # 鸣牌类型映射
    _CALL_KIND_NAMES = {
        "chi": "吃",
        "pon": "碰",
        "daiminkan": "大明杠",
        "ankan": "暗杠",
        "shankuminkan": "加杠",
    }

    # 流局类型映射
    _FLOW_KIND_NAMES = {
        FlowKind.EXHAUSTED: "荒牌",
        FlowKind.NINE_NINE: "九种九牌",
        FlowKind.FOUR_WINDS: "四风连打",
        FlowKind.FOUR_KANS: "四杠散",
        FlowKind.FOUR_RIICHI: "四家立直",
        FlowKind.THREE_RON: "三家和",
    }

    def __init__(self, name_resolver: NameResolver) -> None:
        """初始化事件格式化器。

        Args:
            name_resolver: 名字解析器
        """
        self._name_resolver = name_resolver

    def format_event(self, ev: GameEvent) -> Text | None:
        """格式化单个事件。

        Args:
            ev: 游戏事件

        Returns:
            格式化后的 Rich Text，或 None（不显示）
        """
        if isinstance(ev, RoundBeginEvent):
            return self._format_round_begin(ev)

        if isinstance(ev, DrawTileEvent):
            return self._format_draw_tile(ev)

        if isinstance(ev, DiscardTileEvent):
            return self._format_discard_tile(ev)

        if isinstance(ev, CallEvent):
            return self._format_call(ev)

        if isinstance(ev, RonEvent):
            return self._format_ron(ev)

        if isinstance(ev, TsumoEvent):
            return self._format_tsumo(ev)

        if isinstance(ev, HandOverEvent):
            return self._format_hand_over(ev)

        if isinstance(ev, FlowEvent):
            return self._format_flow(ev)

        return None

    def _format_round_begin(self, ev: RoundBeginEvent) -> Text:
        """格式化局开始事件。"""
        dealer_name = self._name_resolver.get_name_or_seat(ev.dealer_seat)
        return Text.assemble(
            (f"{dealer_name} 配牌 ", "dim"),
            ("宝牌指示器: ", "dim"),
            (tile_code_to_display(ev.dora_indicator.to_code()), "bright_white"),
        )

    def _format_draw_tile(self, ev: DrawTileEvent) -> Text:
        """格式化摸牌事件。"""
        src = "岭上" if ev.is_rinshan else "本墙"
        player_name = self._name_resolver.get_name(ev.seat)
        return Text.assemble(
            (player_name, "cyan"),
            (f" 从{src}摸 ", "dim"),
            tile_to_rich(ev.tile.to_code()),
        )

    def _format_discard_tile(self, ev: DiscardTileEvent) -> Text:
        """格式化打牌事件。"""
        riichi = " 立直" if ev.declare_riichi else ""
        tg = "摸切" if ev.is_tsumogiri else "手切"
        player_name = self._name_resolver.get_name(ev.seat)
        return Text.assemble(
            (player_name, "cyan"),
            (" 打 ", "dim"),
            tile_to_rich(ev.tile.to_code()),
            (f" ({tg}{riichi})", "dim"),
        )

    def _format_call(self, ev: CallEvent) -> Text:
        """格式化鸣牌事件。"""
        cn = self._CALL_KIND_NAMES.get(ev.call_kind, ev.call_kind)
        player_name = self._name_resolver.get_name(ev.seat)
        return Text.assemble(
            (player_name, "bright_magenta"),
            (f" {cn}", "bright_magenta"),
        )

    def _format_ron(self, ev: RonEvent) -> Text:
        """格式化荣和事件。"""
        player_name = self._name_resolver.get_name(ev.seat)
        discarder_name = self._name_resolver.get_name(ev.discard_seat)
        return Text.assemble(
            (player_name, "bold bright_red"),
            (" 荣和 ", "bold bright_red"),
            tile_to_rich(ev.win_tile.to_code()),
            (f" ← {discarder_name}", "dim"),
        )

    def _format_tsumo(self, ev: TsumoEvent) -> Text:
        """格式化自摸事件。"""
        rs = "岭上" if ev.is_rinshan else ""
        player_name = self._name_resolver.get_name(ev.seat)
        return Text.assemble(
            (player_name, "bold bright_red"),
            (f" 自摸和了 {rs}", "bold bright_red"),
            tile_to_rich(ev.win_tile.to_code()),
        )

    def _format_hand_over(self, ev: HandOverEvent) -> Text:
        """格式化局结束事件。"""
        if ev.winners:
            winners = self._name_resolver.format_winners(ev.winners)
            return Text.assemble(
                ("局终: ", "bold yellow"),
                (f"{winners} 和了", "bright_yellow"),
            )
        return Text("局终: 流局", style="dim")

    def _format_flow(self, ev: FlowEvent) -> Text:
        """格式化流局事件。"""
        name = self._FLOW_KIND_NAMES.get(ev.flow_kind, ev.flow_kind.value)
        return Text.assemble(
            ("流局: ", "dim"),
            (name, "yellow"),
        )

    def render_recent_events(
        self,
        events: tuple,
        max_count: int = 2,
    ) -> Group:
        """渲染最近事件面板。

        Args:
            events: 事件元组
            max_count: 最大显示数量

        Returns:
            Rich Group 对象
        """
        lines = []
        for ev in events[-max_count:]:
            line = self.format_event(ev)
            if line:
                lines.append(line)

        if not lines:
            return Group(Text("无", style="dim"))

        return Group(*lines)
