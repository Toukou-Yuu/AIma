"""游戏设置界面：调整内核规则配置。"""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, RadioSet, RadioButton, Static

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
                with RadioSet(id="radio-match-length"):
                    yield RadioButton(
                        "半庄战（东+南各4局）",
                        value=self._config.match_length == "hanchan",
                        id="radio-hanchan",
                    )
                    yield RadioButton(
                        "东风战（仅东场4局）",
                        value=self._config.match_length == "tonpuusen",
                        id="radio-tonpuusen",
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

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """RadioSet 变化时更新对局形式配置。"""
        self._modified = True
        if event.radio_set.id == "radio-match-length":
            # event.pressed 是当前选中的 RadioButton
            if event.pressed.id == "radio-hanchan":
                self._update_config_field("match_length", "hanchan")
            elif event.pressed.id == "radio-tonpuusen":
                self._update_config_field("match_length", "tonpuusen")
                # 东风战强制场风圈数为 1
                self._update_config_field("round_wind_count", 1)
                self.query_one("#input-round-wind-count", Input).value = "1"
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

        field_mapping = {
            "chk-open-tanyao": "allow_open_tanyao",
            "chk-multiple-ron": "allow_multiple_ron",
            "chk-red-dora": "red_dora_enabled",
            "chk-ura-dora": "ura_dora_enabled",
            "chk-flow-mangan": "flow_mangan_enabled",
            "chk-kiriage-mangan": "kiriage_mangan_enabled",
            "chk-ippatsu": "ippatsu_enabled",
            "chk-west-round": "west_round_enabled",
        }

        if checkbox_id in field_mapping:
            self._update_config_field(field_mapping[checkbox_id], value)

    def _apply_input_to_config(self, input_id: str | None, value: str) -> None:
        """将 Input 值应用到配置。"""
        if input_id is None or not value:
            return

        try:
            int_value = int(value)
        except ValueError:
            return

        if input_id == "input-starting-points":
            if int_value < 1000:
                self.set_status("起配点必须 >= 1000", style="red")
                return
            if int_value > 50000:
                self.set_status("起配点必须 <= 50000", style="red")
                return
            self._update_config_field("starting_points", int_value)
            self.set_status("")  # 清除警告
        elif input_id == "input-round-wind-count":
            self._update_config_field("round_wind_count", int_value)
        elif input_id == "input-riichi-stick":
            if int_value < 100:
                self.set_status("立直棒点数必须 >= 100", style="red")
                return
            if int_value > 5000:
                self.set_status("立直棒点数必须 <= 5000", style="red")
                return
            self._update_config_field("riichi_stick_value", int_value)
            self.set_status("")  # 清除警告
        elif input_id == "input-honba-value":
            if int_value < 0:
                self.set_status("本场费必须 >= 0", style="red")
                return
            if int_value > 1000:
                self.set_status("本场费必须 <= 1000", style="red")
                return
            self._update_config_field("honba_value", int_value)
            self.set_status("")  # 清除警告

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
        try:
            KernelConfigManager.save(self._config)
        except Exception as e:
            self.set_status(f"保存失败: {e}", style="red")
            return

    def _reset_to_default(self) -> None:
        """重置为默认配置。"""
        self._config = MahjongConfig.default()
        self._modified = True

        # 更新所有控件值
        radio_set = self.query_one("#radio-match-length", RadioSet)
        radio_set.query_one("#radio-hanchan", RadioButton).value = True
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