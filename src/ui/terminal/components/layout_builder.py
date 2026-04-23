"""UI 布局构建组件：管理 live 观战的响应式布局。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.terminal.components.event_formatter import EventFormatter
from ui.terminal.components.hand_display import HandDisplay
from ui.terminal.components.name_resolver import NameResolver
from ui.terminal.components.render import TileRenderer
from ui.terminal.components.stats_tracker import StatsTracker
from ui.terminal.components.tiles import localize_tile_codes
from ui.terminal.components.token_budget_display import TokenBudgetDisplay

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from llm.agent.token_budget import PromptDiagnostics


RenderMode = Literal["full", "normal", "compact"]


@dataclass(frozen=True, slots=True)
class LiveLayoutProfile:
    """当前终端尺寸下的 live 布局档位。"""

    mode: RenderMode
    sidebar_event_count: int
    sidebar_min_width: int
    show_score_line: bool


@dataclass(frozen=True, slots=True)
class LiveSessionSummary:
    """观战会话级摘要信息。"""

    seed: int
    target_label: str


class LayoutBuilder:
    """构建响应式 live 观战布局。"""

    def __init__(
        self,
        renderer: TileRenderer,
        stats_tracker: StatsTracker,
        event_formatter: EventFormatter,
        hand_display: HandDisplay,
        name_resolver: NameResolver,
    ) -> None:
        self._renderer = renderer
        self._stats_tracker = stats_tracker
        self._event_formatter = event_formatter
        self._hand_display = hand_display
        self._name_resolver = name_resolver
        self._token_budget_display = TokenBudgetDisplay()
        self._session_summary: LiveSessionSummary | None = None

    def set_session_summary(self, *, seed: int, target_label: str) -> None:
        """设置右侧场况区展示的会话级信息。"""
        self._session_summary = LiveSessionSummary(seed=seed, target_label=target_label)

    def build_panel(
        self,
        state: GameState,
        events: tuple,
        last_action_str: str = "",
        last_actor_seat: int | None = None,
        seat_reasons: dict[int, str] | None = None,
        show_reason: bool = True,
        viewport_width: int = 140,
        viewport_height: int = 40,
        seat_prompt_diagnostics: dict[int, "PromptDiagnostics"] | None = None,
        active_context_seat: int | None = None,
        event_history: tuple | None = None,
    ) -> Panel:
        """构建 live 牌桌主视图。"""
        profile = self._select_profile(viewport_width, viewport_height)
        seat_contexts = self._build_seat_context_lines(
            seat_prompt_diagnostics or {},
            active_context_seat=active_context_seat,
            profile=profile,
        )

        hand_panel = Panel(
            self._hand_display.render_player_tree(
                state,
                last_actor_seat,
                last_action_str,
                seat_reasons,
                show_reason,
                mode=profile.mode,
                seat_contexts=seat_contexts,
            ),
            title="[bold green]手牌[/]",
            border_style="green",
            padding=(0, 1),
        )

        sidebar = Group(
            self._render_table_status_panel(state, last_actor_seat, profile),
            self._render_events_panel(event_history or events, profile),
        )

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=3)
        grid.add_column(ratio=1, min_width=profile.sidebar_min_width)
        grid.add_row(hand_panel, sidebar)

        return Panel(grid, border_style="bright_blue", padding=(0, 1))

    def describe_table_lines(
        self,
        state: GameState,
        active_seat: int | None = None,
    ) -> tuple[Text, Text]:
        """返回局况摘要与分数摘要。"""
        from kernel.table.model import PrevailingWind

        if not hasattr(state, "table") or state.table is None:
            phase = getattr(getattr(state, "phase", None), "value", "unknown")
            return (
                Text(f"阶段 {phase}", style="white"),
                Text("牌桌信息暂不可用", style="dim"),
            )

        table = state.table
        board = state.board

        wind = "東" if table.prevailing_wind == PrevailingWind.EAST else "南"
        round_num = table.round_number.value

        line1_parts: list[tuple[str, str] | Text] = [
            (f"{wind}風{round_num}局", "bright_white"),
            (" · ", "dim"),
            (f"第{table.honba}本場", "white"),
            (" | ", "dim"),
            ("供托", "dim"),
            (f"{table.kyoutaku}", "yellow"),
        ]

        if board:
            remaining = len(board.live_wall) - board.live_draw_index
            line1_parts.extend(
                [
                    (" | ", "dim"),
                    ("余牌", "dim"),
                    (f"{remaining}", "cyan"),
                ]
            )
            if board.revealed_indicators:
                dora_codes = localize_tile_codes(
                    " ".join(tile.to_code() for tile in board.revealed_indicators)
                )
                line1_parts.extend(
                    [
                        (" | ", "dim"),
                        ("宝牌指示器 ", "dim"),
                        (f"{dora_codes}", "bright_white"),
                    ]
                )

        line1 = Text.assemble(*line1_parts)

        score_parts: list[tuple[str, str]] = []
        for seat, score in enumerate(table.scores):
            if seat > 0:
                score_parts.append((" | ", "dim"))
            name = self._name_resolver.get_name(seat, f"S{seat}")
            style = "bright_cyan" if seat == active_seat else "white"
            score_parts.extend(
                [
                    (name, style),
                    (" ", "dim"),
                    (f"{score:,}", "bold bright_yellow" if seat == active_seat else "yellow"),
                ]
            )

        return line1, Text.assemble(*score_parts)

    def _select_profile(self, viewport_width: int, viewport_height: int) -> LiveLayoutProfile:
        """根据终端尺寸选择布局档位。"""
        if viewport_height < 28 or viewport_width < 118:
            return LiveLayoutProfile(
                mode="compact",
                sidebar_event_count=5,
                sidebar_min_width=28,
                show_score_line=True,
            )
        if viewport_height < 36 or viewport_width < 152:
            return LiveLayoutProfile(
                mode="normal",
                sidebar_event_count=8,
                sidebar_min_width=30,
                show_score_line=True,
            )
        return LiveLayoutProfile(
            mode="full",
            sidebar_event_count=12,
            sidebar_min_width=32,
            show_score_line=True,
        )

    def _render_table_status_panel(
        self,
        state: GameState,
        active_seat: int | None,
        profile: LiveLayoutProfile,
    ) -> Panel:
        rows = self._build_sidebar_status_lines(state, active_seat, profile)
        return Panel(
            Group(*rows),
            title="[bold bright_cyan]场况[/]",
            border_style="bright_cyan",
            padding=(0, 1),
        )

    def _build_seat_context_lines(
        self,
        diagnostics_by_seat: dict[int, "PromptDiagnostics"],
        *,
        active_context_seat: int | None,
        profile: LiveLayoutProfile,
    ) -> dict[int, Text]:
        include_empty = profile.mode != "compact"
        lines: dict[int, Text] = {}
        for seat in range(4):
            diagnostics = diagnostics_by_seat.get(seat)
            if diagnostics is None and not include_empty:
                continue
            lines[seat] = self._token_budget_display.render_inline(
                diagnostics,
                active=diagnostics is not None and seat == active_context_seat,
            )
        return lines

    def _render_events_panel(self, events: tuple, profile: LiveLayoutProfile) -> Panel:
        return Panel(
            self._event_formatter.render_recent_events(
                events,
                max_count=profile.sidebar_event_count,
            ),
            title="[bold yellow]事件[/]",
            border_style="yellow",
            padding=(0, 1),
        )

    def _build_sidebar_status_lines(
        self,
        state: GameState,
        active_seat: int | None,
        profile: LiveLayoutProfile,
    ) -> list[Text]:
        from kernel.table.model import PrevailingWind

        if not hasattr(state, "table") or state.table is None:
            phase = getattr(getattr(state, "phase", None), "value", "unknown")
            return [Text(f"阶段 {phase}", style="white")]

        table = state.table
        board = state.board
        wind = "東" if table.prevailing_wind == PrevailingWind.EAST else "南"
        round_num = table.round_number.value

        lines = [
            Text.assemble(
                (f"{wind}風{round_num}局", "bright_white"),
                ("  ·  ", "dim"),
                (f"第{table.honba}本場", "white"),
            ),
            Text.assemble(
                ("供托 ", "dim"),
                (f"{table.kyoutaku}", "yellow"),
            ),
        ]

        if board:
            remaining = len(board.live_wall) - board.live_draw_index
            lines.append(
                Text.assemble(
                    ("余牌 ", "dim"),
                    (f"{remaining}", "cyan"),
                )
            )
            if board.revealed_indicators:
                dora_codes = localize_tile_codes(
                    " ".join(tile.to_code() for tile in board.revealed_indicators)
                )
                lines.append(
                    Text.assemble(
                        ("宝牌指示器 ", "dim"),
                        (dora_codes, "bright_white"),
                    )
                )

        lines.extend(self._build_session_summary_lines())
        lines.extend(self._build_score_and_win_lines(table, active_seat))
        return lines

    def _build_session_summary_lines(self) -> list[Text]:
        if self._session_summary is None:
            return []

        return [
            Text(""),
            Text("对局设置", style="bold bright_white"),
            Text.assemble(
                ("seed ", "dim"),
                (str(self._session_summary.seed), "yellow"),
            ),
            Text.assemble(
                ("目标 ", "dim"),
                (self._session_summary.target_label, "yellow"),
            ),
        ]

    def _build_score_and_win_lines(self, table, active_seat: int | None) -> list[Text]:
        snapshot = self._stats_tracker.snapshot()
        lines: list[Text] = [
            Text(""),
            Text.assemble(
                ("点数 / 和了统计", "bold bright_white"),
                ("（已终局 ", "dim"),
                (str(snapshot.rounds), "cyan"),
                (" 局）", "dim"),
            ),
        ]

        for seat, score in enumerate(table.scores):
            name = self._name_resolver.get_name(seat, f"S{seat}")
            name_style = "bold bright_cyan" if seat == active_seat else "bright_white"
            score_style = "bold bright_yellow" if seat == active_seat else "yellow"
            wins = snapshot.win_count(seat)
            rate_label = (
                f"{round(snapshot.win_rate(seat) * 100):d}%"
                if snapshot.rounds > 0
                else "--"
            )
            lines.extend(
                [
                    Text.assemble(
                        (name, name_style),
                        (" ", "dim"),
                        (f"{score:,}点", score_style),
                    ),
                    Text.assemble(
                        ("  和了 ", "dim"),
                        (f"{wins}/{snapshot.rounds}局", "bold bright_cyan" if wins else "cyan"),
                        (" · 和了率 ", "dim"),
                        (rate_label, "yellow" if wins else "dim"),
                    ),
                ]
            )
        return lines
