"""游戏设置界面：调整内核规则配置。"""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Static

from kernel.config import MahjongConfig
from kernel.config_manager import KernelConfigManager
from ui.interactive.chrome import render_page_header, render_summary_panel
from ui.interactive.screens.base import BaseScreen, OptionPickerScreen


class SettingsScreen(BaseScreen):
    """游戏设置界面。"""

    TITLE = "游戏设置"
    SUBTITLE = "调整内核规则配置（下次新建对局生效）"
    BORDER_STYLE = "bright_blue"
    HEADER_WIDTH = 88

    def __init__(self) -> None:
        super().__init__()
        self._config: MahjongConfig = KernelConfigManager.load()
        self._modified = False

    def compose(self) -> ComposeResult:
        yield Static(self.build_header(), id="screen-header")
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with VerticalScroll(classes="form-pane"):
                # 对局形式
                yield Static(Text("对局形式", style="bold bright_green"), classes="section-title")
                yield Checkbox(
                    "半庄战（东+南各4局）",
                    value=self._config.match_length == "hanchan",
                    id="chk-hanchan",
                )
                yield Checkbox(
                    "东风战（仅东场4局）",
                    value=self._config.match_length == "tonpuusen",
                    id="chk-tonpuusen",
                )
                yield Input(
                    value=str(self._config.starting_points),
                    placeholder="起配点",
                    id="input-starting-points",
                )
                yield Input(
                    value=str(self._config.round_wind_count),
                    placeholder="场风圈数（东=1，东+南=2）",
                    id="input-round-wind-count",
                )

                # 鸣牌与役
                yield Static(Text("鸣牌与役", style="bold bright_green"), classes="section-title")
                yield Checkbox("食断あり（副露后断幺九可役）", value=self._config.allow_open_tanyao, id="chk-open-tanyao")
                yield Checkbox("一炮多响あり（多家同时荣和）", value=self._config.allow_multiple_ron, id="chk-multiple-ron")

                # 宝牌
                yield Static(Text("宝牌", style="bold bright_green"), classes="section-title")
                yield Checkbox("赤牌（三赤：5m/5p/5s）", value=self._config.red_dora_enabled, id="chk-red-dora")
                yield Checkbox("里宝牌（立直和了翻开里宝）", value=self._config.ura_dora_enabled, id="chk-ura-dora")

                # 满贯规则
                yield Static(Text("满贯规则", style="bold bright_green"), classes="section-title")
                yield Checkbox("流局满贯（荒牌流局时听牌且全舍牌幺九）", value=self._config.flow_mangan_enabled, id="chk-flow-mangan")
                yield Checkbox("切上满贯（3番70符/4番40符按满贯）", value=self._config.kiriage_mangan_enabled, id="chk-kiriage-mangan")

                # 其他规则
                yield Static(Text("其他规则", style="bold bright_green"), classes="section-title")
                yield Checkbox("一发あり（立直后下一巡内和了）", value=self._config.ippatsu_enabled, id="chk-ippatsu")
                yield Checkbox("西入（半庄南场后亲家听牌进西场）", value=self._config.west_round_enabled, id="chk-west-round")
                yield Input(value=str(self._config.riichi_stick_value), placeholder="立直棒点数", id="input-riichi-stick")
                yield Input(value=str(self._config.honba_value), placeholder="本场费", id="input-honba-value")

            yield Static(classes="detail-pane", id="settings-preview")

        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("返回", id="btn-back")
            yield Button("应用", id="btn-apply", variant="primary")
            yield Button("重置为默认值", id="btn-reset", variant="warning")

    def on_mount(self) -> None:
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """更新右侧配置摘要预览。"""
        preview = self.query_one("#settings-preview", Static)
        preview.update(self._build_preview_panel())

    def _build_preview_panel(self) -> Panel:
        """构建配置摘要面板。"""
        rows = [
            ("对局形式", self._config.match_length),
            ("起配点", str(self._config.starting_points)),
            ("场风圈数", str(self._config.round_wind_count)),
            ("食断", "あり" if self._config.allow_open_tanyao else "なし"),
            ("一炮多响", "あり" if self._config.allow_multiple_ron else "なし"),
            ("赤牌", "あり" if self._config.red_dora_enabled else "なし"),
            ("里宝牌", "あり" if self._config.ura_dora_enabled else "なし"),
            ("流局满贯", "あり" if self._config.flow_mangan_enabled else "なし"),
            ("切上满贯", "あり" if self._config.kiriage_mangan_enabled else "なし"),
            ("一发", "あり" if self._config.ippatsu_enabled else "なし"),
            ("西入", "あり" if self._config.west_round_enabled else "なし"),
            ("立直棒", f"{self._config.riichi_stick_value}点"),
            ("本场费", f"{self._config.honba_value}点/场"),
        ]
        return render_summary_panel("当前配置摘要", rows, border_style=self.BORDER_STYLE)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Checkbox 变化时更新配置。"""
        self._modified = True
        self._apply_checkbox_to_config(event.checkbox.id, event.checkbox.value)
        self._refresh_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Input 变化时更新配置。"""
        self._modified = True
        self._apply_input_to_config(event.input.id, event.input.value)
        self._refresh_preview()

    def _apply_checkbox_to_config(self, checkbox_id: str | None, value: bool) -> None:
        """将 Checkbox 值应用到配置。"""
        if checkbox_id is None:
            return

        # 对局形式特殊处理
        if checkbox_id == "chk-hanchan" and value:
            self._config = MahjongConfig(
                match_length="hanchan",
                starting_points=self._config.starting_points,
                round_wind_count=self._config.round_wind_count,
                allow_open_tanyao=self._config.allow_open_tanyao,
                allow_multiple_ron=self._config.allow_multiple_ron,
                red_dora_enabled=self._config.red_dora_enabled,
                ura_dora_enabled=self._config.ura_dora_enabled,
                flow_mangan_enabled=self._config.flow_mangan_enabled,
                kiriage_mangan_enabled=self._config.kiriage_mangan_enabled,
                ippatsu_enabled=self._config.ippatsu_enabled,
                west_round_enabled=self._config.west_round_enabled,
                riichi_stick_value=self._config.riichi_stick_value,
                honba_value=self._config.honba_value,
            )
        elif checkbox_id == "chk-tonpuusen" and value:
            self._config = MahjongConfig(
                match_length="tonpuusen",
                starting_points=self._config.starting_points,
                round_wind_count=1,
                allow_open_tanyao=self._config.allow_open_tanyao,
                allow_multiple_ron=self._config.allow_multiple_ron,
                red_dora_enabled=self._config.red_dora_enabled,
                ura_dora_enabled=self._config.ura_dora_enabled,
                flow_mangan_enabled=self._config.flow_mangan_enabled,
                kiriage_mangan_enabled=self._config.kiriage_mangan_enabled,
                ippatsu_enabled=self._config.ippatsu_enabled,
                west_round_enabled=self._config.west_round_enabled,
                riichi_stick_value=self._config.riichi_stick_value,
                honba_value=self._config.honba_value,
            )
            # 更新 round_wind_count 输入框
            self.query_one("#input-round-wind-count", Input).value = "1"
        elif checkbox_id == "chk-open-tanyao":
            self._update_config_field("allow_open_tanyao", value)
        elif checkbox_id == "chk-multiple-ron":
            self._update_config_field("allow_multiple_ron", value)
        elif checkbox_id == "chk-red-dora":
            self._update_config_field("red_dora_enabled", value)
        elif checkbox_id == "chk-ura-dora":
            self._update_config_field("ura_dora_enabled", value)
        elif checkbox_id == "chk-flow-mangan":
            self._update_config_field("flow_mangan_enabled", value)
        elif checkbox_id == "chk-kiriage-mangan":
            self._update_config_field("kiriage_mangan_enabled", value)
        elif checkbox_id == "chk-ippatsu":
            self._update_config_field("ippatsu_enabled", value)
        elif checkbox_id == "chk-west-round":
            self._update_config_field("west_round_enabled", value)

    def _apply_input_to_config(self, input_id: str | None, value: str) -> None:
        """将 Input 值应用到配置。"""
        if input_id is None or not value:
            return

        try:
            int_value = int(value)
        except ValueError:
            return

        if input_id == "input-starting-points":
            self._update_config_field("starting_points", int_value)
        elif input_id == "input-round-wind-count":
            self._update_config_field("round_wind_count", int_value)
        elif input_id == "input-riichi-stick":
            self._update_config_field("riichi_stick_value", int_value)
        elif input_id == "input-honba-value":
            self._update_config_field("honba_value", int_value)

    def _update_config_field(self, field: str, value: bool | int) -> None:
        """更新配置字段（创建新实例）。"""
        from dataclasses import replace

        self._config = replace(self._config, **{field: value})

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击处理。"""
        if event.button.id == "btn-back":
            if self._modified:
                await self._confirm_discard_changes()
            else:
                self.open_home()
        elif event.button.id == "btn-apply":
            self._save_config()
            self.set_status("配置已保存，下次新建对局生效", style="green")
            self._modified = False
        elif event.button.id == "btn-reset":
            self._reset_to_default()

    async def _confirm_discard_changes(self) -> None:
        """未保存更改时弹出确认。"""
        picker = OptionPickerScreen(
            title="未保存的更改",
            subtitle="返回将丢失当前修改",
            options=[
                ("discard", "放弃更改并返回"),
                ("continue", "继续编辑"),
            ],
        )
        result = await self.app.push_screen(picker)
        if result == "discard":
            self.open_home()

    def _save_config(self) -> None:
        """保存配置到 YAML。"""
        KernelConfigManager.save(self._config)

    def _reset_to_default(self) -> None:
        """重置为默认配置。"""
        self._config = MahjongConfig.default()
        self._modified = True

        # 更新所有控件值
        self.query_one("#chk-hanchan", Checkbox).value = True
        self.query_one("#chk-tonpuusen", Checkbox).value = False
        self.query_one("#input-starting-points", Input).value = "25000"
        self.query_one("#input-round-wind-count", Input).value = "2"
        self.query_one("#chk-open-tanyao", Checkbox).value = True
        self.query_one("#chk-multiple-ron", Checkbox).value = True
        self.query_one("#chk-red-dora", Checkbox).value = True
        self.query_one("#chk-ura-dora", Checkbox).value = True
        self.query_one("#chk-flow-mangan", Checkbox).value = True
        self.query_one("#chk-kiriage-mangan", Checkbox).value = True
        self.query_one("#chk-ippatsu", Checkbox).value = True
        self.query_one("#chk-west-round", Checkbox).value = False
        self.query_one("#input-riichi-stick", Input).value = "1000"
        self.query_one("#input-honba-value", Input).value = "300"

        self._refresh_preview()
        self.set_status("已重置为默认配置", style="yellow")