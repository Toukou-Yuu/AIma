"""对局设置与启动 - 使用统一框架重构."""

from __future__ import annotations

import subprocess

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel

from ui.interactive.framework import MenuPage, Page, Prompt
from ui.interactive.utils import KERNEL_CONFIG_PATH, list_profiles

console = Console()

SEATS = ["东家 (0)", "南家 (1)", "西家 (2)", "北家 (3)"]


class SelectPlayerPage(Page):
    """选择玩家页."""

    def __init__(self, seat_name: str, profiles: list[dict]):
        self.seat_name = seat_name
        self.profiles = profiles
        self.title = f"选择 {seat_name}"

    def _render_content(self) -> str | None:
        import questionary
        from prompt_toolkit.styles import Style

        choices = [
            questionary.Choice("默认 AI (dry-run)", value="default"),
            questionary.Separator(),
        ]
        for p in self.profiles:
            choices.append(questionary.Choice(p['name'], value=p["id"]))

        style = Style.from_dict({
            "selected": "ansicyan bold",
            "highlighted": "ansicyan bold",
            "pointer": "ansicyan bold",
            "separator": "#666666",
            "instruction": "#555555",
        })

        return questionary.select(
            "",
            choices=choices,
            qmark="",
            pointer=">",
            instruction=f"[选择 {self.seat_name}]",
            style=style,
        ).ask()


class MatchSetupPage(Page):
    """对局设置页."""

    title = "开始对局"
    border_style = "bright_yellow"

    def _render_content(self) -> None:
        profiles = list_profiles()
        while len(profiles) < 4:
            profiles.append({"id": "default", "name": "默认 AI"})

        # 选择4个玩家
        selected = []
        for seat_name in SEATS:
            choice = SelectPlayerPage(seat_name, profiles).run()
            if choice is None:
                return
            selected.append(choice)

        # 对局设置
        settings = self._configure_settings()
        if settings is None:
            return

        # 构建并执行命令
        cmd = self._build_command(selected, settings)
        if cmd is None:
            return

        self._execute_command(cmd, settings["watch"])

    def _configure_settings(self) -> dict | None:
        """配置对局设置."""
        console.print()
        console.print("[dim]对局设置 (直接回车使用默认值)[/dim]")

        seed = Prompt.number("随机种子 (0=随机):", default="0")
        max_hands = Prompt.number("局数 (4=东风, 8=半庄):", default="8")
        watch = Prompt.confirm("实时观战?", default=True)

        delay = "0.5"
        if watch:
            delay = Prompt.number("观战延迟(秒):", default="0.5")

        return {
            "seed": seed,
            "max_hands": max_hands,
            "watch": watch,
            "delay": delay,
        }

    def _build_command(self, selected: list[str], settings: dict) -> str | None:
        """构建执行命令."""
        player_str = ",".join(selected)
        max_hands = settings.get('max_hands', 8)
        cmd_parts = [
            "python -m llm",
            f"--players {player_str}",
            f"--seed {settings['seed']}",
            f"--max-hands {max_hands}",
        ]

        if settings["watch"]:
            cmd_parts.append("--watch")
            cmd_parts.append(f"--watch-delay {settings['delay']}")

        # 添加日志参数（使用空字符串自动生成时间戳文件名）
        cmd_parts.append('--log-session ""')

        # 检查是否需要 API Key
        has_llm = any(s != "default" for s in selected)
        if has_llm and not KERNEL_CONFIG_PATH.exists():
            console.print()
            console.print("[yellow]⚠️  使用了 LLM 玩家，但未找到内核配置[/yellow]")
            console.print(f"  请创建 {KERNEL_CONFIG_PATH}")
            console.print("  或使用 --dry-run 模式")

            use_dry = Prompt.confirm("是否切换到 Dry-run 模式?", default=True)
            if use_dry:
                cmd_parts = [
                    "python -m llm",
                    "--dry-run",
                    f"--seed {settings['seed']}",
                ]
                if settings["watch"]:
                    cmd_parts.append("--watch")
                    cmd_parts.append(f"--watch-delay {settings['delay']}")
            else:
                return None

        cmd = " ".join(cmd_parts)

        console.print()
        console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))

        if not Prompt.confirm("确认开始?", default=True):
            return None

        return cmd

    def _execute_command(self, cmd: str, watch: bool) -> None:
        """执行命令."""
        console.print()
        console.print("[bold green]🚀 启动对局...[/bold green]")
        if watch:
            console.print("[dim]💡 提示: 观战中按 Ctrl+C 可随时退出返回菜单[/dim]")
        console.print()

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                stderr=subprocess.DEVNULL if watch else None,
            )
            if result.returncode != 0:
                console.print(f"\n[red]✗ 对局执行失败 (返回码: {result.returncode})[/red]")
                console.print("[dim]请检查配置和依赖是否正确安装[/dim]")
                Prompt.press_any_key()
                return
            console.print("\n[dim]✓ 对局已结束[/dim]")
            # 终局暂停
            console.print()
            Prompt.press_any_key("终局牌桌已保留，按任意键返回菜单...")
        except KeyboardInterrupt:
            console.print("\n")
            console.print(Panel(
                "[yellow]对局已中断[/yellow]\n"
                "[dim]日志已保存到 logs/ 目录[/dim]",
                border_style="yellow",
                padding=(1, 2),
            ))
            Prompt.press_any_key()


def run() -> None:
    """运行对局设置."""
    MatchSetupPage().run()


class QuickStartPage(Page):
    """快速开始页."""

    title = "demo演示"
    border_style = "bright_green"

    def _render_content(self) -> None:
        seed = Prompt.number("随机种子 (0=随机):", default="42")
        watch = Prompt.confirm("实时观战?", default=True)

        cmd_parts = [
            "python -m llm",
            "--dry-run",
            f"--seed {seed}",
            "--log-session quick",
        ]

        if watch:
            cmd_parts.append("--watch")
            cmd_parts.append("--watch-delay 0.3")

        cmd = " ".join(cmd_parts)

        console.print()
        console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))
        console.print("[dim]💡 提示: 观战中按 Ctrl+C 可随时退出返回菜单[/dim]")

        try:
            if watch:
                # 观战模式：不捕获输出，让 Rich 界面正常显示
                result = subprocess.run(cmd, shell=True)
                # 130 是用户按 Ctrl+C 中断的标准退出码
                if result.returncode == 130 or result.returncode == -1073741510:
                    # 用户主动中断，不显示错误
                    console.print("\n")
                    console.print(Panel(
                        "[yellow]对局已中断[/yellow]\n"
                        "[dim]日志已保存到 logs/simple/quick.txt 和 logs/replay/quick.json[/dim]",
                        border_style="yellow",
                        padding=(1, 2),
                    ))
                    Prompt.press_any_key()
                    self._clear_screen()  # 清屏避免残留
                    return
                if result.returncode != 0:
                    console.print(f"\n[red]✗ 对局执行失败 (返回码: {result.returncode})[/red]")
                    Prompt.press_any_key()
                    self._clear_screen()  # 清屏避免残留
                    return
            else:
                # 非观战模式：捕获输出用于调试
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                # 130 是用户按 Ctrl+C 中断的标准退出码，Windows 可能是 -1073741510
                if result.returncode == 130 or result.returncode == -1073741510:
                    console.print("\n")
                    console.print(Panel(
                        "[yellow]对局已中断[/yellow]\n"
                        "[dim]日志已保存到 logs/simple/quick.txt 和 logs/replay/quick.json[/dim]",
                        border_style="yellow",
                        padding=(1, 2),
                    ))
                    Prompt.press_any_key()
                    self._clear_screen()  # 清屏避免残留
                    return
                if result.returncode != 0:
                    console.print(f"\n[red]✗ 对局执行失败 (返回码: {result.returncode})[/red]")
                    if result.stderr:
                        console.print("[dim]错误信息:[/dim]")
                        error_text = result.stderr[:2000]
                        console.print(f"[red]{error_text}[/red]")
                    Prompt.press_any_key()
                    self._clear_screen()  # 清屏避免残留
                    return
            console.print("\n[dim]✓ 对局已结束[/dim]")
            # 终局暂停
            console.print()
            Prompt.press_any_key("终局牌桌已保留，按任意键返回菜单...")
            self._clear_screen()  # 清屏避免残留
        except KeyboardInterrupt:
            console.print("\n")
            console.print(Panel(
                "[yellow]对局已中断[/yellow]\n"
                "[dim]日志已保存到 logs/simple/quick.txt 和 logs/replay/quick.json[/dim]",
                border_style="yellow",
                padding=(1, 2),
            ))
            Prompt.press_any_key()
            self._clear_screen()  # 清屏避免残留


def quick_start() -> None:
    """快速开始."""
    QuickStartPage().run()
