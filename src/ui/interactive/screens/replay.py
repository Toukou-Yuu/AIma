"""Replay browsing, detail, and live playback screens."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ui.interactive.chrome import render_empty_state
from ui.interactive.data import ReplaySummary, load_recent_replay_summaries
from ui.interactive.replay_session import ReplaySession, ReplaySessionConfig
from ui.interactive.screens.base import BaseScreen
from ui.interactive.screens.panels import (
    render_form_summary,
    render_replay_live_status_bar,
    render_replay_summary_panel,
)

_WATCH_SPEEDS = (0.1, 0.3, 0.5, 1.0)


class ReplayBrowserScreen(BaseScreen):
    TITLE = "牌谱回放"
    SUBTITLE = "先浏览牌谱摘要，再进入动态回放"
    BORDER_STYLE = "bright_magenta"

    def __init__(self) -> None:
        super().__init__()
        self._replays: tuple[ReplaySummary, ...] = ()

    def compose(self) -> ComposeResult:
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
                render_replay_summary_panel(summary, 0.5),
                render_form_summary(
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
            render_replay_summary_panel(self.summary, self.delay_seconds)
        )
        self.query_one("#replay-detail-side", Static).update(
            render_form_summary(
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
        with Vertical(id="screen-body"):
            yield Static(classes="pane", id="replay-live-status")
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
        self.query_one("#replay-live-status", Static).update(
            render_replay_live_status_bar(self.session)
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


def _float_choice(current: float, step: int) -> float:
    try:
        index = _WATCH_SPEEDS.index(round(current, 1))
    except ValueError:
        return _WATCH_SPEEDS[0]
    next_index = min(max(index + step, 0), len(_WATCH_SPEEDS) - 1)
    return _WATCH_SPEEDS[next_index]

