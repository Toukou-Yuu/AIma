"""主菜单首页。"""

from __future__ import annotations

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
from ui.interactive.data import HomeSnapshot, ReplaySummary, build_home_snapshot
from ui.interactive.framework import MenuPage, is_back

console = Console()

_MAIN_ACTIONS = (
    ActionOption("quick", "demo演示", "无需 API Key，直接观看一场 dry-run 对局"),
    ActionOption("match", "开始对局", "选择四位玩家、局数与观战方式"),
    ActionOption("profile", "角色管理", "查看角色卡片、创建新角色、补充 ASCII 形象"),
    ActionOption("replay", "牌谱回放", "浏览最近牌谱并进入回放详情"),
    ActionOption("quit", "退出", "返回终端"),
)


def _bool_text(enabled: bool, positive: str, negative: str) -> Text:
    """渲染布尔状态。"""
    label = positive if enabled else negative
    style = "green" if enabled else "yellow"
    return Text(label, style=style)


def _render_recent_replays_panel(replays: tuple[ReplaySummary, ...]) -> Panel:
    """渲染最近牌谱摘要。"""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_white", width=12, no_wrap=True)
    table.add_column(width=10, no_wrap=True)
    table.add_column()

    for replay in replays:
        table.add_row(
            replay.time_label,
            Text(replay.status_label, style="cyan" if replay.ranking_by_seat else "yellow"),
            Text(
                f"{replay.reason_label} · {replay.action_count} 动作 · "
                f"{replay.stem}",
                style="white",
            ),
        )

    return Panel(
        table,
        title="[bold bright_magenta]最近牌谱[/]",
        border_style="bright_magenta",
        padding=(0, 1),
    )


class MainMenuPage(MenuPage):
    """Hub 型主菜单。"""

    title = "AIma 麻将 AI 终端"
    subtitle = "四人 AI 对局、角色管理与牌谱观战"
    allow_back = False
    header_width = 74

    def _render_content(self) -> str | object | None:
        snapshot = build_home_snapshot()
        self._render_dashboard(snapshot)
        console.print()
        console.print(render_action_catalog("主操作", _MAIN_ACTIONS, border_style="bright_green"))
        console.print(render_status_bar("方向键选择操作 | Enter 确认"))
        console.print()
        return super()._render_content()

    def _render_dashboard(self, snapshot: HomeSnapshot) -> None:
        """渲染首页信息总览。"""
        binding_summary = self._format_model_binding_summary(snapshot)
        model_rows = [
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
        model_panel = render_summary_panel("当前模型", model_rows, border_style="bright_cyan")

        roster_rows = [
            (
                entry.seat_label,
                Text(f"{entry.display_name} · {entry.mode_label}", style="white"),
            )
            for entry in snapshot.roster
        ]
        roster_panel = render_summary_panel("默认阵容", roster_rows, border_style="bright_blue")

        console.print(Columns([model_panel, roster_panel], expand=True, equal=True))

        if snapshot.recent_replays:
            console.print(_render_recent_replays_panel(snapshot.recent_replays))
        else:
            console.print(
                render_empty_state(
                    "暂无牌谱",
                    "还没有可回放的对局记录。",
                    hint="先运行一场 demo 演示或正式对局，首页就会显示最近牌谱。",
                ),
            )

    def _format_model_binding_summary(self, snapshot: HomeSnapshot) -> str:
        groups: dict[str, list[str]] = {}
        for binding in snapshot.model.seat_bindings:
            groups.setdefault(binding.profile_name, []).append(f"S{binding.seat}")
        if not groups:
            return "未绑定"
        return " · ".join(
            f"{'/'.join(seats)} {profile}"
            for profile, seats in groups.items()
        )

    def _get_instruction(self) -> str:
        return "[↑↓选择主页操作，回车确认]"

    def _get_choices(self):
        import questionary

        return [
            questionary.Choice(option.label, value=option.value)
            for option in _MAIN_ACTIONS
        ]


def show_main_menu() -> str:
    """显示主菜单。"""
    result = MainMenuPage().run()
    if is_back(result):
        return "quit"
    return result or "quit"
