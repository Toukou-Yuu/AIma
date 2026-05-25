"""HomeScreen - 实验列表界面。"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static

from ui.viewer.data_source import ExperimentInfo, RunDataSource
from ui.viewer.screens.base import BaseScreen

if TYPE_CHECKING:
    from textual.widget import Widget
    from textual.widgets.option_list import Option


class ExperimentOption:
    """实验列表项。"""

    def __init__(self, exp: ExperimentInfo) -> None:
        self.exp = exp

    def __rich__(self) -> Text:
        """渲染实验信息。"""
        # 格式: [job数] experiment_id - description (tags)
        parts = [f"[{self.exp.job_count:3d}] {self.exp.experiment_id}"]
        if self.exp.description:
            # 限制描述长度
            desc = self.exp.description[:40] + "..." if len(self.exp.description) > 40 else self.exp.description
            parts.append(f" - {desc}")
        if self.exp.tags:
            tags = ", ".join(self.exp.tags[:3])
            if len(self.exp.tags) > 3:
                tags += "..."
            parts.append(f" ({tags})")

        return Text("".join(parts))


class HomeScreen(BaseScreen):
    """实验列表界面。"""

    TITLE = "AIma 实验查看器"
    SUBTITLE = "选择实验查看详情"

    def __init__(
        self,
        run_root: Path,
        *,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id)
        self.run_root = Path(run_root)
        self._data_source = RunDataSource(self.run_root)
        self._experiments: list[ExperimentInfo] = []

    def compose(self) -> Generator[Widget, None, None]:
        """构建界面布局。"""
        yield Static(self.build_header())

        with Horizontal():
            with Vertical(id="experiment-list-container"):
                yield Static(Text("实验列表", style="bold"), classes="list-title")
                yield OptionList(id="experiment-list")

        yield Static(Text("", style="dim"), id="status-line")

    async def on_mount(self) -> None:
        """加载实验列表。"""
        self._load_experiments()

    def _load_experiments(self) -> None:
        """加载实验列表。"""
        self._experiments = self._data_source.list_experiments()
        list_widget = self.query_one("#experiment-list", OptionList)
        list_widget.clear_options()

        if not self._experiments:
            self.set_status("暂无实验数据", style="yellow")
            return

        for exp in self._experiments:
            option: Option = Option(ExperimentOption(exp), id=f"exp-{exp.experiment_id}")  # type: ignore[arg-type]
            list_widget.add_option(option)

        self.set_status(f"共 {len(self._experiments)} 个实验")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """实验选择事件处理。"""
        # 获取选中的实验
        if event.option_id is None:
            return

        # 从 option_id 提取 experiment_id (格式: exp-{id})
        exp_id = event.option_id[4:]  # 移除 "exp-" 前缀
        selected_exp = next((e for e in self._experiments if e.experiment_id == exp_id), None)

        if selected_exp is None:
            return

        # 获取该实验下的 jobs
        jobs = self._data_source.get_jobs(selected_exp.experiment_id)
        if not jobs:
            self.set_status(f"实验 {selected_exp.experiment_id} 没有任务", style="yellow")
            return

        # 自动选择第一个 job 进入 MatchScreen
        first_job = jobs[0]
        from ui.viewer.screens.match_screen import MatchScreen

        self.app.push_screen(
            MatchScreen(
                data_source=self._data_source,
                job_id=first_job.job_id,
            )
        )