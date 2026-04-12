"""角色卡片渲染组件。

职责：
- 渲染精美的角色详情卡片
- 支持进度条可视化统计
- 预留 ASCII 形象区域

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

from llm.agent.memory import PlayerMemory, load_memory
from llm.agent.profile import PlayerProfile, load_profile
from llm.agent.stats import PlayerStats, load_stats

if TYPE_CHECKING:
    pass


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

    # 填充部分
    for _ in range(filled):
        bar.append("█", style=color)

    # 空部分
    for _ in range(width - filled):
        bar.append("░", style="bright_black")

    return bar


def render_character_card(player_id: str, players_dir: str | Path = "configs/players") -> Panel:
    """渲染角色详情卡片。

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

    # 卡片宽度（根据最长内容计算，persona 约 185 中文字符 = 370 宽度，需要约 4 行）
    # 设置为 80 字符，让 persona 自动换行成约 5 行（每行约 80/2=40 中文字符）
    card_width = 80

    # === 人设区（完整显示，自动换行） ===
    persona_lines = []
    if profile.persona_prompt:
        # 嵌套 Panel 的宽度损失：外层 border(2)+padding(2) + 内层 border(2)+padding(2) = 8
        # 内容宽度 = card_width - 8
        content_width = card_width - 8
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

        # 构建多行 Text 对象
        persona_text = Text()
        for i, ln in enumerate(persona_lines):
            if i > 0:
                persona_text.append("\n")
            persona_text.append(ln, style="dim italic white")

    # === ASCII 形象占位区 ===
    ascii_section = Text()
    ascii_section.append("  ┌──┐\n", style="bright_black")
    ascii_section.append("  │？│", style="bright_black dim")
    ascii_section.append(" ← 未来添加 ASCII 形象", style="dim italic")

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

    # 和了/放铳/立直 用不同颜色
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

    # 一位用金色，四位用红色
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

    # 整体风格
    bias_cn = {
        "aggressive": "进攻型",
        "defensive": "防守型",
        "neutral": "中性",
    }.get(memory.play_bias, memory.play_bias)
    memory_section.append("整体风格: ", style="dim")
    memory_section.append(bias_cn, style="bright_cyan" if memory.play_bias != "neutral" else "white")

    # 近期经验
    if memory.recent_patterns:
        memory_section.append("\n", style="")
        memory_section.append("近期经验:\n", style="dim")
        for p in memory.recent_patterns[:3]:  # 最多显示3条
            # 截断过长内容
            p_short = p[:35] + "..." if len(p) > 35 else p
            memory_section.append(f"  • {p_short}\n", style="cyan")

    # === 组合成紧凑卡片 ===
    card_grid = Table.grid(padding=(0, 0))
    card_grid.add_column()

    card_grid.add_row(Panel(title_section, border_style="bright_cyan", box=HEAVY, padding=(0, 1)))
    if profile.persona_prompt:
        # persona 使用分隔线 + Padding，避免 Panel 裁剪
        card_grid.add_row(Rule(style="bright_black"))
        card_grid.add_row(Padding(persona_text, (0, 1)))
    card_grid.add_row(Panel(ascii_section, border_style="bright_black", padding=(0, 1)))
    card_grid.add_row(Panel(summary_line, border_style="yellow", padding=(0, 1)))
    card_grid.add_row(Panel(stats_grid, border_style="blue", padding=(0, 1)))
    card_grid.add_row(Panel(place_grid, border_style="green", padding=(0, 1)))

    # 只有有记忆时才显示
    if memory.recent_patterns or memory.play_bias != "neutral":
        card_grid.add_row(Panel(memory_section, border_style="magenta", padding=(0, 1)))

    # 外层卡片（设置 width 让所有内层 Panel 自动适应）
    return Panel(
        card_grid,
        title="[bold bright_white]👤 角色卡片[/]",
        subtitle=f"[dim]{player_id}[/]",
        border_style="bright_white",
        box=ROUNDED,
        width=card_width,
        padding=(0, 1),
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