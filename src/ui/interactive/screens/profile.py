"""Profile management screens for the Textual UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from ui.interactive.chrome import render_empty_state
from ui.interactive.screens.base import BaseScreen, OptionPickerScreen
from ui.interactive.screens.panels import render_form_summary
from ui.interactive.utils import (
    PERSONA_TEMPLATES,
    PLAYERS_DIR,
    create_profile,
    list_profiles,
)
from ui.terminal.components.character_card import render_character_card


class ProfileBrowserScreen(BaseScreen):
    TITLE = "角色管理"
    SUBTITLE = "左侧选择角色，右侧实时预览角色卡片"
    BORDER_STYLE = "bright_magenta"

    def __init__(self) -> None:
        super().__init__()
        self._profiles: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="list-pane"):
                yield Static(Text("角色列表", style="bold bright_magenta"), classes="section-title")
                yield OptionList(id="profile-list")
            with VerticalScroll(classes="detail-pane", id="profile-preview-scroll"):
                with HorizontalScroll(classes="profile-card-x-scroll"):
                    yield Static(id="profile-preview")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("创建角色", id="profile-create", variant="primary")
            yield Button("添加 ASCII", id="profile-ascii")
            yield Button("返回首页", id="profile-home")

    def on_mount(self) -> None:
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        self._profiles = list_profiles()
        option_list = self.query_one("#profile-list", OptionList)
        option_list.clear_options()
        if not self._profiles:
            self.query_one("#profile-preview", Static).update(_render_profile_placeholder())
            return
        option_list.add_options(
            [Option(profile["name"], id=profile["id"]) for profile in self._profiles]
        )
        option_list.highlighted = 0
        self._update_preview(self._profiles[0]["id"])

    def _selected_profile_id(self) -> str | None:
        option_list = self.query_one("#profile-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None or highlighted >= len(self._profiles):
            return None
        option = option_list.get_option_at_index(highlighted)
        return option.id

    def _update_preview(self, player_id: str) -> None:
        self.query_one("#profile-preview", Static).update(
            render_character_card(player_id, PLAYERS_DIR)
        )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "profile-list" and event.option_id:
            self._update_preview(event.option_id)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-home":
            self.open_home()
        elif event.button.id == "profile-create":
            await self.app.push_screen(CreateProfileScreen(self))
        elif event.button.id == "profile-ascii":
            await self.app.push_screen(AddAsciiScreen(self))


class ProfileDetailScreen(BaseScreen):
    TITLE = "角色详情"
    SUBTITLE = "完整角色卡片"
    BORDER_STYLE = "bright_magenta"

    def __init__(self, player_id: str):
        super().__init__()
        self.player_id = player_id

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="screen-body", classes="detail-pane"):
            with HorizontalScroll(classes="profile-card-x-scroll"):
                yield Static(
                    render_character_card(self.player_id, PLAYERS_DIR),
                    id="profile-detail-card",
                )
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("返回角色列表", id="profile-detail-back", variant="primary")
            yield Button("返回首页", id="profile-detail-home")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-detail-home":
            self.dismiss()
            self.call_after_refresh(self.open_home)
        elif event.button.id == "profile-detail-back":
            self.dismiss()


class CreateProfileScreen(BaseScreen):
    TITLE = "创建新角色"
    SUBTITLE = "输入角色标识、显示名与人格模板"
    BORDER_STYLE = "bright_green"

    def __init__(self, browser: ProfileBrowserScreen):
        super().__init__()
        self.browser = browser
        self._selected_template = "balanced"

    def compose(self) -> ComposeResult:
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="form-pane"):
                yield Input(placeholder="角色标识（仅字母数字）", id="profile-id")
                yield Input(placeholder="显示名称", id="profile-name")
                yield Button("人格模板: 平衡型", id="profile-template", classes="picker-button")
                yield Checkbox("自定义人格描述", value=False, id="profile-customize")
                yield TextArea("", id="profile-persona")
            yield Static(classes="detail-pane", id="profile-create-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("创建角色", id="profile-create-submit", variant="primary")
            yield Button("返回角色列表", id="profile-create-back")

    def on_mount(self) -> None:
        self.query_one("#profile-persona", TextArea).disabled = True
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        template = PERSONA_TEMPLATES[self._selected_template]
        self.query_one("#profile-template", Button).label = f"人格模板: {template['name']}"
        rows: list[tuple[str, str | Text]] = [
            ("角色标识", self.query_one("#profile-id", Input).value or "(待填写)"),
            ("显示名称", self.query_one("#profile-name", Input).value or "(待填写)"),
            ("人格模板", template["name"]),
            ("策略摘要", template["strategy"]),
        ]
        if self.query_one("#profile-customize", Checkbox).value:
            custom_persona = self.query_one("#profile-persona", TextArea).text.strip()
            rows.append(("自定义人格", custom_persona or "(待填写)"))
        self.query_one("#profile-create-summary", Static).update(
            render_form_summary("角色草案", rows, border_style="bright_green")
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"profile-id", "profile-name"}:
            self._refresh_summary()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "profile-customize":
            self.query_one("#profile-persona", TextArea).disabled = not event.value
            self._refresh_summary()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        del event
        self._refresh_summary()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-create-back":
            self.browser._refresh_profiles()
            self.dismiss()
            return
        if event.button.id == "profile-template":
            template_options = [
                (template["name"], key)
                for key, template in PERSONA_TEMPLATES.items()
            ]
            await self.app.push_screen(
                OptionPickerScreen(
                    title="选择人格模板",
                    subtitle="每个模板都会影响默认人格描述与策略摘要",
                    options=template_options,
                    current_value=self._selected_template,
                ),
                callback=self._apply_template_choice,
            )
            return
        if event.button.id != "profile-create-submit":
            return

        player_id = self.query_one("#profile-id", Input).value.strip()
        name = self.query_one("#profile-name", Input).value.strip() or player_id
        template_key = self._selected_template
        custom_persona = None
        if self.query_one("#profile-customize", Checkbox).value:
            custom_persona = self.query_one("#profile-persona", TextArea).text.strip() or None

        if not player_id or not player_id.isalnum():
            self.set_status("角色标识只能是字母和数字，且不能为空", "red")
            return
        if (PLAYERS_DIR / player_id).exists():
            self.set_status(f"角色 {player_id} 已存在", "red")
            return

        try:
            create_profile(player_id, name, template_key, custom_persona)
        except Exception as exc:
            self.set_status(f"创建失败: {exc}", "red")
            return

        self.browser._refresh_profiles()
        self.set_status(f"角色 {name} 已创建", "green")
        self.dismiss()

    def _apply_template_choice(self, value: str | None) -> None:
        if value is None:
            return
        self._selected_template = value
        self._refresh_summary()


class AddAsciiScreen(BaseScreen):
    TITLE = "添加 ASCII 形象"
    SUBTITLE = "从图片生成终端可显示的字符画"
    BORDER_STYLE = "bright_yellow"
    IMAGE_PATH_PLACEHOLDER = "图片路径：绝对路径，或相对当前启动目录"

    def __init__(self, browser: ProfileBrowserScreen):
        super().__init__()
        self.browser = browser
        profiles = list_profiles()
        self._profile_options = [(profile["name"], profile["id"]) for profile in profiles]
        self._selected_profile = self._profile_options[0][1] if self._profile_options else ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="screen-body", classes="pane-row pane-row-large"):
            with Vertical(classes="form-pane"):
                yield Button("目标角色: 未选择", id="ascii-profile", classes="picker-button")
                yield Input(placeholder=self.IMAGE_PATH_PLACEHOLDER, id="ascii-path")
                yield Input(value="60", placeholder="输出宽度", id="ascii-width")
            yield Static(classes="detail-pane", id="ascii-summary")
        yield Static("", id="status-line")
        with Horizontal(classes="action-bar"):
            yield Button("生成 ASCII", id="ascii-submit", variant="primary")
            yield Button("返回角色列表", id="ascii-back")

    def on_mount(self) -> None:
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        player_id = self._selected_profile
        display_name = next(
            (label for label, value in self._profile_options if value == player_id),
            player_id or "未选择",
        )
        self.query_one("#ascii-profile", Button).label = f"目标角色: {display_name}"
        path_text = self.query_one("#ascii-path", Input).value or "(待填写)"
        width_text = self.query_one("#ascii-width", Input).value or "60"
        output_path = (
            PLAYERS_DIR / player_id / "ascii.txt"
            if player_id
            else Path("configs/players/<player>/ascii.txt")
        )
        self.query_one("#ascii-summary", Static).update(
            render_form_summary(
                "生成计划",
                [
                    ("目标角色", player_id or "(暂无角色)"),
                    ("图片路径", path_text),
                    ("输出宽度", width_text),
                    ("输出文件", str(output_path)),
                ],
                border_style="bright_yellow",
            )
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"ascii-path", "ascii-width"}:
            self._refresh_summary()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ascii-back":
            self.browser._refresh_profiles()
            self.dismiss()
            return
        if event.button.id == "ascii-profile":
            if not self._profile_options:
                self.set_status("当前没有可用角色", "red")
                return
            await self.app.push_screen(
                OptionPickerScreen(
                    title="选择目标角色",
                    subtitle="ASCII 形象会写入对应角色目录下的 ascii.txt",
                    options=self._profile_options,
                    current_value=self._selected_profile,
                ),
                callback=self._apply_ascii_profile,
            )
            return
        if event.button.id != "ascii-submit":
            return

        player_id = self._selected_profile
        image_path = Path(self.query_one("#ascii-path", Input).value.strip())
        width_text = self.query_one("#ascii-width", Input).value or "60"
        if not player_id:
            self.set_status("当前没有可用角色", "red")
            return
        if not image_path.exists():
            self.set_status(f"图片不存在: {image_path}", "red")
            return
        try:
            width = int(width_text)
        except ValueError:
            self.set_status("输出宽度必须是数字", "red")
            return

        from scripts.ascii_converter import image_to_unicode_art_halfblock

        output_path = PLAYERS_DIR / player_id / "ascii.txt"
        try:
            image_to_unicode_art_halfblock(image_path, output_path, width)
        except Exception as exc:
            self.set_status(f"生成失败: {exc}", "red")
            return

        self.browser._refresh_profiles()
        self.set_status(f"ASCII 形象已写入 {output_path}", "green")
        self.dismiss()

    def _apply_ascii_profile(self, value: str | None) -> None:
        if value is None:
            return
        self._selected_profile = value
        self._refresh_summary()


def _render_profile_placeholder():
    return render_empty_state(
        "暂无角色",
        "configs/players 下还没有可用角色。",
        hint="先创建角色，之后这里会显示角色卡片预览。",
    )

