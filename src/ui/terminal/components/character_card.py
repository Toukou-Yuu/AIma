"""角色卡片渲染组件。

职责：
- 渲染精美的角色详情卡片
- 支持进度条可视化统计
- ASCII 形象显示在右侧

设计风格：游戏角色详情页
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.box import HEAVY, ROUNDED
from rich.cells import cell_len
from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.columns import Columns

from llm.agent.memory import PlayerMemory, load_memory
from llm.agent.profile import PlayerProfile, load_profile
from llm.agent.stats import PlayerStats, load_stats

if TYPE_CHECKING:
    pass


def load_ascii_art(player_id: str, players_dir: Path) -> Text | None:
    """加载角色的 ASCII 形象。

    Args:
        player_id: 玩家 ID
        players_dir: 玩家配置目录

    Returns:
        Rich Text 对象，如果文件不存在则返回 None
    """
    ascii_file = players_dir / player_id / "ascii.txt"
    if not ascii_file.exists():
        return None

    content = ascii_file.read_text(encoding="utf-8")
    return Text(content, style="bright_white")


def make_progress_bar(pct: float, width: int = 16, color: str = "cyan") -> Text:
    """制作彩色进度条。

    Args:
        pct: 百分比值 (0-100)
        width: 进度条宽度
        color: 颜色主题

    Returns:
        Rich Text 进度条
    """
    filled = int(pct / 100 * width)
    bar = Text()

    for _ in range(filled):
        bar.append("█", style=color)

    for _ in range(width - filled):
        bar.append("░", style="bright_black")

    return bar


def render_character_card(player_id: str, players_dir: str | Path = "configs/players") -> Panel:
    """渲染角色详情卡片（左右布局）。

    Args:
        player_id: 玩家 ID
        players_dir: 玩家配置目录

    Returns:
        Rich Panel 角色卡片
    """
    players_path = Path(players_dir)

    # 加载数据
    profile = load_profile(player_id, players_path)
    stats = load_stats(player_id, players_path)
    memory = load_memory(player_id, players_path)
    ascii_art = load_ascii_art(player_id, players_path)

    # 默认值处理
    if profile is None:
        profile = PlayerProfile(
            id=player_id,
            name=player_id,
            model="default",
            persona_prompt="",
            strategy_prompt="",
        )

    # === 标题区：名字 + 策略 ===
    title_section = Text()
    title_section.append(profile.name, style="bold bright_cyan")
    if profile.strategy_prompt:
        title_section.append(" ", style="")
        title_section.append(f"[{profile.strategy_prompt}]", style="bold red")

    # 左侧信息区参考宽度（用于 persona 换行计算）
    info_width = 52

    # === 人设区（完整显示，自动换行） ===
    persona_lines = []
    if profile.persona_prompt:
        content_width = info_width - 6  # 减去 Panel border + padding
        text = profile.persona_prompt
        line = ""
        for char in text:
            new_width = cell_len(line + char)
            if new_width > content_width:
                persona_lines.append(line)
                line = char
            else:
                line += char
        if line:
            persona_lines.append(line)

        persona_text = Text()
        for i, ln in enumerate(persona_lines):
            if i > 0:
                persona_text.append("\n")
            persona_text.append(ln, style="dim italic white")

    # === 综合统计（一行紧凑） ===
    summary_line = Text.assemble(
        ("累计 ", "dim"),
        (str(stats.total_games), "bold bright_yellow"),
        ("场 ", "dim"),
        (str(stats.total_hands), "yellow"),
        ("局  ", "dim"),
        ("平均顺位 ", "dim"),
        (f"{stats.avg_placement:.2f}", "bold bright_green" if stats.avg_placement < 2.5 else "green"),
        ("  ", ""),
        ("场均 ", "dim"),
        (f"{stats.avg_points_per_game:+.1f}", "green" if stats.avg_points_per_game >= 0 else "red"),
    )

    # === 核心统计（进度条可视化） ===
    stats_grid = Table.grid(padding=(0, 2))
    stats_grid.add_column("label", style="dim", width=8)
    stats_grid.add_column("bar", width=16)
    stats_grid.add_column("value", width=8)

    stats_grid.add_row("和了率", make_progress_bar(stats.win_rate * 100, color="green"), f"{stats.win_rate * 100:.1f}%")
    stats_grid.add_row("放铳率", make_progress_bar(stats.deal_in_rate * 100, color="red"), f"{stats.deal_in_rate * 100:.1f}%")
    stats_grid.add_row("立直率", make_progress_bar(stats.riichi_rate * 100, color="yellow"), f"{stats.riichi_rate * 100:.1f}%")
    stats_grid.add_row("立直成功", make_progress_bar(stats.riichi_success_rate * 100, color="magenta"), f"{stats.riichi_success_rate * 100:.1f}%")

    # === 顺位分布（彩色进度条） ===
    place_grid = Table.grid(padding=(0, 2))
    place_grid.add_column("place", style="dim", width=4)
    place_grid.add_column("bar", width=20)
    place_grid.add_column("pct", style="bold", width=8)
    place_grid.add_column("count", style="dim", width=5)

    one_pct = stats.first_place_count / max(stats.total_games, 1) * 100
    two_pct = stats.second_place_count / max(stats.total_games, 1) * 100
    three_pct = stats.third_place_count / max(stats.total_games, 1) * 100
    four_pct = stats.fourth_place_count / max(stats.total_games, 1) * 100

    place_grid.add_row("一位", make_progress_bar(one_pct, width=20, color="bright_yellow"), f"{one_pct:.1f}%", f"({stats.first_place_count})")
    place_grid.add_row("二位", make_progress_bar(two_pct, width=20, color="cyan"), f"{two_pct:.1f}%", f"({stats.second_place_count})")
    place_grid.add_row("三位", make_progress_bar(three_pct, width=20, color="white"), f"{three_pct:.1f}%", f"({stats.third_place_count})")
    place_grid.add_row("四位", make_progress_bar(four_pct, width=20, color="bright_red"), f"{four_pct:.1f}%", f"({stats.fourth_place_count})")

    # === 风格记忆 ===
    memory_section = Text()
    bias_cn = {
        "aggressive": "进攻型",
        "defensive": "防守型",
        "neutral": "中性",
    }.get(memory.play_bias, memory.play_bias)
    memory_section.append("整体风格: ", style="dim")
    memory_section.append(bias_cn, style="bright_cyan" if memory.play_bias != "neutral" else "white")

    if memory.recent_patterns:
        memory_section.append("\n", style="")
        memory_section.append("近期经验:\n", style="dim")
        for p in memory.recent_patterns[:3]:
            p_short = p[:35] + "..." if len(p) > 35 else p
            memory_section.append(f"  • {p_short}\n", style="cyan")

    # === 左侧信息区 ===
    left_grid = Table.grid(padding=(0, 0))
    left_grid.add_column()

    left_grid.add_row(Panel(title_section, border_style="bright_cyan", box=HEAVY, padding=(0, 1)))
    if profile.persona_prompt:
        left_grid.add_row(Rule(style="bright_black"))
        left_grid.add_row(Padding(persona_text, (0, 1)))
    left_grid.add_row(Panel(summary_line, border_style="yellow", padding=(0, 1)))
    left_grid.add_row(Panel(stats_grid, border_style="blue", padding=(0, 1)))
    left_grid.add_row(Panel(place_grid, border_style="green", padding=(0, 1)))

    if memory.recent_patterns or memory.play_bias != "neutral":
        left_grid.add_row(Panel(memory_section, border_style="magenta", padding=(0, 1)))

    # === 右侧 ASCII 形象区 ===
    if ascii_art:
        right_content = Padding(ascii_art, (0, 1, 0, 1))

        # 左右布局：紧凑排列
        main_layout = Table.grid(padding=(0, 3))
        main_layout.add_column()
        main_layout.add_column()
        main_layout.add_row(left_grid, right_content)

        return Panel(
            main_layout,
            title="[bold bright_white]👤 角色卡片[/]",
            subtitle=f"[dim]{player_id}[/]",
            border_style="bright_white",
            box=ROUNDED,
            padding=(0, 1),
            expand=False,
        )
    else:
        # 无 ASCII 形象时，显示占位提示
        placeholder = Text()
        placeholder.append("  ┌──┐\n", style="bright_black")
        placeholder.append("  │？│", style="bright_black dim")
        placeholder.append(" ← 添加 ascii.txt", style="dim italic")

        left_grid.add_row(Panel(placeholder, border_style="bright_black", padding=(0, 1)))

        return Panel(
            left_grid,
            title="[bold bright_white]👤 角色卡片[/]",
            subtitle=f"[dim]{player_id}[/]",
            border_style="bright_white",
            box=ROUNDED,
            padding=(0, 1),
            expand=False,
        )


def render_all_cards(players_dir: str | Path = "configs/players") -> Group:
    """渲染所有角色卡片（并排显示）。

    Args:
        players_dir: 玩家配置目录

    Returns:
        Rich Group 对象（多个卡片）
    """
    from rich.columns import Columns

    players_path = Path(players_dir)
    cards = []

    # 查找所有有 profile 的玩家
    for player_dir in sorted(players_path.iterdir()):
        if player_dir.is_dir() and (player_dir / "profile.json").exists():
            card = render_character_card(player_dir.name, players_path)
            cards.append(card)

    if not cards:
        return Group(Text("无角色配置", style="dim"))

    return Group(Columns(cards, equal=False))