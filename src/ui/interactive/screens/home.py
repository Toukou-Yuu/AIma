"""Home screen for the Textual full-screen UI."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ui.interactive.chrome import render_empty_state, render_summary_panel
from ui.interactive.data import HomeSnapshot, ReplaySummary, build_home_snapshot
from ui.interactive.screens.base import BaseScreen

_HOME_ACTIONS = (
    ("quick", "demo演示", "无需 API Key，直接观看一场 dry-run 对局"),
    ("match", "开始对局", "选择四位玩家、局数与观战方式"),
    ("profile", "角色管理", "查看角色卡片、创建角色、补充 ASCII 形象"),
    ("replay", "牌谱回放", "浏览最近牌谱并进入动态回放"),
    ("quit", "退出", "关闭全屏终端应用"),
)


class HomeScreen(BaseScreen):
    TITLE = "AIma 麻将 AI 终端"
    SUBTITLE = "动态对局、角色档案与牌谱观战"
    BORDER_STYLE = "bright_cyan"

    def __init__(self) -> None:
        super().__init__()
        self.snapshot = build_home_snapshot()
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Vertical(id="screen-body"):
            with Horizontal(classes="pane-row"):
                yield Static(classes="pane", id="home-model")
                yield Static(classes="pane", id="home-roster")
            with Horizontal(classes="pane-row pane-row-large"):
                with Vertical(classes="list-pane"):
                    yield Static(Text("主操作", style="bold bright_green"), classes="section-title")
                    yield OptionList(
                        *[Option(label, id=value) for value, label, _ in _HOME_ACTIONS],
                        id="home-actions",
                    )
                yield Static(classes="detail-pane", id="home-action-detail")
            yield Static(classes="pane", id="home-replays")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("打开", id="action-open", variant="primary")
            yield Button("刷新", id="action-refresh")
            yield Button("退出", id="action-quit", variant="error")

    def on_mount(self) -> None:
        self._refresh_home()
        self._update_action_detail("quick")
        self._refresh_timer = self.set_interval(1.5, self._refresh_home)
        option_list = self.query_one("#home-actions", OptionList)
        option_list.highlighted = 0

    def on_screen_suspend(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.pause()

    def on_screen_resume(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.resume()
        self._refresh_home()

    def _refresh_home(self) -> None:
        self.snapshot = build_home_snapshot()
        self.query_one("#home-model", Static).update(_render_home_model_panel(self.snapshot))
        self.query_one("#home-roster", Static).update(_render_home_roster_panel(self.snapshot))
        replay_panel = (
            _render_recent_replays_panel(self.snapshot.recent_replays)
            if self.snapshot.recent_replays
            else render_empty_state(
                "暂无牌谱",
                "还没有可回放的对局记录。",
                hint="先运行一场 demo 演示或正式对局，首页就会显示最近牌谱。",
            )
        )
        self.query_one("#home-replays", Static).update(replay_panel)
        self.set_status("首页数据已刷新")

    def _selected_action_id(self) -> str:
        option_list = self.query_one("#home-actions", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None:
            return "quick"
        option = option_list.get_option_at_index(highlighted)
        return option.id or "quick"

    def _update_action_detail(self, action_id: str) -> None:
        self.query_one("#home-action-detail", Static).update(_render_action_preview(action_id))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "home-actions":
            self._update_action_detail(event.option_id or "quick")

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "home-actions":
            self._open_action(event.option_id or "quick")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "action-open":
            self._open_action(self._selected_action_id())
        elif event.button.id == "action-refresh":
            self._refresh_home()
        elif event.button.id == "action-quit":
            self.app.exit()

    def _open_action(self, action_id: str) -> None:
        if action_id == "quick":
            from ui.interactive.screens.match import QuickStartScreen

            self.app.switch_screen(QuickStartScreen())
        elif action_id == "match":
            from ui.interactive.screens.match import MatchSetupScreen

            self.app.switch_screen(MatchSetupScreen())
        elif action_id == "profile":
            from ui.interactive.screens.profile import ProfileBrowserScreen

            self.app.switch_screen(ProfileBrowserScreen())
        elif action_id == "replay":
            from ui.interactive.screens.replay import ReplayBrowserScreen

            self.app.switch_screen(ReplayBrowserScreen())
        elif action_id == "quit":
            self.app.exit()


def _render_recent_replays_panel(replays: tuple[ReplaySummary, ...]) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_white", width=12, no_wrap=True)
    table.add_column(width=10, no_wrap=True)
    table.add_column()

    for replay in replays:
        table.add_row(
            replay.time_label,
            Text(replay.status_label, style="cyan" if replay.ranking_by_seat else "yellow"),
            Text(
                f"{replay.reason_label} · {replay.action_count} 动作 · {replay.stem}",
                style="white",
            ),
        )

    return Panel(
        table,
        title="[bold bright_magenta]最近牌谱[/]",
        border_style="bright_magenta",
        padding=(0, 1),
    )


def _render_home_model_panel(snapshot: HomeSnapshot) -> Panel:
    binding_summary = _format_model_binding_summary(snapshot.model)
    rows = [
        ("接入", snapshot.model.headline),
        (
            "连接状态",
            Text(
                f"{snapshot.model.connection_label} · {snapshot.model.connection_note}",
                style=snapshot.model.connection_style,
            ),
        ),
        ("座位绑定", binding_summary),
        ("Prompt", snapshot.model.prompt_format),
        ("对话日志", _bool_text(snapshot.model.conversation_logging, "已开启", "已关闭")),
        (
            "配置状态",
            _bool_text(snapshot.model.configured, snapshot.model.note, snapshot.model.note),
        ),
    ]
    return render_summary_panel("当前模型", rows, border_style="bright_cyan")


def _format_model_binding_summary(model) -> str:
    groups: dict[str, list[str]] = {}
    for binding in model.seat_bindings:
        groups.setdefault(binding.profile_name, []).append(f"S{binding.seat}")
    if not groups:
        return "未绑定"
    return " · ".join(
        f"{'/'.join(seats)} {profile}"
        for profile, seats in groups.items()
    )


def _render_home_roster_panel(snapshot: HomeSnapshot) -> Panel:
    rows = [
        (
            entry.seat_label,
            Text(f"{entry.display_name} · {entry.mode_label}", style="white"),
        )
        for entry in snapshot.roster
    ]
    return render_summary_panel("默认阵容", rows, border_style="bright_blue")


def _render_action_preview(action_id: str) -> Panel:
    label, description = next(
        (title, desc) for value, title, desc in _HOME_ACTIONS if value == action_id
    )
    return Panel(
        Text(description, style="white"),
        title=f"[bold bright_green]{label}[/]",
        border_style="bright_green",
        padding=(1, 2),
    )


def _bool_text(enabled: bool, positive: str, negative: str) -> Text:
    label = positive if enabled else negative
    return Text(label, style="green" if enabled else "yellow")

