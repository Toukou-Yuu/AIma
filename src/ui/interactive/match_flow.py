"""交互式对局会话页面流。"""

from __future__ import annotations

from dataclasses import replace

import questionary
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
from ui.interactive.data import SEAT_LABELS, load_replay_summary
from ui.interactive.formatting import format_duration, format_timestamp
from ui.interactive.framework import Page, Prompt
from ui.interactive.match_session import (
    MatchSession,
    MatchSessionConfig,
    MatchSessionResult,
    MatchSessionState,
    create_session_stem,
)
from ui.interactive.replay import ReplayDetailPage
from ui.interactive.token_usage import render_token_summary_panel

console = Console()


def _session_status_text(session: MatchSession) -> tuple[str, str]:
    """返回状态标签与颜色。"""
    state = session.state
    if state == MatchSessionState.RUNNING:
        return ("运行中", "green")
    if state == MatchSessionState.FINISHED:
        return ("已完成", "cyan")
    if state == MatchSessionState.FAILED:
        return ("失败", "red")
    return ("等待启动", "yellow")


def _render_runtime_panel(session: MatchSession) -> Panel:
    """渲染会话运行摘要。"""
    snapshot = session.snapshot
    status_label, status_style = _session_status_text(session)
    rows = [
        ("状态", Text(status_label, style=status_style)),
        ("开始时间", format_timestamp(session.started_at)),
        ("最近动作", snapshot.action_label),
        ("最新阶段", snapshot.phase_label),
        ("快照步数", str(snapshot.callback_steps)),
    ]
    return render_summary_panel("对局状态", rows, border_style="bright_cyan")


def _render_config_panel(session: MatchSession) -> Panel:
    """渲染对局配置摘要。"""
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


def _render_log_panel(result: MatchSessionResult) -> Panel:
    """渲染日志路径。"""
    rows = [
        ("牌谱日志", str(result.logs.replay_path)),
        ("调试日志", str(result.logs.debug_path)),
        ("可读日志", str(result.logs.simple_path)),
    ]
    return render_summary_panel("日志记录", rows, border_style="bright_magenta")


def _render_standings_panel(result: MatchSessionResult) -> Panel:
    """渲染结算表。"""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_white", width=8, no_wrap=True)
    table.add_column(width=16, no_wrap=True)
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
        for idx, seat in enumerate(ranking, start=1):
            player_name = result.player_names.get(seat, f"S{seat}")
            table.add_row(f"{idx} 位", f"{SEAT_LABELS[seat]} {player_name}", f"{scores[seat]:,}")

    return Panel(
        table,
        title="[bold bright_green]最终排名[/]",
        border_style="bright_green",
        padding=(0, 1),
    )


class MatchWatchPage(Page):
    """当前牌桌画面。"""

    allow_back = False
    border_style = "bright_green"
    header_width = 84

    def __init__(self, session: MatchSession):
        self.session = session
        self.title = f"{session.config.label}观战"
        self.subtitle = "离开观战后，对局会继续在后台运行"

    def _render_content(self) -> str:
        if self.session.is_finished:
            return "settlement"

        console.print(
            Columns(
                [_render_runtime_panel(self.session), _render_config_panel(self.session)],
                expand=True,
                equal=True,
            )
        )
        console.print()

        snapshot = self.session.snapshot
        if snapshot.panel is not None:
            console.print(snapshot.panel)
        else:
            console.print(
                render_empty_state(
                    "等待首帧",
                    "后台对局已启动，正在等待第一帧牌桌快照。",
                    hint="选择“刷新画面”可重新获取最新牌桌。",
                ),
            )

        console.print()
        console.print(
            render_action_catalog(
                "观战操作",
                (
                    ActionOption("refresh", "刷新画面", "重新读取最新牌桌快照"),
                    ActionOption("detach", "离开观战", "回到对局控制页，对局继续运行"),
                ),
                border_style="bright_green",
            )
        )
        console.print(render_status_bar("选择操作后继续"))
        console.print()
        return Prompt.select(
            "",
            choices=[
                questionary.Choice("刷新画面", value="refresh"),
                questionary.Choice("离开观战", value="detach"),
            ],
            allow_back=False,
            instruction="[↑↓选择操作，回车确认]",
        )


class MatchControlPage(Page):
    """对局后台控制页。"""

    allow_back = False
    border_style = "bright_yellow"
    header_width = 84

    def __init__(self, session: MatchSession):
        self.session = session
        self.title = f"{session.config.label}控制台"
        self.subtitle = "这里管理后台对局，不会中断当前会话"

    def _render_content(self) -> str:
        if self.session.is_finished:
            return "settlement"

        console.print(
            Columns(
                [_render_runtime_panel(self.session), _render_config_panel(self.session)],
                expand=True,
                equal=True,
            )
        )
        console.print()

        actions: list[ActionOption] = [
            ActionOption("refresh", "刷新状态", "重新读取后台会话状态"),
            ActionOption("wait", "等待结束", "留在当前页，直到对局自然结束"),
        ]
        if self.session.config.watch_enabled:
            actions.insert(0, ActionOption("watch", "进入观战", "查看最新牌桌画面"))

        console.print(render_action_catalog("控制操作", actions, border_style="bright_yellow"))
        console.print(render_status_bar("选择操作后继续"))
        console.print()

        choices = [questionary.Choice(option.label, value=option.value) for option in actions]
        action = Prompt.select(
            "",
            choices=choices,
            allow_back=False,
            instruction="[↑↓选择操作，回车确认]",
        )
        if action == "wait":
            with console.status("[bold green]对局进行中，等待自然结束...[/bold green]"):
                while not self.session.wait(0.2):
                    pass
            return "settlement"
        return action


class MatchSettlementPage(Page):
    """对局结算页。"""

    allow_back = False
    border_style = "bright_magenta"
    header_width = 84

    def __init__(self, session: MatchSession):
        self.session = session
        self.title = f"{session.config.label}结算"
        self.subtitle = "对局生命周期在这里结束，再决定下一步"

    def _render_content(self) -> str:
        result = self.session.result
        if result is None:
            console.print(render_empty_state("暂无结果", "后台会话尚未生成结果。"))
            Prompt.press_any_key()
            return "menu"

        console.print(self._render_overview(result))
        console.print()
        console.print(_render_standings_panel(result))
        console.print()
        token_diagnostics = result.run_result.token_diagnostics if result.run_result else ()
        console.print(render_token_summary_panel(token_diagnostics))
        console.print()
        console.print(_render_log_panel(result))
        console.print()

        while True:
            action = self._choose_action(result)
            if action == "replay":
                if result.logs.replay_path.exists():
                    ReplayDetailPage(load_replay_summary(result.logs.replay_path)).run()
                continue
            return action

    def _render_overview(self, result: MatchSessionResult) -> Columns:
        status_label, status_style = _session_status_text(self.session)
        run_result = result.run_result
        outcome_rows = [
            ("状态", Text(status_label, style=status_style)),
            ("开始时间", format_timestamp(self.session.started_at)),
            ("结束时间", format_timestamp(self.session.finished_at)),
            ("总耗时", format_duration(result.duration_seconds)),
            ("seed", str(self.session.config.seed)),
        ]
        if run_result is not None:
            outcome_rows.extend(
                [
                    ("结束原因", run_result.stopped_reason),
                    ("玩家步数", str(run_result.player_steps)),
                    ("内核步数", str(run_result.kernel_steps)),
                    ("终局阶段", run_result.final_state.phase.value),
                ]
            )
        else:
            outcome_rows.append(("错误信息", result.error_message or "未知错误"))

        next_rows = [
            ("模式", "Dry-run" if self.session.config.dry_run else "LLM 对局"),
            ("观战延迟", f"{self.session.config.watch_delay:.1f} 秒"),
            ("目标局数", str(self.session.config.target_hands)),
            ("牌谱可回放", "是" if result.logs.replay_path.exists() else "否"),
            ("日志 stem", result.logs.stem),
        ]
        return Columns(
            [
                render_summary_panel("对局结果", outcome_rows, border_style="bright_cyan"),
                render_summary_panel("会话信息", next_rows, border_style="bright_blue"),
            ],
            expand=True,
            equal=True,
        )

    def _choose_action(self, result: MatchSessionResult) -> str:
        actions: list[ActionOption] = []
        if result.logs.replay_path.exists():
            actions.append(ActionOption("replay", "回放这场对局", "进入牌谱详情并观看回放"))
        actions.extend(
            [
                ActionOption("restart", "再来一局", "用相同配置重新启动一场新对局"),
                ActionOption("menu", "返回主菜单", "结束当前会话流程"),
            ]
        )
        console.print(render_action_catalog("后续操作", actions, border_style="bright_green"))
        console.print(render_status_bar("选择操作后继续"))
        console.print()

        choices = [questionary.Choice(option.label, value=option.value) for option in actions]
        return Prompt.select(
            "",
            choices=choices,
            allow_back=False,
            instruction="[↑↓选择操作，回车确认]",
        )


def run_match_session_flow(config: MatchSessionConfig) -> None:
    """运行一场完整的交互式对局会话。"""
    active_config = config
    while True:
        session = MatchSession(active_config)
        session.start()

        current_view = "watch" if active_config.watch_enabled else "control"
        while not session.is_finished:
            if current_view == "watch":
                action = MatchWatchPage(session).run()
                if action == "detach":
                    current_view = "control"
            else:
                action = MatchControlPage(session).run()
                if action == "watch":
                    current_view = "watch"

        settlement_action = MatchSettlementPage(session).run()
        if settlement_action == "restart":
            active_config = replace(
                active_config,
                session_stem=create_session_stem(active_config.label),
            )
            continue
        return
