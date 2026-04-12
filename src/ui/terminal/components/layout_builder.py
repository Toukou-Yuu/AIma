"""UI 布局构建组件：管理面板尺寸和排列。

职责：
- 构建完整的观战界面布局
- 管理场况面板、统计面板、手牌面板、事件面板
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from ui.terminal.components.event_formatter import EventFormatter
from ui.terminal.components.hand_display import HandDisplay
from ui.terminal.components.name_resolver import NameResolver
from ui.terminal.components.render import TileRenderer
from ui.terminal.components.stats_tracker import StatsTracker

if TYPE_CHECKING:
    from kernel.engine.state import GameState


class LayoutBuilder:
    """UI 布局构建组件。

    主要职责：
    - 构建完整的观战界面布局
    - 紧凑的场况和统计面板设计
    """

    def __init__(
        self,
        renderer: TileRenderer,
        stats_tracker: StatsTracker,
        event_formatter: EventFormatter,
        hand_display: HandDisplay,
        name_resolver: NameResolver,
    ) -> None:
        """初始化布局构建器。

        Args:
            renderer: 牌面渲染器
            stats_tracker: 统计追踪器
            event_formatter: 事件格式化器
            hand_display: 手牌显示组件
            name_resolver: 名字解析器
        """
        self._renderer = renderer
        self._stats_tracker = stats_tracker
        self._event_formatter = event_formatter
        self._hand_display = hand_display
        self._name_resolver = name_resolver

    def build_panel(
        self,
        state: GameState,
        events: tuple,
        last_action_str: str = "",
        last_actor_seat: int | None = None,
        seat_reasons: dict[int, str] | None = None,
        seat_decision_times: dict[int, float] | None = None,
        show_reason: bool = True,
    ) -> Panel:
        """构建完整布局面板（紧凑设计）。

        Args:
            state: 游戏状态
            events: 事件元组
            last_action_str: 上一步动作描述
            last_actor_seat: 上一步操作者座位
            seat_reasons: 各席决策理由
            seat_decision_times: 各席决策时间
            show_reason: 是否显示决策理由

        Returns:
            Rich Panel 对象
        """
        # 场况面板（紧凑两行设计）
        header = self._render_header(state, last_actor_seat)
        header_panel = Panel(
            header,
            title="[bold bright_cyan]场况[/]",
            border_style="bright_cyan",
            padding=(0, 1),
        )

        # 统计面板（紧凑一行设计）
        stats = self._stats_tracker.render_compact()
        stats_panel = Panel(
            stats,
            title="[bold bright_blue]和了[/]",
            border_style="bright_blue",
            padding=(0, 1),
        )

        # 顶部并排（紧凑）
        from rich.columns import Columns
        top_row = Columns([header_panel, stats_panel], equal=False, expand=True)

        # 手牌树
        player_tree = self._hand_display.render_player_tree(
            state,
            last_actor_seat,
            last_action_str,
            seat_reasons,
            seat_decision_times,
            show_reason,
        )
        hand_panel = Panel(
            player_tree,
            title="[bold green]手牌[/]",
            border_style="green",
            padding=(0, 2),
        )

        # 事件面板
        recent = self._event_formatter.render_recent_events(events)
        event_panel = Panel(
            recent,
            title="[bold yellow]事件[/]",
            border_style="yellow",
            height=4,
            padding=(0, 1),
        )

        # 主布局
        main_content = Group(top_row, hand_panel, event_panel)

        return Panel(main_content, border_style="bright_blue")

    def _render_header(
        self,
        state: GameState,
        active_seat: int | None = None,
    ) -> Group:
        """渲染场况信息（紧凑两行设计）。

        Args:
            state: 游戏状态
            active_seat: 当前活跃席位

        Returns:
            Rich Group 对象（两行紧凑信息）
        """
        from kernel.table.model import PrevailingWind

        table = state.table
        board = state.board

        # 风向和局数
        wind = "東" if table.prevailing_wind == PrevailingWind.EAST else "南"
        round_num = table.round_number.value

        # 第一行：局/供托/余牌/宝牌（紧凑分隔）
        line1_parts = [
            (f"{wind}風{round_num}局", "bright_white"),
            (" · ", "dim"),
            (f"第{table.honba}本場", "white"),
            (" | ", "dim"),
            ("供托", "dim"),
            (f"{table.kyoutaku}", "yellow"),
        ]

        if board:
            remaining = len(board.live_wall) - board.live_draw_index
            line1_parts.extend([
                (" | ", "dim"),
                ("余牌", "dim"),
                (f"{remaining}", "cyan"),
            ])

            # 宝牌指示器（紧凑显示）
            if board.revealed_indicators:
                line1_parts.extend([
                    (" | ", "dim"),
                    ("宝牌指示器", "dim"),
                    (" ", ""),
                ])
                for tile in board.revealed_indicators:
                    line1_parts.append(self._renderer.render_single_tile(tile))

        line1 = Text.assemble(*line1_parts)

        # 第二行：分数（紧凑分隔）
        score_parts = []
        for i, s in enumerate(table.scores):
            if i > 0:
                score_parts.append((" | ", "dim"))
            name = self._name_resolver.get_name_or_seat(i)
            is_active = i == active_seat
            score_parts.extend([
                (name, "bright_cyan" if is_active else "white"),
                (" ", ""),
                (f"{s:,}", "bold bright_yellow" if is_active else "yellow"),
            ])

        line2 = Text.assemble(*score_parts)

        return Group(line1, line2)