"""对局设置与启动."""

from __future__ import annotations

import subprocess
import sys

from rich.console import Console
from rich.panel import Panel

from . import menu
from .utils import KERNEL_CONFIG_PATH, list_profiles

console = Console()

SEATS = ["东家 (0)", "南家 (1)", "西家 (2)", "北家 (3)"]


def run() -> None:
    """运行对局设置."""
    profiles = list_profiles()

    # 确保至少有4个选项
    while len(profiles) < 4:
        profiles.append({"id": "default", "name": "默认 AI"})

    console.print()
    console.print(Panel("开始对局", border_style="bright_yellow"))

    # 选择4个玩家
    selected = []
    for seat_name in SEATS:
        choice = menu.select_player_for_seat(seat_name, profiles)
        if choice is None:
            return  # 取消
        selected.append(choice)

    # 对局设置
    settings = _configure_settings()
    if settings is None:
        return

    # 构建并执行命令
    cmd = _build_command(selected, settings)
    if cmd is None:
        return

    _execute_command(cmd, settings["watch"])


def _configure_settings() -> dict | None:
    """配置对局设置."""
    console.print()
    console.print("[dim]对局设置 (直接回车使用默认值)[/dim]")

    seed = menu.input_number("随机种子 (0=随机):", default="0")
    max_steps = menu.input_number("最大步数:", default="500")
    watch = menu.confirm("实时观战?", default=True)

    delay = "0.5"
    if watch:
        delay = menu.input_number("观战延迟(秒):", default="0.5")

    return {
        "seed": seed,
        "max_steps": max_steps,
        "watch": watch,
        "delay": delay,
    }


def _build_command(selected: list[str], settings: dict) -> str | None:
    """构建执行命令."""
    player_str = ",".join(selected)
    cmd_parts = [
        "python -m llm",
        f"--players {player_str}",
        f"--seed {settings['seed']}",
        f"--max-player-steps {settings['max_steps']}",
    ]

    if settings["watch"]:
        cmd_parts.append("--watch")
        cmd_parts.append(f"--watch-delay {settings['delay']}")

    # 检查是否需要 API Key
    has_llm = any(s != "default" for s in selected)
    if has_llm and not KERNEL_CONFIG_PATH.exists():
        console.print()
        console.print("[yellow]⚠️  使用了 LLM 玩家，但未找到内核配置[/yellow]")
        console.print(f"  请创建 {KERNEL_CONFIG_PATH}")
        console.print("  或使用 --dry-run 模式")

        use_dry = menu.confirm("是否切换到 Dry-run 模式?", default=True)
        if use_dry:
            cmd_parts = [
                "python -m llm",
                "--dry-run",
                f"--seed {settings['seed']}",
                f"--max-player-steps {settings['max_steps']}",
            ]
            if settings["watch"]:
                cmd_parts.append("--watch")
                cmd_parts.append(f"--watch-delay {settings['delay']}")
        else:
            return None

    cmd = " ".join(cmd_parts)

    console.print()
    console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))

    if not menu.confirm("确认开始?", default=True):
        return None

    return cmd


def _execute_command(cmd: str, watch: bool) -> None:
    """执行命令."""
    console.print()
    console.print("[bold green]🚀 启动对局...[/bold green]")
    if watch:
        console.print("[dim]💡 提示: 观战中按 Ctrl+C 可随时退出返回菜单[/dim]")
    console.print()

    try:
        # 使用 DEVNULL 隐藏子进程的报错输出
        subprocess.run(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL if watch else None,
        )
        console.print("\n[dim]✓ 对局已结束[/dim]")
    except KeyboardInterrupt:
        console.print("\n")
        console.print(Panel(
            "[yellow]对局已中断[/yellow]\n"
            "[dim]日志已保存到 logs/ 目录[/dim]",
            border_style="yellow",
            padding=(1, 2),
        ))

    menu.press_any_key()


def quick_start() -> None:
    """快速开始 - Dry-run 演示."""
    console.print()
    console.print(Panel("🎮 快速开始 (Dry-run 演示)", border_style="bright_green"))

    seed = menu.input_number("随机种子 (0=随机):", default="42")
    watch = menu.confirm("实时观战?", default=True)

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
        subprocess.run(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL if watch else None,
        )
        console.print("\n[dim]✓ 对局已结束[/dim]")
    except KeyboardInterrupt:
        console.print("\n")
        console.print(Panel(
            "[yellow]对局已中断[/yellow]\n"
            "[dim]日志已保存到 logs/simple/quick.txt 和 logs/replay/quick.json[/dim]",
            border_style="yellow",
            padding=(1, 2),
        ))

    menu.press_any_key()

