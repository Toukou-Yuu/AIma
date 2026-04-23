"""统一页面框架 - 所有菜单/页面继承此类."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from typing import Any

console = Console()


class NavigationAction(Enum):
    """统一页面导航动作."""

    BACK = "back"


BACK = NavigationAction.BACK


def is_back(value: object) -> bool:
    """判断返回值是否为统一的返回动作."""
    return value is BACK


class Page(ABC):
    """页面基类 - 统一处理清屏、异常捕获、UI渲染."""

    # 页面标题，子类可覆盖
    title: str = ""
    # 页面副标题
    subtitle: str = ""
    # 边框颜色
    border_style: str = "bright_cyan"
    # 标题宽度
    header_width: int = 68
    # 当前页面是否支持返回上一层
    allow_back: bool = True

    def run(self) -> Any:
        """运行页面，自动处理清屏和异常."""
        self._clear_screen()
        self._render_header()

        try:
            return self._render_content()
        except Exception as e:
            self._on_error(e)
            return None

    def _clear_screen(self) -> None:
        """清屏 - 使用系统命令减少闪烁."""
        import os
        import sys

        # Windows 使用 cls，其他使用 clear
        if sys.platform == "win32":
            os.system("cls")
        else:
            console.clear()

    def _render_header(self) -> None:
        """渲染页面标题."""
        from ui.interactive.chrome import render_page_header

        if self.title:
            console.print()
            console.print(
                render_page_header(
                    self.title,
                    subtitle=self.subtitle or None,
                    border_style=self.border_style,
                    width=self.header_width,
                ),
            )
            console.print()

    @abstractmethod
    def _render_content(self) -> Any:
        """子类实现：渲染页面内容."""
        ...

    def _on_interrupt(self) -> NavigationAction | None:
        """处理页面中断请求。"""
        if self.allow_back:
            console.print("\n[dim]已返回上一层[/dim]")
            return BACK

        console.print("\n[dim]已取消[/dim]")
        return None

    def _on_error(self, error: Exception) -> None:
        """处理错误."""
        console.print(f"\n[red]错误: {error}[/red]")


class MenuPage(Page):
    """菜单页面基类 - 统一处理 questionary 菜单."""

    back_label: str = "返回上一层"

    def _render_content(self) -> str | NavigationAction | None:
        """渲染菜单."""
        import questionary
        from prompt_toolkit.styles import Style

        choices = list(self._get_choices())
        if not choices:
            return None

        if self.allow_back:
            choices.extend([
                questionary.Separator(),
                questionary.Choice(self.back_label, value=BACK),
            ])

        style = Style.from_dict({
            "selected": "bold bg:#16324f #8de1ff",
            "highlighted": "bold #8de1ff",
            "pointer": "bold #f6bd60",
            "separator": "#5c6370",
            "question": "bold #e5eef7",
            "instruction": "italic #7f8c8d",
        })

        while True:
            answer = questionary.select(
                "",
                choices=choices,
                qmark="",
                pointer="▸",
                instruction=self._get_instruction(),
                style=style,
            ).ask()
            if answer is None:
                continue
            return answer

    def _get_instruction(self) -> str:
        """菜单操作提示."""
        if self.allow_back:
            return "[↑↓选择，回车确认]"
        return "[↑↓选择，回车确认]"

    @abstractmethod
    def _get_choices(self) -> list:
        """子类实现：返回菜单选项."""
        ...


class Prompt:
    """统一输入提示类."""

    _ACTION_EDIT = "__edit__"
    _ACTION_USE_DEFAULT = "__use_default__"

    @staticmethod
    def _style():
        from prompt_toolkit.styles import Style

        return Style.from_dict({
            "question": "bold #e5eef7",
            "answer": "bold #8de1ff",
            "selected": "bold bg:#16324f #8de1ff",
            "highlighted": "bold #8de1ff",
            "pointer": "bold #f6bd60",
            "separator": "#5c6370",
            "instruction": "italic #7f8c8d",
        })

    @staticmethod
    def _build_message(message: str, instruction: str | None = None) -> list[tuple[str, str]]:
        """构建统一的输入提示文本."""
        tokens: list[tuple[str, str]] = [("class:question", f"{message} ")]
        if instruction:
            tokens.append(("class:instruction", f"{instruction}"))
        return tokens

    @staticmethod
    def _read_text(
        message: str,
        default: str = "",
        *,
        multiline: bool = False,
        instruction: str | None = None,
    ) -> str:
        """读取文本输入。"""
        from prompt_toolkit import PromptSession
        from prompt_toolkit.key_binding import KeyBindings

        bindings = KeyBindings()

        if multiline:
            @bindings.add("c-s")
            def _submit(event) -> None:
                event.app.current_buffer.validate_and_handle()

        session = PromptSession(
            style=Prompt._style(),
            multiline=multiline,
            key_bindings=bindings,
        )
        answer = session.prompt(
            Prompt._build_message(message, instruction),
            default=default,
        )
        return answer

    @staticmethod
    def _format_default_label(default: str) -> str:
        """格式化默认值菜单标签。"""
        compact = default.replace("\n", " ").strip()
        if len(compact) > 24:
            compact = compact[:21] + "..."
        return compact or "(空)"

    @staticmethod
    def _input_via_menu(
        message: str,
        *,
        default: str = "",
        multiline: bool = False,
        edit_label: str,
        default_label: str | None = None,
        submit_instruction: str,
    ) -> str | NavigationAction:
        """先选操作，再进入输入。"""
        import questionary

        choices = [questionary.Choice(edit_label, value=Prompt._ACTION_EDIT)]
        if default_label is not None:
            choices.append(questionary.Choice(default_label, value=Prompt._ACTION_USE_DEFAULT))

        action = Prompt.select(
            message,
            choices=choices,
            instruction="[↑↓选择操作，回车确认]",
        )
        if is_back(action):
            return BACK
        if action == Prompt._ACTION_USE_DEFAULT:
            return default
        return Prompt._read_text(
            message,
            default=default,
            multiline=multiline,
            instruction=submit_instruction,
        )

    @staticmethod
    def select(
        message: str,
        choices: list,
        instruction: str = "[↑↓选择，回车确认]",
        allow_back: bool = True,
    ) -> Any:
        """统一选择输入."""
        import questionary

        resolved_choices = list(choices)
        if allow_back:
            resolved_choices.extend([
                questionary.Separator(),
                questionary.Choice("返回上一层", value=BACK),
            ])

        while True:
            answer = questionary.select(
                message,
                choices=resolved_choices,
                qmark="",
                pointer="▸",
                instruction=instruction,
                style=Prompt._style(),
            ).ask()
            if answer is None:
                continue
            return answer

    @staticmethod
    def confirm(message: str, default: bool = True) -> bool | NavigationAction:
        """确认对话框."""
        import questionary

        choices = [
            questionary.Choice("是", value=True),
            questionary.Choice("否", value=False),
        ]
        if not default:
            choices.reverse()

        answer = Prompt.select(
            message,
            choices=choices,
            instruction="[↑↓选择，回车确认]",
        )
        return answer

    @staticmethod
    def text(message: str, default: str = "") -> str | NavigationAction:
        """文本输入."""
        default_label = None
        if default:
            default_label = f"使用默认值: {Prompt._format_default_label(default)}"
        return Prompt._input_via_menu(
            message,
            default=default,
            edit_label="输入内容" if not default else "编辑内容",
            default_label=default_label,
            submit_instruction="(输入后回车确认)",
        )

    @staticmethod
    def number(message: str, default: str = "0") -> str | NavigationAction:
        """数字输入."""
        answer = Prompt._input_via_menu(
            message,
            default=default,
            edit_label="输入数值",
            default_label=f"使用默认值: {Prompt._format_default_label(default)}",
            submit_instruction="(输入后回车确认)",
        )
        return BACK if answer is BACK else (answer or default)

    @staticmethod
    def multiline(message: str) -> str | NavigationAction:
        """多行文本输入."""
        return Prompt._input_via_menu(
            message,
            multiline=True,
            edit_label="开始输入",
            submit_instruction="(Ctrl+S确认)",
        )

    @staticmethod
    def press_any_key(message: str = "选择返回继续...") -> None:
        """等待用户通过菜单项继续。"""
        import questionary

        console.print()
        console.print(f"[dim]{message}[/dim]")
        while True:
            answer = questionary.select(
                "",
                choices=[questionary.Choice("返回", value=True)],
                qmark="",
                pointer="▸",
                instruction="[回车返回]",
                style=Prompt._style(),
            ).ask()
            if answer is not None:
                return
