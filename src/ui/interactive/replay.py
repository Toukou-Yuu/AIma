"""牌谱回放."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from . import menu

console = Console()

REPLAY_DIR = Path("logs/replay")


def run() -> None:
    """运行牌谱回放菜单."""
    replays = _list_replays()

    if not replays:
        console.print("[dim]暂无牌谱记录[/dim]")
        menu.press_any_key()
        return

    labels = [(f"📄 {label}", path) for label, path in replays]
    choice = menu.show_replay_menu(labels)

    if choice == "back" or choice is None:
        return

    _play_replay(choice)


def _list_replays() -> list[tuple[str, Path]]:
    """列出牌谱文件."""
    if not REPLAY_DIR.exists():
        return []

    replays = sorted(
        REPLAY_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:20]  # 最近20个

    result = []
    for r in replays:
        try:
            data = json.loads(r.read_text(encoding="utf-8"))
            timestamp = data.get("timestamp", "")
            if isinstance(timestamp, str) and timestamp:
                label = f"{r.stem} ({timestamp[:16]})"
            else:
                label = r.stem
        except Exception:
            label = r.stem
        result.append((label, r))

    return result


def _play_replay(replay_path: str) -> None:
    """播放牌谱."""
    delay = menu.input_number("回放延迟(秒):", default="0.5")

    cmd = f'python -m llm --replay "{replay_path}" --watch --watch-delay {delay}'

    console.print()
    console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))

    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        pass

    menu.press_any_key()
