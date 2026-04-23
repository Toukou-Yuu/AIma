"""Match setup, live view, control, and settlement screens."""

from __future__ import annotations

from dataclasses import replace

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.timer import Timer
from textual.widgets import Button, Checkbox, Input, Static

from llm.config import MatchEndCondition
from ui.interactive.chrome import render_empty_state
from ui.interactive.data import SEAT_LABELS, load_model_summary, load_replay_summary
from ui.interactive.formatting import format_timestamp
from ui.interactive.match_session import (
    MatchSession,
    MatchSessionConfig,
    create_session_stem,
    load_runtime_options,
)
from ui.interactive.screens.base import BaseScreen, OptionPickerScreen
from ui.interactive.screens.panels import (
    render_form_summary,
    render_match_config_panel,
    render_match_live_status_bar,
    render_match_log_panel,
    render_match_overview_panel,
    render_match_runtime_panel,
    render_match_standings_panel,
)
from ui.interactive.token_usage import render_token_summary_panel
from ui.interactive.utils import KERNEL_CONFIG_PATH, list_profiles
from ui.interactive.view_models import (
    MatchSetupDraft,
    build_match_setup_rows,
    player_display_name,
    selected_players_from_ids,
)


class QuickStartScreen(BaseScreen):
    TITLE = "demo演示"
    SUBTITLE = "dry-run 单局动态观战"
    BORDER_STYLE = "bright_green"

    def compose(self) -> ComposeResult:
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
            render_form_summary("当前配置", rows, border_style="bright_green")
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
            llm_runtime=_runtime_options(),
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
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with VerticalScroll(classes="form-pane", id="match-form-pane"):
                yield Static(Text("玩家配置", style="bold bright_yellow"), classes="section-title")
                for seat, label in enumerate(SEAT_LABELS):
                    yield Button(
                        f"{label}: 默认 AI (dry-run)",
                        id=f"match-seat-{seat}",
                        classes="picker-button",
                    )
                yield Static(Text("运行参数", style="bold bright_yellow"), classes="section-title")
                yield Input(
                    value="",
                    placeholder="随机种子：留空或填 0 表示每次随机生成一场新对局",
                    id="match-seed",
                )
                yield Input(
                    value="",
                    placeholder="目标局数：留空默认 8，4=东风战，8=半庄战",
                    id="match-hands",
                )
                yield Checkbox("实时观战", value=True, id="match-watch")
                yield Input(
                    value="",
                    placeholder="观战延迟：留空默认 0.5 秒，控制每个动作之间暂停多久",
                    id="match-delay",
                )
            yield Static(classes="detail-pane", id="match-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("开始对局", id="match-start", variant="primary")
            yield Button("返回首页", id="match-home")

    def on_mount(self) -> None:
        self._refresh_summary()
        self.query_one("#match-start", Button).focus()

    def _current_draft(self) -> MatchSetupDraft:
        return MatchSetupDraft(
            selected_player_ids=tuple(self._selected_player_ids),
            seed=self.query_one("#match-seed", Input).value or "0",
            max_hands=self.query_one("#match-hands", Input).value or "8",
            watch=self.query_one("#match-watch", Checkbox).value,
            delay=self.query_one("#match-delay", Input).value or "0.5",
        )

    def _refresh_player_buttons(self) -> None:
        for seat, player_id in enumerate(self._selected_player_ids):
            button = self.query_one(f"#match-seat-{seat}", Button)
            name = player_display_name(player_id, self._profile_options)
            button.label = f"{SEAT_LABELS[seat]}: {name}"

    def _refresh_summary(self) -> None:
        self._refresh_player_buttons()
        draft = self._current_draft()
        model_summary = load_model_summary(KERNEL_CONFIG_PATH)
        rows = build_match_setup_rows(
            draft,
            player_options=self._profile_options,
            model_summary=model_summary,
        )
        self.query_one("#match-summary", Static).update(
            render_form_summary("当前对局计划", rows, border_style="bright_yellow")
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
        players = selected_players_from_ids(self._selected_player_ids)
        uses_llm = any(player["id"] != "default" for player in players)
        model_summary = load_model_summary(KERNEL_CONFIG_PATH)
        if uses_llm and not model_summary.configured:
            self.set_status(f"LLM 配置不可用：{model_summary.note}", "red")
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
            llm_runtime=runtime_options,
            players=players,
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
        with Vertical(id="screen-body"):
            yield Static(classes="pane", id="match-live-status")
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
        self.query_one("#match-live-status", Static).update(
            render_match_live_status_bar(self.session)
        )
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
        self.query_one("#match-control-runtime", Static).update(
            render_match_runtime_panel(self.session)
        )
        self.query_one("#match-control-config", Static).update(
            render_match_config_panel(self.session)
        )
        result = self.session.result
        if result is not None:
            self.query_one("#match-control-extra", Static).update(render_match_log_panel(result))
        else:
            snapshot = self.session.snapshot
            self.query_one("#match-control-extra", Static).update(
                render_form_summary(
                    "后台状态",
                    [
                        ("最近动作", snapshot.action_label),
                        ("最新阶段", snapshot.phase_label),
                        ("开始时间", format_timestamp(self.session.started_at)),
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
        with Vertical(id="screen-body"):
            with Horizontal(classes="pane-row"):
                yield Static(classes="pane", id="settlement-overview")
                yield Static(classes="pane", id="settlement-logs")
            yield Static(classes="pane", id="settlement-token")
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
            render_match_overview_panel(self.session, result)
        )
        self.query_one("#settlement-logs", Static).update(render_match_log_panel(result))
        token_diagnostics = result.run_result.token_diagnostics if result.run_result else ()
        self.query_one("#settlement-token", Static).update(
            render_token_summary_panel(token_diagnostics)
        )
        self.query_one("#settlement-standings", Static).update(
            render_match_standings_panel(result)
        )

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
            from ui.interactive.screens.replay import ReplayDetailScreen

            summary = load_replay_summary(result.logs.replay_path)
            await self.app.push_screen(ReplayDetailScreen(summary))


def _runtime_options():
    return load_runtime_options(KERNEL_CONFIG_PATH)

