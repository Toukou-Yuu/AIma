"""UI 布局构建组件：管理面板尺寸和排列。

职责：
- 构建完整的观战界面布局
- 管理场况面板、统计面板、手牌面板、事件面板
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
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
    - 管理场况面板、统计面板、手牌面板、事件面板
    """

    # 默认布局尺寸
    DEFAULT_HEADER_WIDTH = 55
    DEFAULT_STATS_WIDTH = 35
    DEFAULT_EVENT_HEIGHT = 4

    def __init__(
        self,
        renderer: TileRenderer,
        stats_tracker: StatsTracker,
        event_formatter: EventFormatter,
        hand_display: HandDisplay,
        name_resolver: NameResolver,
        header_width: int = DEFAULT_HEADER_WIDTH,
        stats_width: int = DEFAULT_STATS_WIDTH,
        event_height: int = DEFAULT_EVENT_HEIGHT,
    ) -> None:
        """初始化布局构建器。

        Args:
            renderer: 牌面渲染器
            stats_tracker: 统计追踪器
            event_formatter: 事件格式化器
            hand_display: 手牌显示组件
            name_resolver: 名字解析器
            header_width: 场况面板宽度
            stats_width: 统计面板宽度
            event_height: 事件面板高度
        """
        self._renderer = renderer
        self._stats_tracker = stats_tracker
        self._event_formatter = event_formatter
        self._hand_display = hand_display
        self._name_resolver = name_resolver

        self._header_width = header_width
        self._stats_width = stats_width
        self._event_height = event_height

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
        """构建完整布局面板。

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
        # 场况面板（自适应宽度）
        header = self._render_header(state, last_actor_seat)
        header_panel = Panel(
            header,
            title="场况",
            border_style="bright_cyan",
            padding=(0, 1),
            # 不固定宽度，让内容自适应
        )

        # 统计面板（自适应宽度）
        stats = self._stats_tracker.render_stats()
        stats_panel = Panel(
            stats,
            title="和了统计",
            border_style="bright_blue",
            padding=(0, 1),
            # 不固定宽度，让内容自适应
        )

        # 顶部并排（expand=True 让列自适应）
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
            title="手牌",
            border_style="green",
            padding=(0, 2),
        )

        # 事件面板
        recent = self._event_formatter.render_recent_events(events)
        event_panel = Panel(
            recent,
            title="事件",
            border_style="yellow",
            height=self._event_height,
            padding=(0, 1),
        )

        # 主布局
        main_content = Group(top_row, hand_panel, event_panel)

        return Panel(main_content, border_style="bright_blue")

    def _render_header(
        self,
        state: GameState,
        active_seat: int | None = None,
    ) -> Table:
        """渲染场况信息表。

        Args:
            state: 游戏状态
            active_seat: 当前活跃席位

        Returns:
            Rich Table 对象
        """
        from kernel.table.model import PrevailingWind

        table = state.table
        board = state.board

        # 风向和局数
        wind = "東" if table.prevailing_wind == PrevailingWind.EAST else "南"
        round_num = table.round_number.value

        header = Table(show_header=False, box=None, padding=(0, 2))
        header.add_column("key", style="dim")
        header.add_column("value")

        # 显示局数和本场
        header.add_row("局", f"{wind}風{round_num}局 第{table.honba}本場")
        header.add_row("供托", str(table.kyoutaku))

        if board:
            remaining = len(board.live_wall) - board.live_draw_index
            header.add_row("余牌", str(remaining))

            # 宝牌指示器
            if board.revealed_indicators:
                dora_text = Text.assemble(
                    *(self._renderer.render_dora_indicators(board.revealed_indicators))
                )
                header.add_row("宝牌指示器", dora_text)

        # 点数（每行单独渲染，避免嵌套 Table 截断）
        score_lines = []
        for i, s in enumerate(table.scores):
            label = self._name_resolver.get_name_or_seat(i)
            is_active = i == active_seat
            line = Text()
            content = f"{label}: {s}"
            line.append(content, style="bold bright_cyan" if is_active else "white")
            score_lines.append(line)
        scores = Text("\n").join(score_lines)

        # 使用 Columns 并排显示场况信息和分数
        # 左侧：局/供托/余牌/宝牌指示器
        # 右侧：分数列表
        return Columns([header, scores], equal=False, expand=True)