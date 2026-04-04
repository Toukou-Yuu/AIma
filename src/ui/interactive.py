"""交互式终端入口 - Rich + questionary.

用法::

    python -m ui.interactive

或::

    python -m ui.interactive quick  # 快速开始
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# 确保能找到 src 下的模块
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError as e:
    print(f"需要 rich: pip install rich ({e})", file=sys.stderr)
    raise SystemExit(1)

try:
    import questionary
except ImportError as e:
    print(f"需要 questionary: pip install questionary ({e})", file=sys.stderr)
    raise SystemExit(1)

if TYPE_CHECKING:
    from typing import Any


# ───────────────────────────────────────────────────────────────
# 常量
# ───────────────────────────────────────────────────────────────

PLAYERS_DIR = Path("configs/players")
KERNEL_CONFIG_PATH = Path("configs/aima_kernel.yaml")

# 角色模板
PERSONA_TEMPLATES = {
    "aggressive": {
        "name": "进攻型",
        "persona": "你是热血激进的麻将牌手，说话简短有力，喜欢直接进攻。",
        "strategy": "积极鸣牌，早立直，追求和牌速度。听牌即立，不畏惧风险。",
    },
    "defensive": {
        "name": "防守型",
        "persona": "你是谨慎沉稳的麻将牌手，说话温和但坚定。",
        "strategy": "优先安全牌，避免放铳。立直前确保足够安全，宁可弃和也不冒险。",
    },
    "balanced": {
        "name": "平衡型",
        "persona": "你是冷静理性的麻将牌手，攻守兼备。",
        "strategy": "根据场况灵活调整，攻守平衡。听牌好时立直，危险时防守。",
    },
    "adaptive": {
        "name": "变化型",
        "persona": "你是难以捉摸的麻将牌手，风格多变。",
        "strategy": "根据对手和场况随时改变策略，让对手无法预测。",
    },
}


# ───────────────────────────────────────────────────────────────
# 工具函数（与业务解耦）
# ───────────────────────────────────────────────────────────────

console = Console()


def _list_profiles() -> list[dict[str, Any]]:
    """扫描 configs/players 目录，返回所有角色配置."""
    profiles = []
    if not PLAYERS_DIR.exists():
        return profiles

    for player_dir in sorted(PLAYERS_DIR.iterdir()):
        if not player_dir.is_dir():
            continue
        profile_path = player_dir / "profile.json"
        if profile_path.exists():
            try:
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                # 兼容两种字段名
                persona = data.get("persona") or data.get("persona_prompt", "")
                persona_display = (persona[:27] + "...") if len(persona) > 30 else persona
                profiles.append({
                    "id": player_dir.name,
                    "name": data.get("name", player_dir.name),
                    "persona": persona_display,
                })
            except Exception:
                profiles.append({
                    "id": player_dir.name,
                    "name": player_dir.name,
                    "persona": "",
                })
    return profiles


def _create_profile(
    player_id: str,
    name: str,
    template_key: str,
    custom_persona: str | None = None,
) -> Path:
    """创建新角色配置."""
    player_dir = PLAYERS_DIR / player_id
    player_dir.mkdir(parents=True, exist_ok=True)

    template = PERSONA_TEMPLATES[template_key]
    persona = custom_persona if custom_persona else template["persona"]
    strategy = template["strategy"]

    profile = {
        "id": player_id,
        "name": name,
        "persona": persona,
        "strategy": strategy,
        "model": "default",
    }

    profile_path = player_dir / "profile.json"
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 初始化空 stats
    stats_path = player_dir / "stats.json"
    if not stats_path.exists():
        stats = {
            "total_games": 0,
            "total_hands": 0,
            "wins": 0,
            "deal_ins": 0,
            "riichi_count": 0,
            "riichi_wins": 0,
            "riichi_deal_ins": 0,
            "total_points": 0,
            "first_place_count": 0,
            "second_place_count": 0,
            "third_place_count": 0,
            "fourth_place_count": 0,
            "last_updated": "",
        }
        stats_path.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 初始化空 memory
    memory_path = player_dir / "memory.json"
    if not memory_path.exists():
        memory = {
            "play_bias": template["name"],
            "recent_patterns": [],
            "total_games": 0,
            "last_updated": "",
        }
        memory_path.write_text(
            json.dumps(memory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return profile_path


def _show_profile_stats(player_id: str) -> None:
    """显示角色统计（如果有）."""
    stats_path = PLAYERS_DIR / player_id / "stats.json"
    if not stats_path.exists():
        console.print("  [dim]暂无统计数据[/dim]")
        return

    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))

        if stats.get("total_games", 0) == 0:
            console.print("  [dim]暂无对局记录[/dim]")
            return

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()

        table.add_row("对局数:", str(stats["total_games"]))
        table.add_row("和了:", f"{stats['wins']} ({stats['wins']/max(stats['total_hands'],1)*100:.1f}%)")
        table.add_row("放铳:", f"{stats['deal_ins']} ({stats['deal_ins']/max(stats['total_hands'],1)*100:.1f}%)")
        table.add_row("立直:", f"{stats['riichi_count']} ({stats['riichi_count']/max(stats['total_hands'],1)*100:.1f}%)")
        table.add_row("场均得点:", f"{stats['total_points']/max(stats['total_games'],1):+.0f}")

        console.print(table)
    except Exception:
        console.print("  [dim]统计加载失败[/dim]")


# ───────────────────────────────────────────────────────────────
# 菜单
# ───────────────────────────────────────────────────────────────


def _main_menu() -> str:
    """显示主菜单，返回选择."""
    console.print()
    console.print(
        Panel(
            Text.assemble(
                ("AIma", "bold bright_cyan"),
                (" 麻将 AI 终端", "bright_white"),
            ),
            border_style="bright_cyan",
            padding=(1, 0),
        )
    )

    return questionary.select(
        "",
        choices=[
            questionary.Choice("🎮 快速开始 (Dry-run 演示)", value="quick"),
            questionary.Choice("🀄 开始对局", value="match"),
            questionary.Choice("👤 角色管理", value="profile"),
            questionary.Choice("📺 牌谱回放", value="replay"),
            questionary.Separator(),
            questionary.Choice("❌ 退出", value="quit"),
        ],
        qmark="",
        pointer="▸",
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask() or "quit"


def _profile_menu() -> None:
    """角色管理菜单."""
    while True:
        profiles = _list_profiles()

        choices = []
        for p in profiles:
            label = f"🀄 {p['name']}"
            choices.append(questionary.Choice(label, value=f"view:{p['id']}"))

        choices.extend([
            questionary.Separator(),
            questionary.Choice("➕ 创建新角色", value="create"),
            questionary.Separator(),
            questionary.Choice("🔙 返回主菜单", value="back"),
        ])

        console.print()
        choice = questionary.select(
            "角色管理",
            choices=choices,
            qmark="",
            pointer="▸",
        ).ask()

        if choice == "back" or choice is None:
            break
        elif choice == "create":
            _create_profile_wizard()
        elif choice.startswith("view:"):
            _view_profile(choice.split(":", 1)[1])


def _create_profile_wizard() -> None:
    """创建角色向导."""
    console.print()
    console.print(Panel("创建新角色", border_style="bright_green"))

    # 步骤 1: ID
    player_id = questionary.text(
        "角色标识 (用于文件夹名，如: ichihime_v2):",
        validate=lambda text: bool(text) and text.isalnum() or "只能使用字母和数字",
    ).ask()

    if not player_id:
        return

    # 检查是否已存在
    if (PLAYERS_DIR / player_id).exists():
        console.print(f"[red]错误: 角色 '{player_id}' 已存在[/red]")
        questionary.press_any_key_to_continue().ask()
        return

    # 步骤 2: 名称
    name = questionary.text(
        "显示名称 (牌桌上的名字):",
        default=player_id,
    ).ask() or player_id

    # 步骤 3: 选择模板
    template_choice = questionary.select(
        "选择人格模板:",
        choices=[
            questionary.Choice(f"🗡️  {PERSONA_TEMPLATES['aggressive']['name']}", value="aggressive"),
            questionary.Choice(f"🛡️  {PERSONA_TEMPLATES['defensive']['name']}", value="defensive"),
            questionary.Choice(f"⚖️  {PERSONA_TEMPLATES['balanced']['name']}", value="balanced"),
            questionary.Choice(f"🎭 {PERSONA_TEMPLATES['adaptive']['name']}", value="adaptive"),
        ],
        qmark="",
        pointer="▸",
    ).ask()

    if not template_choice:
        return

    # 步骤 4: 是否自定义 prompt
    customize = questionary.confirm(
        f"是否自定义人格描述? (默认: {PERSONA_TEMPLATES[template_choice]['persona'][:30]}...)",
        default=False,
    ).ask()

    custom_persona = None
    if customize:
        custom_persona = questionary.text(
            "输入自定义人格描述:",
            multiline=True,
        ).ask()

    # 创建
    try:
        path = _create_profile(player_id, name, template_choice, custom_persona)
        console.print(f"[green]✓ 角色 '{name}' 已创建![/green]")
        console.print(f"  [dim]{path}[/dim]")
    except Exception as e:
        console.print(f"[red]创建失败: {e}[/red]")

    questionary.press_any_key_to_continue().ask()


def _view_profile(player_id: str) -> None:
    """查看角色详情."""
    profile_path = PLAYERS_DIR / player_id / "profile.json"

    if not profile_path.exists():
        console.print(f"[red]角色配置不存在[/red]")
        questionary.press_any_key_to_continue().ask()
        return

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))

        console.print()
        console.print(Panel(f"🀄 {profile.get('name', player_id)}", border_style="bright_magenta"))

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()

        table.add_row("ID:", player_id)
        # 兼容两种字段名: persona/strategy 或 persona_prompt/strategy_prompt
        persona = profile.get("persona") or profile.get("persona_prompt", "")
        strategy = profile.get("strategy") or profile.get("strategy_prompt", "")
        # 智能截断：超过50字符才截断并加...
        persona_display = (persona[:47] + "...") if len(persona) > 50 else persona
        strategy_display = (strategy[:47] + "...") if len(strategy) > 50 else strategy
        table.add_row("人格:", persona_display)
        table.add_row("策略:", strategy_display)

        console.print(table)

        console.print("\n[bold]统计:[/bold]")
        _show_profile_stats(player_id)

    except Exception as e:
        console.print(f"[red]加载失败: {e}[/red]")

    questionary.press_any_key_to_continue().ask()


def _match_setup() -> None:
    """开始对局设置."""
    profiles = _list_profiles()

    if len(profiles) < 4:
        # 自动补充 default
        while len(profiles) < 4:
            profiles.append({"id": "default", "name": "默认 AI"})

    console.print()
    console.print(Panel("开始对局", border_style="bright_yellow"))

    # 选择4个玩家
    selected = []
    seats = ["东家 (0)", "南家 (1)", "西家 (2)", "北家 (3)"]

    for seat_name in seats:
        choices = [
            questionary.Choice(f"🤖 默认 AI (dry-run)", value="default"),
            questionary.Separator(),
        ]
        for p in profiles:
            choices.append(questionary.Choice(f"🀄 {p['name']}", value=p["id"]))

        choice = questionary.select(
            f"选择 {seat_name}:",
            choices=choices,
            qmark="",
            pointer="▸",
        ).ask()

        if choice is None:
            return  # 取消
        selected.append(choice)

    # 对局设置
    console.print()
    console.print("[dim]对局设置 (直接回车使用默认值)[/dim]")

    seed = questionary.text(
        "随机种子 (0=随机):",
        default="0",
    ).ask() or "0"

    max_steps = questionary.text(
        "最大步数:",
        default="500",
    ).ask() or "500"

    watch = questionary.confirm(
        "实时观战?",
        default=True,
    ).ask()

    delay = "0.5"
    if watch:
        delay = questionary.text(
            "观战延迟(秒):",
            default="0.5",
        ).ask() or "0.5"

    # 构建命令
    player_str = ",".join(selected)
    cmd_parts = [
        "python -m llm",
        f"--players {player_str}",
        f"--seed {seed}",
        f"--max-player-steps {max_steps}",
    ]

    if watch:
        cmd_parts.append("--watch")
        cmd_parts.append(f"--watch-delay {delay}")

    # 检查是否有非 default 玩家需要 API
    has_llm = any(s != "default" for s in selected)
    if has_llm and not KERNEL_CONFIG_PATH.exists():
        console.print()
        console.print("[yellow]⚠️  使用了 LLM 玩家，但未找到内核配置[/yellow]")
        console.print(f"  请创建 {KERNEL_CONFIG_PATH}")
        console.print("  或使用 --dry-run 模式")

        use_dry = questionary.confirm(
            "是否切换到 Dry-run 模式?",
            default=True,
        ).ask()
        if use_dry:
            # 全部换成 default
            cmd_parts = [
                "python -m llm",
                "--dry-run",
                f"--seed {seed}",
                f"--max-player-steps {max_steps}",
            ]
            if watch:
                cmd_parts.append("--watch")
                cmd_parts.append(f"--watch-delay {delay}")

    cmd = " ".join(cmd_parts)

    console.print()
    console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))

    confirm = questionary.confirm("确认开始?", default=True).ask()
    if not confirm:
        return

    # 执行
    console.print()
    console.print("[bold green]🚀 启动对局...[/bold green]")
    console.print()

    import subprocess
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        console.print("\n[dim]对局已中断[/dim]")

    questionary.press_any_key_to_continue().ask()


def _quick_start() -> None:
    """快速开始 - Dry-run 演示."""
    console.print()
    console.print(Panel("🎮 快速开始 (Dry-run 演示)", border_style="bright_green"))

    seed = questionary.text(
        "随机种子 (0=随机):",
        default="42",
    ).ask() or "42"

    watch = questionary.confirm(
        "实时观战?",
        default=True,
    ).ask()

    cmd_parts = [
        "python -m llm",
        "--dry-run",
        f"--seed {seed}",
        "--log-session quick",
    ]

    if watch:
        cmd_parts.append("--watch")
        cmd_parts.append("--watch-delay 0.3")

    cmd = " ".join(cmd_parts)

    console.print()
    console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))

    import subprocess
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        console.print("\n[dim]对局已中断[/dim]")

    console.print()
    console.print("[dim]日志保存于: logs/simple/quick.txt 和 logs/replay/quick.json[/dim]")
    questionary.press_any_key_to_continue().ask()


def _replay_menu() -> None:
    """牌谱回放菜单."""
    replay_dir = Path("logs/replay")

    if not replay_dir.exists():
        console.print("[dim]暂无牌谱记录[/dim]")
        questionary.press_any_key_to_continue().ask()
        return

    replays = sorted(replay_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not replays:
        console.print("[dim]暂无牌谱记录[/dim]")
        questionary.press_any_key_to_continue().ask()
        return

    choices = []
    for r in replays[:20]:  # 最近20个
        # 从文件内容提取信息
        try:
            data = json.loads(r.read_text(encoding="utf-8"))
            timestamp = data.get("timestamp", "")[:16] if isinstance(data.get("timestamp"), str) else ""
            label = f"📄 {r.stem}"
            if timestamp:
                label += f" ({timestamp})"
        except Exception:
            label = f"📄 {r.stem}"

        choices.append(questionary.Choice(label, value=str(r)))

    choices.append(questionary.Separator())
    choices.append(questionary.Choice("🔙 返回", value="back"))

    console.print()
    choice = questionary.select(
        "选择牌谱回放:",
        choices=choices,
        qmark="",
        pointer="▸",
    ).ask()

    if choice == "back" or choice is None:
        return

    # 回放
    delay = questionary.text(
        "回放延迟(秒):",
        default="0.5",
    ).ask() or "0.5"

    cmd = f'python -m llm --replay "{choice}" --watch --watch-delay {delay}'

    console.print()
    console.print(Panel(f"[dim]{cmd}[/dim]", title="执行命令", border_style="green"))

    import subprocess
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        pass

    questionary.press_any_key_to_continue().ask()


# ───────────────────────────────────────────────────────────────
# 主入口
# ───────────────────────────────────────────────────────────────


def main() -> int:
    """主循环."""
    try:
        while True:
            choice = _main_menu()

            if choice == "quit":
                console.print("\n[dim]再见! 👋[/dim]")
                return 0
            elif choice == "quick":
                _quick_start()
            elif choice == "match":
                _match_setup()
            elif choice == "profile":
                _profile_menu()
            elif choice == "replay":
                _replay_menu()

    except KeyboardInterrupt:
        console.print("\n\n[dim]已退出[/dim]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
