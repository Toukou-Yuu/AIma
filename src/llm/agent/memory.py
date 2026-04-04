"""Player Memory 读写与摘要生成."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class PlayerMemory:
    """玩家长期记忆."""

    play_bias: Literal["aggressive", "defensive", "neutral"] = "neutral"
    recent_patterns: list[str] = field(default_factory=list)
    total_games: int = 0
    last_updated: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()

    @classmethod
    def from_json(cls, path: Path | str) -> PlayerMemory:
        """从 JSON 文件加载 memory."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_json(self, path: Path | str) -> None:
        """保存 memory 到 JSON 文件."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "play_bias": self.play_bias,
                    "recent_patterns": self.recent_patterns,
                    "total_games": self.total_games,
                    "last_updated": self.last_updated,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def load_memory(player_id: str, players_dir: Path | str = "configs/players") -> PlayerMemory:
    """加载指定玩家的 memory.

    Args:
        player_id: 玩家 ID
        players_dir: players 目录路径

    Returns:
        PlayerMemory（如果文件不存在返回默认空记忆）
    """
    players_path = Path(players_dir)
    memory_path = players_path / player_id / "memory.json"
    if not memory_path.exists():
        return PlayerMemory()
    return PlayerMemory.from_json(memory_path)


def save_memory(
    player_id: str,
    memory: PlayerMemory,
    players_dir: Path | str = "configs/players",
) -> None:
    """保存 memory 到文件."""
    players_path = Path(players_dir)
    memory_path = players_path / player_id / "memory.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory.to_json(memory_path)


@dataclass
class EpisodeStats:
    """单局统计（用于生成 memory 摘要）."""

    player_id: str
    seat: int
    # 和了统计
    wins: int = 0
    win_tiles: list[str] = field(default_factory=list)
    # 放铳统计
    deal_ins: int = 0
    deal_in_tiles: list[str] = field(default_factory=list)
    # 立直统计
    riichi_count: int = 0
    riichi_win: int = 0  # 立直后和了次数
    riichi_deal_in: int = 0  # 立直后放铳次数
    # 鸣牌统计
    call_count: int = 0
    # 打点
    total_points: int = 0
    # 局数
    hands_played: int = 0


class EpisodeSummarizer:
    """基于统计生成 memory 摘要."""

    def __init__(self, max_patterns: int = 5):
        self.max_patterns = max_patterns

    def summarize(
        self,
        stats: EpisodeStats,
        current_memory: PlayerMemory,
    ) -> PlayerMemory:
        """根据本局统计和当前记忆生成新记忆."""
        new_patterns = []

        # 规则 1: 放铳 -> 建议防守
        if stats.deal_ins > 0:
            new_patterns.append("本局有放铳，注意防守")

        # 规则 2: 立直后放铳 -> 立直选择需更谨慎
        if stats.riichi_deal_in > 0:
            new_patterns.append("立直后放铳，需评估立直时机")

        # 规则 3: 立直成功率高 -> 可以更积极
        if stats.riichi_count > 0 and stats.riichi_win >= stats.riichi_count // 2:
            new_patterns.append("立直成功率较高，可保持积极性")

        # 规则 4: 多次未和了 -> 注意一向听处理
        if stats.hands_played >= 1 and stats.wins == 0:
            new_patterns.append("本局未和了，注意一向听处理")

        # 计算 play_bias
        if stats.deal_ins >= 2:
            play_bias = "defensive"
        elif stats.wins >= 1:
            play_bias = "aggressive"
        else:
            play_bias = current_memory.play_bias

        # 合并 patterns（保留最近 N 条）
        all_patterns = new_patterns + current_memory.recent_patterns
        all_patterns = all_patterns[: self.max_patterns]

        return PlayerMemory(
            play_bias=play_bias,
            recent_patterns=all_patterns,
            total_games=current_memory.total_games + 1,
            last_updated=datetime.now().isoformat(),
        )


def format_memory_for_prompt(memory: PlayerMemory) -> str:
    """将 memory 格式化为 prompt 文本."""
    if not memory.recent_patterns and memory.play_bias == "neutral":
        return ""

    sections = []
    if memory.play_bias != "neutral":
        bias_desc = {
            "aggressive": "偏向进攻",
            "defensive": "偏向防守",
        }.get(memory.play_bias, memory.play_bias)
        sections.append(f"整体风格: {bias_desc}")

    if memory.recent_patterns:
        sections.append("近期总结:")
        for p in memory.recent_patterns:
            sections.append(f"  - {p}")

    return "\n".join(sections)
