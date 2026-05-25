"""Viewer App - 对局回放查看器。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App

if TYPE_CHECKING:
    pass


class ViewerApp(App[None]):
    """对局回放查看器。"""

    CSS_PATH = "viewer.tcss"
    BINDINGS = [
        ("q", "quit", "退出"),
        ("d", "toggle_dark", "切换主题"),
    ]

    def __init__(
        self,
        *,
        run_dir: Path,
        job_id: str | None = None,
        initial_step: int = 0,
    ) -> None:
        super().__init__()
        self.run_dir = Path(run_dir)
        self.job_id = job_id
        self.initial_step = initial_step

    async def on_mount(self) -> None:
        """启动时加载初始界面。"""
        if self.job_id:
            # TODO: 直接加载 MatchScreen
            pass
        else:
            # 显示实验列表
            from ui.viewer.screens.home_screen import HomeScreen

            self.push_screen(HomeScreen(self.run_dir))