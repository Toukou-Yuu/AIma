"""Pure panel builders shared by Textual screens."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.interactive.chrome import render_summary_panel
from ui.interactive.data import SEAT_LABELS, ReplaySummary
from ui.interactive.formatting import format_duration, format_replay_speed, format_timestamp
from ui.interactive.match_session import MatchSession, MatchSessionResult, MatchSessionState
from ui.interactive.replay_session import ReplaySession, ReplaySessionResult, ReplaySessionState


def render_form_summary(
    title: str,
    rows: list[tuple[str, str | Text]],
    border_style: str = "bright_blue",
) -> Panel:
    return render_summary_panel(title, rows, border_style=border_style)


def render_match_runtime_panel(session: MatchSession) -> Panel:
    status_label, status_style = _match_status(session)
    snapshot = session.snapshot
    rows = [
        ("状态", Text(status_label, style=status_style)),
        ("开始时间", format_timestamp(session.started_at)),
        ("最近动作", snapshot.action_label),
        ("最新阶段", snapshot.phase_label),
        ("快照步数", str(snapshot.callback_steps)),
    ]
    return render_summary_panel("对局状态", rows, border_style="bright_cyan")


def render_match_config_panel(session: MatchSession) -> Panel:
    player_text = " / ".join(
        f"{SEAT_LABELS[seat]} {name}"
        for seat, name in sorted(session.player_names.items())
    )
    rows = [
        ("模式", "Dry-run" if session.config.dry_run else "LLM 对局"),
        ("seed", str(session.config.seed)),
        ("目标", session.config.target_label),
        ("玩家", player_text),
        ("日志 stem", session.logs.stem),
    ]
    return render_summary_panel("配置摘要", rows, border_style="bright_blue")


def render_match_log_panel(result: MatchSessionResult) -> Panel:
    rows = [
        ("牌谱日志", str(result.logs.replay_path)),
        ("调试日志", str(result.logs.debug_path)),
        ("可读日志", str(result.logs.simple_path)),
    ]
    return render_summary_panel("日志记录", rows, border_style="bright_magenta")


def render_match_standings_panel(result: MatchSessionResult) -> Panel:
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


def render_match_overview_panel(session: MatchSession, result: MatchSessionResult) -> Panel:
    rows = [
        ("状态", "正常完成" if result.succeeded else "执行失败"),
        (
            "结束原因",
            result.run_result.stopped_reason
            if result.run_result
            else (result.error_message or "unknown"),
        ),
        ("耗时", format_duration(result.duration_seconds)),
        ("seed", str(session.config.seed)),
        ("目标", session.config.target_label),
    ]
    if result.error_message:
        rows.append(("错误", Text(result.error_message, style="red")))
    return render_summary_panel("对局概览", rows, border_style="bright_cyan")


def render_replay_runtime_panel(session: ReplaySession) -> Panel:
    status_label, status_style = _replay_status(session)
    snapshot = session.snapshot
    rows = [
        ("状态", Text(status_label, style=status_style)),
        ("开始时间", format_timestamp(session.started_at)),
        ("当前步骤", f"{snapshot.current_step} / {snapshot.total_steps}"),
        ("最近动作", snapshot.action_label),
        ("当前阶段", snapshot.phase_label),
    ]
    return render_summary_panel("回放状态", rows, border_style="bright_cyan")


def render_replay_summary_panel(summary: ReplaySummary, delay_seconds: float) -> Panel:
    rows = [
        ("记录时间", summary.time_label),
        ("seed", str(summary.seed) if summary.seed is not None else "未记录"),
        ("结束状态", summary.status_label),
        ("结束原因", summary.reason_label),
        ("终局阶段", summary.final_phase),
        ("动作数", str(summary.action_count)),
        ("当前速度", format_replay_speed(delay_seconds)),
    ]
    return render_summary_panel("牌谱概览", rows, border_style="bright_blue")


def render_replay_result_panel(result: ReplaySessionResult, delay_seconds: float) -> Panel:
    rows = [
        ("状态", "正常完成" if result.succeeded else "执行失败"),
        ("耗时", format_duration(result.duration_seconds)),
        ("结束状态", result.summary.status_label),
        ("回放速度", format_replay_speed(delay_seconds)),
    ]
    if result.error_message:
        rows.append(("错误", Text(result.error_message, style="red")))
    return render_summary_panel("回放结果", rows, border_style="bright_magenta")


def render_replay_live_status_bar(session: ReplaySession) -> Panel:
    status_label, status_style = _replay_status(session)
    snapshot = session.snapshot
    line1 = Text.assemble(
        ("状态 ", "dim"),
        (status_label, status_style),
        (" | ", "dim"),
        ("步骤 ", "dim"),
        (f"{snapshot.current_step}/{snapshot.total_steps}", "cyan"),
        (" | ", "dim"),
        ("速度 ", "dim"),
        (format_replay_speed(session.config.delay_seconds), "yellow"),
        (" | ", "dim"),
        (snapshot.table_summary or "等待牌桌快照", "white"),
    )
    line2 = Text.assemble(
        ("当前阶段 ", "dim"),
        (snapshot.phase_label, "white"),
        (" | ", "dim"),
        ("最近动作 ", "dim"),
        (snapshot.action_label, "bold bright_white"),
    )
    return _render_live_status_bar(line1, line2, border_style="bright_green")


def _match_status(session: MatchSession) -> tuple[str, str]:
    if session.state == MatchSessionState.RUNNING:
        return ("运行中", "green")
    if session.state == MatchSessionState.FINISHED:
        return ("已完成", "cyan")
    if session.state == MatchSessionState.FAILED:
        return ("失败", "red")
    return ("等待启动", "yellow")


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


def _render_live_status_bar(
    line1: Text,
    line2: Text | None = None,
    *,
    border_style: str = "bright_cyan",
) -> Panel:
    content = Group(line1) if line2 is None else Group(line1, line2)
    return Panel(content, border_style=border_style, padding=(0, 1))
