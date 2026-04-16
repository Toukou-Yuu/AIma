"""Textual 全屏交互 screens。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Button, Checkbox, Input, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from llm.config import MatchEndCondition
from ui.interactive.chrome import render_empty_state, render_page_header, render_summary_panel
from ui.interactive.data import (
    HomeSnapshot,
    ReplaySummary,
    build_home_snapshot,
    load_model_summary,
    load_recent_replay_summaries,
    load_replay_summary,
)
from ui.interactive.match_session import (
    MatchSession,
    MatchSessionConfig,
    MatchSessionResult,
    MatchSessionState,
    create_session_stem,
    load_runtime_options,
)
from ui.interactive.replay_session import (
    ReplaySession,
    ReplaySessionConfig,
    ReplaySessionResult,
    ReplaySessionState,
)
from ui.interactive.utils import (
    KERNEL_CONFIG_PATH,
    PERSONA_TEMPLATES,
    PLAYERS_DIR,
    create_profile,
    list_profiles,
)
from ui.terminal.components.character_card import render_character_card

SEAT_LABELS = ("东家", "南家", "西家", "北家")

_HOME_ACTIONS = (
    ("quick", "demo演示", "无需 API Key，直接观看一场 dry-run 对局"),
    ("match", "开始对局", "选择四位玩家、局数与观战方式"),
    ("profile", "角色管理", "查看角色卡片、创建角色、补充 ASCII 形象"),
    ("replay", "牌谱回放", "浏览最近牌谱并进入动态回放"),
    ("quit", "退出", "关闭全屏终端应用"),
)
_WATCH_SPEEDS = (0.1, 0.3, 0.5, 1.0)


def _bool_text(enabled: bool, positive: str, negative: str) -> Text:
    label = positive if enabled else negative
    return Text(label, style="green" if enabled else "yellow")


def _format_timestamp(timestamp: float | None) -> str:
    if timestamp is None:
        return "未开始"
    from datetime import datetime

    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "0.0 秒"
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    minutes, remain = divmod(seconds, 60)
    return f"{int(minutes)} 分 {remain:.1f} 秒"


def _format_replay_speed(delay_seconds: float) -> str:
    return f"{delay_seconds:.1f} 秒 / 步"


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
    rows = [
        ("接入", snapshot.model.headline),
        (
            "连接状态",
            Text(
                f"{snapshot.model.connection_label} · {snapshot.model.connection_note}",
                style=snapshot.model.connection_style,
            ),
        ),
        ("Prompt", snapshot.model.prompt_format),
        ("对话日志", _bool_text(snapshot.model.conversation_logging, "已开启", "已关闭")),
        ("配置状态", _bool_text(snapshot.model.configured, snapshot.model.note, snapshot.model.note)),
    ]
    return render_summary_panel("当前模型", rows, border_style="bright_cyan")


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


def _render_profile_placeholder() -> Panel:
    return render_empty_state(
        "暂无角色",
        "configs/players 下还没有可用角色。",
        hint="先创建角色，之后这里会显示角色卡片预览。",
    )


def _match_status(session: MatchSession) -> tuple[str, str]:
    if session.state == MatchSessionState.RUNNING:
        return ("运行中", "green")
    if session.state == MatchSessionState.FINISHED:
        return ("已完成", "cyan")
    if session.state == MatchSessionState.FAILED:
        return ("失败", "red")
    return ("等待启动", "yellow")


def _render_match_runtime_panel(session: MatchSession) -> Panel:
    status_label, status_style = _match_status(session)
    snapshot = session.snapshot
    rows = [
        ("状态", Text(status_label, style=status_style)),
        ("开始时间", _format_timestamp(session.started_at)),
        ("最近动作", snapshot.action_label),
        ("最新阶段", snapshot.phase_label),
        ("快照步数", str(snapshot.callback_steps)),
    ]
    return render_summary_panel("对局状态", rows, border_style="bright_cyan")


def _render_match_config_panel(session: MatchSession) -> Panel:
    player_text = " / ".join(
        f"{SEAT_LABELS[seat]} {name}"
        for seat, name in sorted(session.player_names.items())
    )
    rows = [
        ("模式", "Dry-run" if session.config.dry_run else "LLM 对局"),
        ("seed", str(session.config.seed)),
        ("目标局数", str(session.config.target_hands)),
        ("玩家", player_text),
        ("日志 stem", session.logs.stem),
    ]
    return render_summary_panel("配置摘要", rows, border_style="bright_blue")


def _render_match_log_panel(result: MatchSessionResult) -> Panel:
    rows = [
        ("牌谱日志", str(result.logs.replay_path)),
        ("调试日志", str(result.logs.debug_path)),
        ("可读日志", str(result.logs.simple_path)),
    ]
    return render_summary_panel("日志记录", rows, border_style="bright_magenta")


def _render_match_standings_panel(result: MatchSessionResult) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_white", width=8, no_wrap=True)
    table.add_column(width=18, no_wrap=True)
    table.add_column(justify="right", width=10, no_wrap=True)

    if result.run_result is None:
        table.add_row("状态", "未生成结算", "-")
    else:
        final_state = result.run_result.final_state
        scores = final_state.table.scores
        dealer = final_state.table.dealer_seat
        ranking = sorted(
            range(4),
            key=lambda seat: (-scores[seat], (seat - dealer) % 4),
        )
        for index, seat in enumerate(ranking, start=1):
            table.add_row(
                f"{index} 位",
                f"{SEAT_LABELS[seat]} {result.player_names.get(seat, f'S{seat}')}",
                f"{scores[seat]:,}",
            )

    return Panel(
        table,
        title="[bold bright_green]最终排名[/]",
        border_style="bright_green",
        padding=(0, 1),
    )


def _render_match_overview_panel(session: MatchSession, result: MatchSessionResult) -> Panel:
    rows = [
        ("状态", "正常完成" if result.succeeded else "执行失败"),
        ("结束原因", result.run_result.stopped_reason if result.run_result else (result.error_message or "unknown")),
        ("耗时", _format_duration(result.duration_seconds)),
        ("seed", str(session.config.seed)),
        ("目标局数", str(session.config.target_hands)),
    ]
    if result.error_message:
        rows.append(("错误", Text(result.error_message, style="red")))
    return render_summary_panel("对局概览", rows, border_style="bright_cyan")


def _replay_status(session: ReplaySession) -> tuple[str, str]:
    if session.state == ReplaySessionState.RUNNING:
        return ("播放中", "green")
    if session.state == ReplaySessionState.PAUSED:
        return ("已暂停", "yellow")
    if session.state == ReplaySessionState.FINISHED:
        return ("已完成", "cyan")
    if session.state == ReplaySessionState.FAILED:
        return ("失败", "red")
    if session.state == ReplaySessionState.STOPPED:
        return ("已退出", "yellow")
    return ("等待启动", "yellow")


def _render_replay_runtime_panel(session: ReplaySession) -> Panel:
    status_label, status_style = _replay_status(session)
    snapshot = session.snapshot
    rows = [
        ("状态", Text(status_label, style=status_style)),
        ("开始时间", _format_timestamp(session.started_at)),
        ("当前步骤", f"{snapshot.current_step} / {snapshot.total_steps}"),
        ("最近动作", snapshot.action_label),
        ("当前阶段", snapshot.phase_label),
    ]
    return render_summary_panel("回放状态", rows, border_style="bright_cyan")


def _render_replay_summary_panel(summary: ReplaySummary, delay_seconds: float) -> Panel:
    rows = [
        ("记录时间", summary.time_label),
        ("seed", str(summary.seed) if summary.seed is not None else "未记录"),
        ("结束状态", summary.status_label),
        ("结束原因", summary.reason_label),
        ("终局阶段", summary.final_phase),
        ("动作数", str(summary.action_count)),
        ("当前速度", _format_replay_speed(delay_seconds)),
    ]
    return render_summary_panel("牌谱概览", rows, border_style="bright_blue")


def _render_replay_result_panel(result: ReplaySessionResult, delay_seconds: float) -> Panel:
    rows = [
        ("状态", "正常完成" if result.succeeded else "执行失败"),
        ("耗时", _format_duration(result.duration_seconds)),
        ("结束状态", result.summary.status_label),
        ("回放速度", _format_replay_speed(delay_seconds)),
    ]
    if result.error_message:
        rows.append(("错误", Text(result.error_message, style="red")))
    return render_summary_panel("回放结果", rows, border_style="bright_magenta")


def _render_form_summary(title: str, rows: list[tuple[str, str | Text]], border_style: str = "bright_blue") -> Panel:
    return render_summary_panel(title, rows, border_style=border_style)


def _float_choice(current: float, step: int) -> float:
    try:
        index = _WATCH_SPEEDS.index(round(current, 1))
    except ValueError:
        return _WATCH_SPEEDS[0]
    next_index = min(max(index + step, 0), len(_WATCH_SPEEDS) - 1)
    return _WATCH_SPEEDS[next_index]


class BaseScreen(Screen[None]):
    """通用 screen 基类。"""

    TITLE = ""
    SUBTITLE = ""
    BORDER_STYLE = "bright_cyan"
    HEADER_WIDTH = 88

    def build_header(self) -> Panel:
        return render_page_header(
            self.TITLE,
            subtitle=self.SUBTITLE,
            border_style=self.BORDER_STYLE,
            width=self.HEADER_WIDTH,
        )

    def set_status(self, message: str, style: str = "dim") -> None:
        status = self.query_one("#status-line", Static)
        status.update(Text(message, style=style))

    def open_home(self) -> None:
        self.app.switch_screen(HomeScreen())


class OptionPickerScreen(ModalScreen[str | None]):
    """通用选项选择弹层。"""

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        options: list[tuple[str, str]],
        current_value: str | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.options = options
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        with Container(id="picker-modal"):
            yield Static(
                render_page_header(
                    self.title,
                    subtitle=self.subtitle,
                    border_style="bright_cyan",
                    width=72,
                ),
                id="picker-header",
            )
            yield OptionList(
                *[Option(label, id=value) for label, value in self.options],
                id="picker-options",
            )
            with Horizontal(classes="action-bar modal-actions"):
                yield Button("确认选择", id="picker-confirm", variant="primary")
                yield Button("取消", id="picker-cancel")

    def on_mount(self) -> None:
        option_list = self.query_one("#picker-options", OptionList)
        if self.current_value is None:
            option_list.highlighted = 0
            return
        for index, (_label, value) in enumerate(self.options):
            if value == self.current_value:
                option_list.highlighted = index
                return
        option_list.highlighted = 0

    def _selected_value(self) -> str | None:
        option_list = self.query_one("#picker-options", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None or highlighted >= len(self.options):
            return None
        option = option_list.get_option_at_index(highlighted)
        return option.id

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "picker-options":
            self.dismiss(event.option_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-cancel":
            self.dismiss(None)
        elif event.button.id == "picker-confirm":
            self.dismiss(self._selected_value())


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
            self.app.switch_screen(QuickStartScreen())
        elif action_id == "match":
            self.app.switch_screen(MatchSetupScreen())
        elif action_id == "profile":
            self.app.switch_screen(ProfileBrowserScreen())
        elif action_id == "replay":
            self.app.switch_screen(ReplayBrowserScreen())
        elif action_id == "quit":
            self.app.exit()


class QuickStartScreen(BaseScreen):
    TITLE = "demo演示"
    SUBTITLE = "dry-run 单局动态观战"
    BORDER_STYLE = "bright_green"

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="form-pane"):
                yield Static(Text("基础设置", style="bold bright_green"), classes="section-title")
                yield Input(value="42", placeholder="随机种子", id="quick-seed")
                yield Checkbox("实时观战", value=True, id="quick-watch")
                yield Input(value="0.3", placeholder="观战延迟（秒）", id="quick-delay")
            yield Static(classes="detail-pane", id="quick-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("开始演示", id="quick-start", variant="primary")
            yield Button("返回首页", id="quick-home")

    def on_mount(self) -> None:
        self._refresh_summary()
        self.query_one("#quick-start", Button).focus()

    def _refresh_summary(self) -> None:
        seed = self.query_one("#quick-seed", Input).value or "42"
        watch = self.query_one("#quick-watch", Checkbox).value
        delay = self.query_one("#quick-delay", Input).value or "0.3"
        rows = [
            ("随机种子", "随机" if seed == "0" else seed),
            ("观战模式", "实时观战" if watch else "后台快速完成"),
        ]
        if watch:
            rows.append(("观战延迟", f"{delay} 秒"))
        self.query_one("#quick-summary", Static).update(
            _render_form_summary("当前配置", rows, border_style="bright_green")
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"quick-seed", "quick-delay"}:
            self._refresh_summary()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "quick-watch":
            self._refresh_summary()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quick-home":
            self.open_home()
            return
        if event.button.id != "quick-start":
            return

        try:
            seed = int(self.query_one("#quick-seed", Input).value or "42")
            delay = float(self.query_one("#quick-delay", Input).value or "0.3")
        except ValueError:
            self.set_status("seed 和观战延迟必须是数字", "red")
            return

        watch = self.query_one("#quick-watch", Checkbox).value
        config = MatchSessionConfig(
            label="demo演示",
            config_path=KERNEL_CONFIG_PATH,
            seed=seed,
            match_end=MatchEndCondition(type="hands", value=1, allow_negative=False),
            dry_run=True,
            watch_enabled=watch,
            watch_delay=delay if watch else 0.0,
            request_delay_seconds=0.0,
            players=None,
            session_stem=create_session_stem("demo"),
        )
        session = MatchSession(config)
        session.start()
        if watch:
            self.app.switch_screen(LiveMatchScreen(session))
        else:
            self.app.switch_screen(MatchControlScreen(session))


class MatchSetupScreen(BaseScreen):
    TITLE = "开始对局"
    SUBTITLE = "选择四家角色与运行方式"
    BORDER_STYLE = "bright_yellow"

    def __init__(self) -> None:
        super().__init__()
        self._profiles = list_profiles()
        self._profile_options = [("默认 AI (dry-run)", "default")] + [
            (profile["name"], profile["id"]) for profile in self._profiles
        ]
        self._selected_player_ids = ["default", "default", "default", "default"]

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="form-pane"):
                yield Static(Text("玩家配置", style="bold bright_yellow"), classes="section-title")
                for seat, label in enumerate(SEAT_LABELS):
                    yield Button(f"{label}: 默认 AI (dry-run)", id=f"match-seat-{seat}", classes="picker-button")
                yield Static(Text("运行参数", style="bold bright_yellow"), classes="section-title")
                yield Input(value="", placeholder="随机种子：留空或填 0 表示每次随机生成一场新对局", id="match-seed")
                yield Input(value="", placeholder="目标局数：留空默认 8，4=东风战，8=半庄战", id="match-hands")
                yield Checkbox("实时观战", value=True, id="match-watch")
                yield Input(value="", placeholder="观战延迟：留空默认 0.5 秒，控制每个动作之间暂停多久", id="match-delay")
            yield Static(classes="detail-pane", id="match-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("开始对局", id="match-start", variant="primary")
            yield Button("返回首页", id="match-home")

    def on_mount(self) -> None:
        self._refresh_summary()
        self.query_one("#match-start", Button).focus()

    def _selected_players(self) -> list[dict[str, Any]]:
        return [
            {"id": player_id, "seat": seat}
            for seat, player_id in enumerate(self._selected_player_ids)
        ]

    def _player_display_name(self, player_id: str) -> str:
        if player_id == "default":
            return "默认 AI (dry-run)"
        for label, value in self._profile_options:
            if value == player_id:
                return label
        return player_id

    def _refresh_player_buttons(self) -> None:
        for seat, player_id in enumerate(self._selected_player_ids):
            button = self.query_one(f"#match-seat-{seat}", Button)
            button.label = f"{SEAT_LABELS[seat]}: {self._player_display_name(player_id)}"

    def _refresh_summary(self) -> None:
        self._refresh_player_buttons()
        players = self._selected_players()
        seed = self.query_one("#match-seed", Input).value or "0"
        max_hands = self.query_one("#match-hands", Input).value or "8"
        watch = self.query_one("#match-watch", Checkbox).value
        delay = self.query_one("#match-delay", Input).value or "0.5"
        rows = [
            ("玩家", " / ".join(f"{SEAT_LABELS[p['seat']]} {self._player_display_name(str(p['id']))}" for p in players)),
            ("随机种子", "随机" if seed == "0" else seed),
            ("目标局数", max_hands),
            ("观战模式", "实时观战" if watch else "后台运行"),
        ]
        if watch:
            rows.append(("观战延迟", f"{delay} 秒"))
        self.query_one("#match-summary", Static).update(
            _render_form_summary("当前对局计划", rows, border_style="bright_yellow")
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"match-seed", "match-hands", "match-delay"}:
            self._refresh_summary()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "match-watch":
            self._refresh_summary()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "match-home":
            self.open_home()
            return
        if event.button.id.startswith("match-seat-"):
            seat = int(event.button.id.rsplit("-", 1)[1])
            await self.app.push_screen(
                OptionPickerScreen(
                    title="选择对局角色",
                    subtitle=f"为 {SEAT_LABELS[seat]} 选择一名玩家",
                    options=self._profile_options,
                    current_value=self._selected_player_ids[seat],
                ),
                callback=lambda value, seat=seat: self._apply_match_player(seat, value),
            )
            return
        if event.button.id != "match-start":
            return

        try:
            seed = int(self.query_one("#match-seed", Input).value or "0")
            max_hands = int(self.query_one("#match-hands", Input).value or "8")
            delay = float(self.query_one("#match-delay", Input).value or "0.5")
        except ValueError:
            self.set_status("seed、局数和观战延迟都必须是数字", "red")
            return

        watch = self.query_one("#match-watch", Checkbox).value
        players = self._selected_players()
        uses_llm = any(player["id"] != "default" for player in players)
        model_summary = load_model_summary(KERNEL_CONFIG_PATH)
        if uses_llm and not model_summary.configured:
            self.set_status("当前未配置可用 LLM，正式对局只能选择默认 AI 或先补齐模型配置", "red")
            return

        runtime_options = _runtime_options()
        config = MatchSessionConfig(
            label="正式对局",
            config_path=KERNEL_CONFIG_PATH,
            seed=seed,
            match_end=MatchEndCondition(type="hands", value=max_hands, allow_negative=False),
            dry_run=not uses_llm,
            watch_enabled=watch,
            watch_delay=delay if watch else 0.0,
            request_delay_seconds=0.0 if not uses_llm else float(runtime_options["request_delay_seconds"]),
            players=players,
            max_history_rounds=int(runtime_options["max_history_rounds"]),
            clear_history_per_hand=bool(runtime_options["clear_history_per_hand"]),
            enable_conversation_logging=bool(runtime_options["enable_conversation_logging"]),
            session_stem=create_session_stem("match"),
        )
        session = MatchSession(config)
        session.start()
        if watch:
            self.app.switch_screen(LiveMatchScreen(session))
        else:
            self.app.switch_screen(MatchControlScreen(session))

    def _apply_match_player(self, seat: int, value: str | None) -> None:
        if value is None:
            return
        self._selected_player_ids[seat] = value
        self._refresh_summary()


class LiveMatchScreen(BaseScreen):
    TITLE = "动态观战"
    SUBTITLE = "后台对局持续进行，画面会自动刷新"
    BORDER_STYLE = "bright_green"

    def __init__(self, session: MatchSession) -> None:
        super().__init__()
        self.session = session
        self._navigated_to_settlement = False
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Vertical(id="screen-body"):
            with Horizontal(classes="pane-row"):
                yield Static(classes="pane", id="match-runtime")
                yield Static(classes="pane", id="match-config")
            yield Static(classes="live-pane", id="match-live-panel")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("离开观战", id="match-detach", variant="primary")
            yield Button("进入控制台", id="match-control")

    def on_mount(self) -> None:
        self._refresh_live()
        self._refresh_timer = self.set_interval(0.25, self._refresh_live)

    def on_screen_suspend(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.pause()

    def on_screen_resume(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.resume()
        self._refresh_live()

    def _refresh_live(self) -> None:
        self.query_one("#match-runtime", Static).update(_render_match_runtime_panel(self.session))
        self.query_one("#match-config", Static).update(_render_match_config_panel(self.session))
        snapshot = self.session.snapshot
        if snapshot.panel is None:
            self.query_one("#match-live-panel", Static).update(
                render_empty_state(
                    "等待首帧",
                    "后台对局已启动，正在等待第一帧牌桌快照。",
                    hint="牌局一旦推进，这里会自动刷新。",
                )
            )
        else:
            self.query_one("#match-live-panel", Static).update(snapshot.panel)
        if self.session.is_finished and not self._navigated_to_settlement:
            self._navigated_to_settlement = True
            self.call_after_refresh(self._open_settlement)

    async def _open_settlement(self) -> None:
        result = self.session.result
        if result is not None:
            self.app.switch_screen(MatchSettlementScreen(self.session))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "match-detach":
            self.app.switch_screen(MatchControlScreen(self.session))
        elif event.button.id == "match-control":
            self.app.switch_screen(MatchControlScreen(self.session))


class MatchControlScreen(BaseScreen):
    TITLE = "对局控制台"
    SUBTITLE = "这里查看后台对局状态，不会中断当前会话"
    BORDER_STYLE = "bright_yellow"

    def __init__(self, session: MatchSession) -> None:
        super().__init__()
        self.session = session
        self._navigated_to_settlement = False
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Vertical(id="screen-body"):
            with Horizontal(classes="pane-row"):
                yield Static(classes="pane", id="match-control-runtime")
                yield Static(classes="pane", id="match-control-config")
            yield Static(classes="pane", id="match-control-extra")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("进入观战", id="control-watch", variant="primary")
            yield Button("等待结束", id="control-wait")
            yield Button("返回首页", id="control-home")

    def on_mount(self) -> None:
        self._refresh_control()
        self._refresh_timer = self.set_interval(0.25, self._refresh_control)

    def on_screen_suspend(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.pause()

    def on_screen_resume(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.resume()
        self._refresh_control()

    def _refresh_control(self) -> None:
        self.query_one("#match-control-runtime", Static).update(_render_match_runtime_panel(self.session))
        self.query_one("#match-control-config", Static).update(_render_match_config_panel(self.session))
        result = self.session.result
        if result is not None:
            self.query_one("#match-control-extra", Static).update(_render_match_log_panel(result))
        else:
            snapshot = self.session.snapshot
            self.query_one("#match-control-extra", Static).update(
                _render_form_summary(
                    "后台状态",
                    [
                        ("最近动作", snapshot.action_label),
                        ("最新阶段", snapshot.phase_label),
                        ("开始时间", _format_timestamp(self.session.started_at)),
                    ],
                    border_style="bright_magenta",
                )
            )
        home_button = self.query_one("#control-home", Button)
        home_button.disabled = not self.session.is_finished
        if self.session.is_finished and not self._navigated_to_settlement:
            self._navigated_to_settlement = True
            self.call_after_refresh(self._open_settlement)

    async def _open_settlement(self) -> None:
        self.app.switch_screen(MatchSettlementScreen(self.session))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "control-watch":
            self.app.switch_screen(LiveMatchScreen(self.session))
        elif event.button.id == "control-wait":
            self.set_status("保持在当前页，等待对局自然结束", "yellow")
        elif event.button.id == "control-home" and self.session.is_finished:
            self.open_home()


class MatchSettlementScreen(BaseScreen):
    TITLE = "对局结算"
    SUBTITLE = "这场对局已经结束，先看结果再决定下一步"
    BORDER_STYLE = "bright_magenta"

    def __init__(self, session: MatchSession) -> None:
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Vertical(id="screen-body"):
            with Horizontal(classes="pane-row"):
                yield Static(classes="pane", id="settlement-overview")
                yield Static(classes="pane", id="settlement-logs")
            yield Static(classes="pane", id="settlement-standings")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("回放这场对局", id="settlement-replay", variant="primary")
            yield Button("再来一局", id="settlement-restart")
            yield Button("返回首页", id="settlement-home")

    def on_mount(self) -> None:
        self._refresh_settlement()

    def _refresh_settlement(self) -> None:
        result = self.session.result
        if result is None:
            self.query_one("#settlement-overview", Static).update(
                render_empty_state("暂无结果", "后台会话尚未生成结算。")
            )
            return
        self.query_one("#settlement-overview", Static).update(
            _render_match_overview_panel(self.session, result)
        )
        self.query_one("#settlement-logs", Static).update(_render_match_log_panel(result))
        self.query_one("#settlement-standings", Static).update(_render_match_standings_panel(result))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        result = self.session.result
        if event.button.id == "settlement-home":
            self.open_home()
        elif event.button.id == "settlement-restart":
            config = replace(
                self.session.config,
                session_stem=create_session_stem(self.session.config.label),
            )
            new_session = MatchSession(config)
            new_session.start()
            if new_session.config.watch_enabled:
                self.app.switch_screen(LiveMatchScreen(new_session))
            else:
                self.app.switch_screen(MatchControlScreen(new_session))
        elif event.button.id == "settlement-replay" and result is not None:
            summary = load_replay_summary(result.logs.replay_path)
            await self.app.push_screen(ReplayDetailScreen(summary))


class ReplayBrowserScreen(BaseScreen):
    TITLE = "牌谱回放"
    SUBTITLE = "先浏览牌谱摘要，再进入动态回放"
    BORDER_STYLE = "bright_magenta"

    def __init__(self) -> None:
        super().__init__()
        self._replays: tuple[ReplaySummary, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="list-pane"):
                yield Static(Text("最近牌谱", style="bold bright_magenta"), classes="section-title")
                yield OptionList(id="replay-list")
            yield Static(classes="detail-pane", id="replay-preview")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("查看详情", id="replay-open", variant="primary")
            yield Button("刷新列表", id="replay-refresh")
            yield Button("返回首页", id="replay-home")

    def on_mount(self) -> None:
        self._refresh_replays()

    def _refresh_replays(self) -> None:
        self._replays = load_recent_replay_summaries(limit=20)
        option_list = self.query_one("#replay-list", OptionList)
        option_list.clear_options()
        if not self._replays:
            self.query_one("#replay-preview", Static).update(
                render_empty_state(
                    "暂无牌谱",
                    "还没有可回放的牌谱记录。",
                    hint="完成一场 demo 演示或正式对局后，这里会自动显示最新牌谱。",
                )
            )
            return
        option_list.add_options(
            [Option(summary.menu_label, id=summary.stem) for summary in self._replays]
        )
        option_list.highlighted = 0
        self._update_preview(self._replays[0])

    def _selected_summary(self) -> ReplaySummary | None:
        option_list = self.query_one("#replay-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None or highlighted >= len(self._replays):
            return None
        return self._replays[highlighted]

    def _update_preview(self, summary: ReplaySummary) -> None:
        self.query_one("#replay-preview", Static).update(
            Group(
                _render_replay_summary_panel(summary, 0.5),
                _render_form_summary(
                    "终局结果",
                    [
                        ("名次", summary.ranking_label),
                        ("分数", summary.score_label),
                    ],
                    border_style="bright_green",
                ),
            )
        )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "replay-list":
            summary = self._selected_summary()
            if summary is not None:
                self._update_preview(summary)

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "replay-list":
            summary = self._selected_summary()
            if summary is not None:
                await self.app.push_screen(ReplayDetailScreen(summary))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "replay-home":
            self.open_home()
        elif event.button.id == "replay-refresh":
            self._refresh_replays()
        elif event.button.id == "replay-open":
            summary = self._selected_summary()
            if summary is not None:
                await self.app.push_screen(ReplayDetailScreen(summary))


class ReplayDetailScreen(BaseScreen):
    TITLE = "回放详情"
    SUBTITLE = "动态回放会在全屏 live 画面中播放"
    BORDER_STYLE = "bright_magenta"

    def __init__(self, summary: ReplaySummary):
        super().__init__()
        self.summary = summary
        self.delay_seconds = 0.5

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            yield Static(classes="detail-pane", id="replay-detail-main")
            yield Static(classes="detail-pane", id="replay-detail-side")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("开始回放", id="replay-start", variant="primary")
            yield Button("减速", id="replay-slower")
            yield Button("加速", id="replay-faster")
            yield Button("返回浏览", id="replay-back")

    def on_mount(self) -> None:
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        self.query_one("#replay-detail-main", Static).update(
            _render_replay_summary_panel(self.summary, self.delay_seconds)
        )
        self.query_one("#replay-detail-side", Static).update(
            _render_form_summary(
                "终局结果",
                [
                    ("名次", self.summary.ranking_label),
                    ("分数", self.summary.score_label),
                    ("牌谱文件", str(self.summary.path)),
                ],
                border_style="bright_green",
            )
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "replay-back":
            self.dismiss()
        elif event.button.id == "replay-start":
            session = ReplaySession(
                ReplaySessionConfig(
                    replay_path=self.summary.path,
                    delay_seconds=self.delay_seconds,
                    label=f"回放 {self.summary.stem}",
                )
            )
            session.start()
            await self.app.push_screen(ReplayLiveScreen(session, self))
        elif event.button.id == "replay-slower":
            self.delay_seconds = _float_choice(self.delay_seconds, +1)
            self._refresh_detail()
        elif event.button.id == "replay-faster":
            self.delay_seconds = _float_choice(self.delay_seconds, -1)
            self._refresh_detail()


class ReplayLiveScreen(BaseScreen):
    TITLE = "牌谱动态回放"
    SUBTITLE = "自动播放，可暂停、调速，并随时返回详情页"
    BORDER_STYLE = "bright_green"

    def __init__(self, session: ReplaySession, detail_screen: ReplayDetailScreen):
        super().__init__()
        self.session = session
        self.detail_screen = detail_screen
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Vertical(id="screen-body"):
            with Horizontal(classes="pane-row"):
                yield Static(classes="pane", id="replay-runtime")
                yield Static(classes="pane", id="replay-summary")
            yield Static(classes="live-pane", id="replay-live-panel")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("暂停/继续", id="replay-toggle", variant="primary")
            yield Button("减速", id="replay-live-slower")
            yield Button("加速", id="replay-live-faster")
            yield Button("退出到详情", id="replay-exit")

    def on_mount(self) -> None:
        self._refresh_live()
        self._refresh_timer = self.set_interval(0.2, self._refresh_live)

    def on_screen_suspend(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.pause()

    def on_screen_resume(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.resume()
        self._refresh_live()

    def _refresh_live(self) -> None:
        self.query_one("#replay-runtime", Static).update(_render_replay_runtime_panel(self.session))
        self.query_one("#replay-summary", Static).update(
            _render_replay_summary_panel(self.session.summary, self.session.config.delay_seconds)
        )
        snapshot = self.session.snapshot
        if snapshot.panel is None:
            self.query_one("#replay-live-panel", Static).update(
                render_empty_state("等待首帧", "牌谱回放已启动，正在等待第一帧画面。")
            )
        else:
            self.query_one("#replay-live-panel", Static).update(snapshot.panel)
        if self.session.is_finished and self.session.result is not None:
            self.query_one("#status-line", Static).update(
                Text("回放已结束，可以退出到详情页查看摘要。", style="yellow")
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "replay-toggle":
            self.session.toggle_pause()
            self._refresh_live()
        elif event.button.id == "replay-live-slower":
            self.session.set_delay(_float_choice(self.session.config.delay_seconds, +1))
            self._refresh_live()
        elif event.button.id == "replay-live-faster":
            self.session.set_delay(_float_choice(self.session.config.delay_seconds, -1))
            self._refresh_live()
        elif event.button.id == "replay-exit":
            self.session.stop()
            self.detail_screen.delay_seconds = self.session.config.delay_seconds
            self.detail_screen._refresh_detail()
            self.dismiss()


class ProfileBrowserScreen(BaseScreen):
    TITLE = "角色管理"
    SUBTITLE = "左侧选择角色，右侧实时预览角色卡片"
    BORDER_STYLE = "bright_magenta"

    def __init__(self) -> None:
        super().__init__()
        self._profiles: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="list-pane"):
                yield Static(Text("角色列表", style="bold bright_magenta"), classes="section-title")
                yield OptionList(id="profile-list")
            with VerticalScroll(classes="detail-pane", id="profile-preview-scroll"):
                yield Static(id="profile-preview")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("创建角色", id="profile-create", variant="primary")
            yield Button("添加 ASCII", id="profile-ascii")
            yield Button("返回首页", id="profile-home")

    def on_mount(self) -> None:
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        self._profiles = list_profiles()
        option_list = self.query_one("#profile-list", OptionList)
        option_list.clear_options()
        if not self._profiles:
            self.query_one("#profile-preview", Static).update(_render_profile_placeholder())
            return
        option_list.add_options(
            [Option(profile["name"], id=profile["id"]) for profile in self._profiles]
        )
        option_list.highlighted = 0
        self._update_preview(self._profiles[0]["id"])

    def _selected_profile_id(self) -> str | None:
        option_list = self.query_one("#profile-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None or highlighted >= len(self._profiles):
            return None
        option = option_list.get_option_at_index(highlighted)
        return option.id

    def _update_preview(self, player_id: str) -> None:
        self.query_one("#profile-preview", Static).update(
            render_character_card(player_id, PLAYERS_DIR)
        )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "profile-list" and event.option_id:
            self._update_preview(event.option_id)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-home":
            self.open_home()
        elif event.button.id == "profile-create":
            await self.app.push_screen(CreateProfileScreen(self))
        elif event.button.id == "profile-ascii":
            await self.app.push_screen(AddAsciiScreen(self))


class ProfileDetailScreen(BaseScreen):
    TITLE = "角色详情"
    SUBTITLE = "完整角色卡片"
    BORDER_STYLE = "bright_magenta"

    def __init__(self, player_id: str):
        super().__init__()
        self.player_id = player_id

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with VerticalScroll(id="screen-body", classes="detail-pane"):
            yield Static(render_character_card(self.player_id, PLAYERS_DIR), id="profile-detail-card")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("返回角色列表", id="profile-detail-back", variant="primary")
            yield Button("返回首页", id="profile-detail-home")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-detail-home":
            self.dismiss()
            self.call_after_refresh(self.open_home)
        elif event.button.id == "profile-detail-back":
            self.dismiss()


class CreateProfileScreen(BaseScreen):
    TITLE = "创建新角色"
    SUBTITLE = "输入角色标识、显示名与人格模板"
    BORDER_STYLE = "bright_green"

    def __init__(self, browser: ProfileBrowserScreen):
        super().__init__()
        self.browser = browser
        self._selected_template = "balanced"

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="form-pane"):
                yield Input(placeholder="角色标识（仅字母数字）", id="profile-id")
                yield Input(placeholder="显示名称", id="profile-name")
                yield Button("人格模板: 平衡型", id="profile-template", classes="picker-button")
                yield Checkbox("自定义人格描述", value=False, id="profile-customize")
                yield TextArea("", id="profile-persona")
            yield Static(classes="detail-pane", id="profile-create-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("创建角色", id="profile-create-submit", variant="primary")
            yield Button("返回角色列表", id="profile-create-back")

    def on_mount(self) -> None:
        self.query_one("#profile-persona", TextArea).disabled = True
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        template = PERSONA_TEMPLATES[self._selected_template]
        self.query_one("#profile-template", Button).label = f"人格模板: {template['name']}"
        rows: list[tuple[str, str | Text]] = [
            ("角色标识", self.query_one("#profile-id", Input).value or "(待填写)"),
            ("显示名称", self.query_one("#profile-name", Input).value or "(待填写)"),
            ("人格模板", template["name"]),
            ("策略摘要", template["strategy"]),
        ]
        if self.query_one("#profile-customize", Checkbox).value:
            custom_persona = self.query_one("#profile-persona", TextArea).text.strip()
            rows.append(("自定义人格", custom_persona or "(待填写)"))
        self.query_one("#profile-create-summary", Static).update(
            _render_form_summary("角色草案", rows, border_style="bright_green")
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"profile-id", "profile-name"}:
            self._refresh_summary()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "profile-customize":
            self.query_one("#profile-persona", TextArea).disabled = not event.value
            self._refresh_summary()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        del event
        self._refresh_summary()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-create-back":
            self.browser._refresh_profiles()
            self.dismiss()
            return
        if event.button.id == "profile-template":
            template_options = [(template["name"], key) for key, template in PERSONA_TEMPLATES.items()]
            await self.app.push_screen(
                OptionPickerScreen(
                    title="选择人格模板",
                    subtitle="每个模板都会影响默认人格描述与策略摘要",
                    options=template_options,
                    current_value=self._selected_template,
                ),
                callback=self._apply_template_choice,
            )
            return
        if event.button.id != "profile-create-submit":
            return

        player_id = self.query_one("#profile-id", Input).value.strip()
        name = self.query_one("#profile-name", Input).value.strip() or player_id
        template_key = self._selected_template
        custom_persona = None
        if self.query_one("#profile-customize", Checkbox).value:
            custom_persona = self.query_one("#profile-persona", TextArea).text.strip() or None

        if not player_id or not player_id.isalnum():
            self.set_status("角色标识只能是字母和数字，且不能为空", "red")
            return
        if (PLAYERS_DIR / player_id).exists():
            self.set_status(f"角色 {player_id} 已存在", "red")
            return

        try:
            create_profile(player_id, name, template_key, custom_persona)
        except Exception as exc:
            self.set_status(f"创建失败: {exc}", "red")
            return

        self.browser._refresh_profiles()
        self.set_status(f"角色 {name} 已创建", "green")
        self.dismiss()

    def _apply_template_choice(self, value: str | None) -> None:
        if value is None:
            return
        self._selected_template = value
        self._refresh_summary()


class AddAsciiScreen(BaseScreen):
    TITLE = "添加 ASCII 形象"
    SUBTITLE = "从图片生成终端可显示的字符画"
    BORDER_STYLE = "bright_yellow"

    def __init__(self, browser: ProfileBrowserScreen):
        super().__init__()
        self.browser = browser
        profiles = list_profiles()
        self._profile_options = [(profile["name"], profile["id"]) for profile in profiles]
        self._selected_profile = self._profile_options[0][1] if self._profile_options else ""

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="form-pane"):
                yield Button("目标角色: 未选择", id="ascii-profile", classes="picker-button")
                yield Input(placeholder="图片路径", id="ascii-path")
                yield Input(value="60", placeholder="输出宽度", id="ascii-width")
            yield Static(classes="detail-pane", id="ascii-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("生成 ASCII", id="ascii-submit", variant="primary")
            yield Button("返回角色列表", id="ascii-back")

    def on_mount(self) -> None:
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        player_id = self._selected_profile
        display_name = next((label for label, value in self._profile_options if value == player_id), player_id or "未选择")
        self.query_one("#ascii-profile", Button).label = f"目标角色: {display_name}"
        path_text = self.query_one("#ascii-path", Input).value or "(待填写)"
        width_text = self.query_one("#ascii-width", Input).value or "60"
        output_path = PLAYERS_DIR / player_id / "ascii.txt" if player_id else Path("configs/players/<player>/ascii.txt")
        self.query_one("#ascii-summary", Static).update(
            _render_form_summary(
                "生成计划",
                [
                    ("目标角色", player_id or "(暂无角色)"),
                    ("图片路径", path_text),
                    ("输出宽度", width_text),
                    ("输出文件", str(output_path)),
                ],
                border_style="bright_yellow",
            )
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"ascii-path", "ascii-width"}:
            self._refresh_summary()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ascii-back":
            self.browser._refresh_profiles()
            self.dismiss()
            return
        if event.button.id == "ascii-profile":
            if not self._profile_options:
                self.set_status("当前没有可用角色", "red")
                return
            await self.app.push_screen(
                OptionPickerScreen(
                    title="选择目标角色",
                    subtitle="ASCII 形象会写入对应角色目录下的 ascii.txt",
                    options=self._profile_options,
                    current_value=self._selected_profile,
                ),
                callback=self._apply_ascii_profile,
            )
            return
        if event.button.id != "ascii-submit":
            return

        player_id = self._selected_profile
        image_path = Path(self.query_one("#ascii-path", Input).value.strip())
        width_text = self.query_one("#ascii-width", Input).value or "60"
        if not player_id:
            self.set_status("当前没有可用角色", "red")
            return
        if not image_path.exists():
            self.set_status(f"图片不存在: {image_path}", "red")
            return
        try:
            width = int(width_text)
        except ValueError:
            self.set_status("输出宽度必须是数字", "red")
            return

        from scripts.ascii_converter import image_to_unicode_art_halfblock

        output_path = PLAYERS_DIR / player_id / "ascii.txt"
        try:
            image_to_unicode_art_halfblock(image_path, output_path, width)
        except Exception as exc:
            self.set_status(f"生成失败: {exc}", "red")
            return

        self.browser._refresh_profiles()
        self.set_status(f"ASCII 形象已写入 {output_path}", "green")
        self.dismiss()

    def _apply_ascii_profile(self, value: str | None) -> None:
        if value is None:
            return
        self._selected_profile = value
        self._refresh_summary()


def _runtime_options() -> dict[str, object]:
    defaults: dict[str, object] = {
        "request_delay_seconds": 0.5,
        "max_history_rounds": 10,
        "clear_history_per_hand": False,
        "enable_conversation_logging": False,
    }
    if not KERNEL_CONFIG_PATH.exists():
        return defaults
    return load_runtime_options(KERNEL_CONFIG_PATH)
