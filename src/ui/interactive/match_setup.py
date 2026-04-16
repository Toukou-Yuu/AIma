"""对局设置与启动 - 使用统一框架重构。"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel

from ui.interactive.framework import BACK, MenuPage, Page, Prompt, is_back
from ui.interactive.session_runner import run_llm_session
from ui.interactive.utils import KERNEL_CONFIG_PATH, list_profiles

console = Console()

SEATS = ["东家 (0)", "南家 (1)", "西家 (2)", "北家 (3)"]


@dataclass
class QuickStartConfig:
    """demo 演示配置."""

    seed: str = "42"
    watch: bool = True
    delay: str = "0.3"

    def seed_label(self) -> str:
        """种子显示文本."""
        return "随机" if self.seed == "0" else self.seed

    def build_command(self) -> str:
        """构建 demo 命令."""
        cmd_parts = [
            "python -m llm",
            "--dry-run",
            f"--seed {self.seed}",
            "--log-session quick",
        ]

        if self.watch:
            cmd_parts.append("--watch")
            cmd_parts.append(f"--watch-delay {self.delay}")

        return " ".join(cmd_parts)

    def build_argv(self) -> list[str]:
        """构建 demo CLI 参数。"""
        argv = [
            "--dry-run",
            "--seed",
            self.seed,
            "--log-session",
            "quick",
        ]
        if self.watch:
            argv.extend(["--watch", "--watch-delay", self.delay])
        return argv

    def summary_text(self) -> str:
        """当前 demo 配置摘要。"""
        watch_mode = "实时观战" if self.watch else "静默运行"
        lines = [
            f"随机种子: {self.seed_label()}",
            f"运行模式: {watch_mode}",
        ]
        if self.watch:
            lines.append(f"观战延迟: {self.delay} 秒")
        return "\n".join(lines)


class SelectPlayerPage(MenuPage):
    """选择玩家页."""

    def __init__(self, seat_name: str, profiles: list[dict]):
        self.seat_name = seat_name
        self.profiles = profiles
        self.title = f"选择 {seat_name}"

    def _get_choices(self) -> list:
        import questionary

        choices = [
            questionary.Choice("默认 AI (dry-run)", value="default"),
            questionary.Separator(),
        ]
        for p in self.profiles:
            choices.append(questionary.Choice(p['name'], value=p["id"]))
        return choices

    def _get_instruction(self) -> str:
        return f"[选择 {self.seat_name}]"


class MatchSetupPage(Page):
    """对局设置页."""

    title = "开始对局"
    border_style = "bright_yellow"

    def _render_content(self) -> None:
        profiles = list_profiles()
        while len(profiles) < 4:
            profiles.append({"id": "default", "name": "默认 AI"})

        # 选择4个玩家
        selected = []
        for seat_name in SEATS:
            choice = SelectPlayerPage(seat_name, profiles).run()
            if is_back(choice):
                return BACK
            selected.append(choice)

        # 对局设置
        settings = self._configure_settings()
        if is_back(settings):
            return BACK

        # 构建并执行命令
        cli_args = self._build_cli_args(selected, settings)
        if is_back(cli_args):
            return BACK
        if cli_args is None:
            return None

        self._execute_command(cli_args, settings["watch"])

    def _configure_settings(self) -> dict | object:
        """配置对局设置."""
        console.print()
        console.print("[dim]对局设置 (直接回车使用默认值)[/dim]")

        seed = Prompt.number("随机种子 (0=随机):", default="0")
        if is_back(seed):
            return BACK
        max_hands = Prompt.number("局数 (4=东风, 8=半庄):", default="8")
        if is_back(max_hands):
            return BACK
        watch = Prompt.confirm("实时观战?", default=True)
        if is_back(watch):
            return BACK

        delay = "0.5"
        if watch:
            delay = Prompt.number("观战延迟(秒):", default="0.5")
            if is_back(delay):
                return BACK

        return {
            "seed": seed,
            "max_hands": max_hands,
            "watch": watch,
            "delay": delay,
        }

    def _build_cli_args(self, selected: list[str], settings: dict) -> list[str] | object | None:
        """构建 ``llm.cli`` 参数。"""
        player_str = ",".join(selected)
        max_hands = settings.get('max_hands', 8)
        cli_args = [
            "--config",
            str(KERNEL_CONFIG_PATH),
            "--players",
            player_str,
            "--seed",
            settings["seed"],
            "--max-hands",
            str(max_hands),
        ]

        if settings["watch"]:
            cli_args.extend(["--watch", "--watch-delay", settings["delay"]])

        # 添加日志参数（使用空字符串自动生成时间戳文件名）
        cli_args.extend(["--log-session", ""])

        # 检查是否需要 API Key
        has_llm = any(s != "default" for s in selected)
        if has_llm and not KERNEL_CONFIG_PATH.exists():
            console.print()
            console.print("[yellow]⚠️  使用了 LLM 玩家，但未找到内核配置[/yellow]")
            console.print(f"  请创建 {KERNEL_CONFIG_PATH}")
            console.print("  或使用 --dry-run 模式")

            use_dry = Prompt.confirm("是否切换到 Dry-run 模式?", default=True)
            if is_back(use_dry):
                return BACK
            if use_dry:
                cli_args = [
                    "--dry-run",
                    "--seed",
                    settings["seed"],
                ]
                if settings["watch"]:
                    cli_args.extend(["--watch", "--watch-delay", settings["delay"]])
            else:
                return None

        console.print()
        console.print(
            Panel(
                "\n".join(
                    [
                        f"玩家阵容: {player_str}",
                        f"随机种子: {settings['seed']}",
                        f"对局局数: {max_hands}",
                        f"观战模式: {'开启' if settings['watch'] else '关闭'}",
                    ]
                ),
                title="即将开始",
                border_style="green",
                padding=(1, 2),
            )
        )

        confirmed = Prompt.confirm("确认开始?", default=True)
        if is_back(confirmed):
            return BACK
        if not confirmed:
            return None

        return cli_args

    def _execute_command(self, cli_args: list[str], watch: bool) -> None:
        """执行对局会话。"""
        console.print()
        console.print("[bold green]🚀 启动对局...[/bold green]")
        console.print()

        result = run_llm_session(cli_args)
        if result.returncode != 0:
            console.print(f"\n[red]✗ 对局执行失败 (返回码: {result.returncode})[/red]")
            console.print("[dim]请检查配置和依赖是否正确安装[/dim]")
            Prompt.press_any_key()
            return
        console.print("\n[dim]✓ 对局已结束[/dim]")
        console.print()
        Prompt.press_any_key("终局牌桌已保留，按返回回到菜单...")


def run() -> None:
    """运行对局设置."""
    MatchSetupPage().run()


class QuickStartMenuPage(MenuPage):
    """demo 配置菜单."""

    title = "demo演示"
    border_style = "bright_green"

    def __init__(self, config: QuickStartConfig):
        self.config = config

    def _render_content(self) -> str | object | None:
        console.print(Panel(
            self.config.summary_text(),
            title="当前配置",
            border_style="green",
            padding=(1, 2),
        ))
        console.print()
        return super()._render_content()

    def _get_choices(self) -> list:
        import questionary

        choices = [
            questionary.Choice("开始演示", value="start"),
            questionary.Separator(),
            questionary.Choice(
                f"随机种子: {self.config.seed_label()}",
                value="seed",
            ),
            questionary.Choice(
                f"实时观战: {'开启' if self.config.watch else '关闭'}",
                value="watch",
            ),
        ]
        if self.config.watch:
            choices.append(
                questionary.Choice(f"观战延迟: {self.config.delay} 秒", value="delay")
            )
        return choices


class QuickStartPage(Page):
    """快速开始页."""

    title = "demo演示"
    border_style = "bright_green"

    def _render_content(self) -> None:
        config = QuickStartConfig()

        while True:
            action = QuickStartMenuPage(config).run()
            if is_back(action):
                return BACK
            if action == "start":
                if self._execute_demo(config):
                    return None
                continue
            if action == "seed":
                self._configure_seed(config)
            elif action == "watch":
                config.watch = not config.watch
            elif action == "delay":
                self._configure_delay(config)

    def _configure_seed(self, config: QuickStartConfig) -> None:
        """配置种子."""
        import questionary

        choice = Prompt.select(
            "选择随机种子:",
            choices=[
                questionary.Choice("固定种子 42", value="42"),
                questionary.Choice("随机种子", value="0"),
                questionary.Choice("自定义输入", value="custom"),
            ],
        )
        if is_back(choice):
            return
        if choice == "custom":
            custom_seed = Prompt.number("输入随机种子 (0=随机):", default=config.seed)
            if is_back(custom_seed):
                return
            config.seed = custom_seed
            return
        config.seed = choice

    def _configure_delay(self, config: QuickStartConfig) -> None:
        """配置观战延迟."""
        import questionary

        choice = Prompt.select(
            "选择观战延迟:",
            choices=[
                questionary.Choice("0.1 秒", value="0.1"),
                questionary.Choice("0.3 秒", value="0.3"),
                questionary.Choice("0.5 秒", value="0.5"),
                questionary.Choice("1.0 秒", value="1.0"),
                questionary.Choice("自定义输入", value="custom"),
            ],
        )
        if is_back(choice):
            return
        if choice == "custom":
            custom_delay = Prompt.number("输入观战延迟(秒):", default=config.delay)
            if is_back(custom_delay):
                return
            config.delay = custom_delay
            return
        config.delay = choice

    def _execute_demo(self, config: QuickStartConfig) -> bool:
        """执行 demo；成功结束后返回 True。"""
        cli_args = config.build_argv()

        console.print()
        console.print(
            Panel(
                config.summary_text(),
                title="即将开始 demo",
                border_style="green",
                padding=(1, 2),
            )
        )

        result = run_llm_session(cli_args)
        if result.returncode != 0:
            console.print(f"\n[red]✗ 对局执行失败 (返回码: {result.returncode})[/red]")
            Prompt.press_any_key()
            self._clear_screen()
            return False
        console.print("\n[dim]✓ 对局已结束[/dim]")
        console.print()
        Prompt.press_any_key("终局牌桌已保留，按返回回到菜单...")
        self._clear_screen()
        return True


def quick_start() -> None:
    """快速开始."""
    QuickStartPage().run()
