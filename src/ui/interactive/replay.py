"""牌谱回放浏览与详情页面。"""

from __future__ import annotations

from dataclasses import dataclass

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.interactive.chrome import (
    ActionOption,
    render_action_catalog,
    render_empty_state,
    render_status_bar,
    render_summary_panel,
)
from ui.interactive.data import ReplaySummary, load_recent_replay_summaries
from ui.interactive.framework import BACK, MenuPage, Page, Prompt, is_back
from ui.interactive.session_runner import run_llm_session

console = Console()


def _render_replay_table(replays: tuple[ReplaySummary, ...]) -> Panel:
    """渲染牌谱列表。"""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_white", width=12, no_wrap=True)
    table.add_column(width=10, no_wrap=True)
    table.add_column(width=12, no_wrap=True)
    table.add_column()

    for replay in replays:
        seed_label = f"seed {replay.seed}" if replay.seed is not None else "seed ?"
        table.add_row(
            replay.time_label,
            Text(replay.status_label, style="cyan" if replay.ranking_by_seat else "yellow"),
            Text(seed_label, style="dim"),
            Text(
                f"{replay.reason_label} · {replay.action_count} 动作 · {replay.stem}",
                style="white",
            ),
        )

    return Panel(
        table,
        title="[bold bright_magenta]最近 20 场牌谱[/]",
        border_style="bright_magenta",
        padding=(0, 1),
    )


@dataclass
class ReplayPlaybackConfig:
    """回放配置。"""

    delay: str = "0.5"


class ReplayMenuPage(MenuPage):
    """牌谱回放菜单。"""

    title = "牌谱回放"
    subtitle = "先浏览摘要，再进入回放详情"
    header_width = 74

    def __init__(self) -> None:
        self._replays = load_recent_replay_summaries(limit=20)

    def _get_choices(self):
        import questionary

        return [
            questionary.Choice(replay.menu_label, value=replay)
            for replay in self._replays
        ]

    def _render_content(self) -> ReplaySummary | object | None:
        choices = self._get_choices()
        if not choices:
            console.print(
                render_empty_state(
                    "暂无牌谱",
                    "还没有可回放的牌谱记录。",
                    hint="完成一场 demo 演示或正式对局后，这里会自动显示最新牌谱。",
                ),
            )
            Prompt.press_any_key()
            return BACK

        console.print(_render_replay_table(self._replays))
        console.print(render_status_bar("选择一场牌谱进入详情页"))
        console.print()
        return super()._render_content()


class ReplayDetailMenuPage(MenuPage):
    """牌谱详情菜单。"""

    title = "回放详情"
    border_style = "bright_magenta"
    header_width = 74

    def __init__(self, replay: ReplaySummary, config: ReplayPlaybackConfig):
        self.replay = replay
        self.config = config
        self.subtitle = replay.stem

    def _render_content(self) -> str | object | None:
        console.print(self._render_overview())
        console.print()
        console.print(self._render_actions())
        console.print(render_status_bar("选择操作后继续"))
        console.print()
        return super()._render_content()

    def _render_overview(self) -> Columns:
        """渲染回放详情总览。"""
        basic_rows = [
            ("记录时间", self.replay.time_label),
            ("seed", str(self.replay.seed) if self.replay.seed is not None else "未记录"),
            ("结束状态", self.replay.status_label),
            ("结束原因", self.replay.reason_label),
            ("终局阶段", self.replay.final_phase),
            ("动作数", str(self.replay.action_count)),
        ]
        result_rows = [
            ("名次", self.replay.ranking_label),
            ("分数", self.replay.score_label),
            ("回放速度", f"{self.config.delay} 秒 / 步"),
        ]
        return Columns(
            [
                render_summary_panel("牌谱概览", basic_rows, border_style="bright_cyan"),
                render_summary_panel("终局结果", result_rows, border_style="bright_blue"),
            ],
            expand=True,
            equal=True,
        )

    def _render_actions(self) -> Panel:
        actions = (
            ActionOption("start", "开始回放", "进入动态观战回放"),
            ActionOption("delay", "调整速度", f"当前 {self.config.delay} 秒 / 步"),
        )
        return render_action_catalog("可执行操作", actions, border_style="bright_green")

    def _get_choices(self):
        import questionary

        return [
            questionary.Choice("开始回放", value="start"),
            questionary.Choice(f"调整速度: {self.config.delay} 秒 / 步", value="delay"),
        ]


class ReplayDetailPage(Page):
    """牌谱详情控制器。"""

    allow_back = True

    def __init__(self, replay: ReplaySummary):
        self.replay = replay
        self.config = ReplayPlaybackConfig()

    def _render_content(self) -> None:
        while True:
            action = ReplayDetailMenuPage(self.replay, self.config).run()
            if is_back(action):
                return BACK
            if action == "delay":
                delay = Prompt.number("输入回放延迟(秒):", default=self.config.delay)
                if is_back(delay):
                    continue
                self.config.delay = delay
                continue
            if action == "start":
                self._run_replay()
                continue

    def _run_replay(self) -> None:
        """执行牌谱回放。"""
        cli_args = [
            "--replay",
            str(self.replay.path),
            "--watch",
            "--watch-delay",
            self.config.delay,
        ]
        result = run_llm_session(cli_args)
        console.print()
        Prompt.press_any_key("回放结束，按返回回到详情页...")


def run() -> None:
    """运行牌谱回放。"""
    replay = ReplayMenuPage().run()
    if replay is None or is_back(replay):
        return
    ReplayDetailPage(replay).run()
