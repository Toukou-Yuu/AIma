"""Shared Textual screen primitives."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ui.interactive.chrome import render_page_header


class BaseScreen(Screen[None]):
    """通用 screen 基类。"""

    TITLE = ""
    SUBTITLE = ""
    BORDER_STYLE = "bright_cyan"
    HEADER_WIDTH = 88

    def build_header(self) -> Panel:
        return render_page_header(
            self.TITLE,
            subtitle=self.SUBTITLE,
            border_style=self.BORDER_STYLE,
            width=self.HEADER_WIDTH,
        )

    def set_status(self, message: str, style: str = "dim") -> None:
        status = self.query_one("#status-line", Static)
        status.update(Text(message, style=style))

    def open_home(self) -> None:
        from ui.interactive.screens.home import HomeScreen

        self.app.switch_screen(HomeScreen())


class OptionPickerScreen(ModalScreen[str | None]):
    """通用选项选择弹层。"""

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        options: list[tuple[str, str]],
        current_value: str | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.options = options
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        with Container(id="picker-modal"):
            yield Static(
                render_page_header(
                    self.title,
                    subtitle=self.subtitle,
                    border_style="bright_cyan",
                    width=72,
                ),
                id="picker-header",
            )
            yield OptionList(
                *[Option(label, id=value) for label, value in self.options],
                id="picker-options",
            )
            with Horizontal(classes="action-bar modal-actions"):
                yield Button("确认选择", id="picker-confirm", variant="primary")
                yield Button("取消", id="picker-cancel")

    def on_mount(self) -> None:
        option_list = self.query_one("#picker-options", OptionList)
        if self.current_value is None:
            option_list.highlighted = 0
            return
        for index, (_label, value) in enumerate(self.options):
            if value == self.current_value:
                option_list.highlighted = index
                return
        option_list.highlighted = 0

    def _selected_value(self) -> str | None:
        option_list = self.query_one("#picker-options", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None or highlighted >= len(self.options):
            return None
        option = option_list.get_option_at_index(highlighted)
        return option.id

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "picker-options":
            self.dismiss(event.option_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-cancel":
            self.dismiss(None)
        elif event.button.id == "picker-confirm":
            self.dismiss(self._selected_value())

