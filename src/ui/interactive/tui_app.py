"""Textual 全屏 TUI 应用入口。"""

from __future__ import annotations

from textual.app import App

from ui.interactive.screens import HomeScreen, QuickStartScreen


class AImaTextualApp(App[None]):
    """AIma 全屏终端应用。"""

    CSS_PATH = "tui.tcss"
    BINDINGS = []

    def __init__(self, *, start_mode: str | None = None) -> None:
        super().__init__()
        self.start_mode = start_mode

    async def on_mount(self) -> None:
        if self.start_mode == "quick":
            await self.push_screen(QuickStartScreen())
            return
        await self.push_screen(HomeScreen())
