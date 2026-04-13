"""牌谱回放 - 使用统一框架重构."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rich.console import Console

from ui.interactive.framework import BACK, MenuPage, Page, Prompt, is_back

console = Console()

REPLAY_DIR = Path("logs/replay")


class ReplayMenuPage(MenuPage):
    """牌谱回放菜单."""

    title = "牌谱回放"

    def _get_choices(self):
        import questionary
        replays = self._list_replays()

        if not replays:
            return []

        choices = []
        for label, path in replays:
            choices.append(questionary.Choice(label, value=str(path)))
        return choices

    def _list_replays(self) -> list[tuple[str, Path]]:
        """列出牌谱文件."""
        if not REPLAY_DIR.exists():
            return []

        replays = sorted(
            REPLAY_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:20]

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

    def _render_content(self) -> str | object | None:
        """重写以处理无牌谱情况."""
        choices = self._get_choices()
        if not choices:
            console.print("[dim]暂无牌谱记录[/dim]")
            Prompt.press_any_key()
            return BACK
        return super()._render_content()


class ReplayPlayerPage(Page):
    """牌谱播放页."""

    def __init__(self, replay_path: str):
        self.replay_path = replay_path

    def _render_content(self) -> None:
        delay = Prompt.number("回放延迟(秒):", default="0.5")
        if is_back(delay):
            return BACK

        cmd = f'python -m llm --replay "{self.replay_path}" --watch --watch-delay {delay}'

        console.print()
        console.print(f"[dim]{cmd}[/dim]")

        try:
            subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)
            # 终局暂停
            console.print()
            Prompt.press_any_key("回放结束，按任意键返回...")
        except KeyboardInterrupt:
            pass


def run() -> None:
    """运行牌谱回放."""
    choice = ReplayMenuPage().run()

    if choice is None or is_back(choice):
        return

    ReplayPlayerPage(choice).run()
