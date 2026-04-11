"""Player Stats 读写与统计计算."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class PlayerStats:
    """玩家长期统计."""

    # 基础统计
    total_games: int = 0
    total_hands: int = 0
    wins: int = 0
    deal_ins: int = 0
    riichi_count: int = 0
    riichi_wins: int = 0
    riichi_deal_ins: int = 0
    total_points: int = 0

    # 顺位统计
    first_place_count: int = 0
    second_place_count: int = 0
    third_place_count: int = 0
    fourth_place_count: int = 0

    # 元数据
    last_updated: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()

    @classmethod
    def from_json(cls, path: Path | str) -> PlayerStats:
        """从 JSON 文件加载 stats."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_json(self, path: Path | str) -> None:
        """保存 stats 到 JSON 文件."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "total_games": self.total_games,
                    "total_hands": self.total_hands,
                    "wins": self.wins,
                    "deal_ins": self.deal_ins,
                    "riichi_count": self.riichi_count,
                    "riichi_wins": self.riichi_wins,
                    "riichi_deal_ins": self.riichi_deal_ins,
                    "total_points": self.total_points,
                    "first_place_count": self.first_place_count,
                    "second_place_count": self.second_place_count,
                    "third_place_count": self.third_place_count,
                    "fourth_place_count": self.fourth_place_count,
                    "last_updated": self.last_updated,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    # 派生指标（计算属性）
    @property
    def win_rate(self) -> float:
        """和了率."""
        return self.wins / self.total_hands if self.total_hands > 0 else 0.0

    @property
    def deal_in_rate(self) -> float:
        """放铳率."""
        return self.deal_ins / self.total_hands if self.total_hands > 0 else 0.0

    @property
    def riichi_rate(self) -> float:
        """立直率."""
        return self.riichi_count / self.total_hands if self.total_hands > 0 else 0.0

    @property
    def riichi_success_rate(self) -> float:
        """立直成功率."""
        return self.riichi_wins / self.riichi_count if self.riichi_count > 0 else 0.0

    @property
    def riichi_deal_in_rate(self) -> float:
        """立直后放铳率."""
        return self.riichi_deal_ins / self.riichi_count if self.riichi_count > 0 else 0.0

    @property
    def avg_placement(self) -> float:
        """平均顺位."""
        total = (
            self.first_place_count * 1
            + self.second_place_count * 2
            + self.third_place_count * 3
            + self.fourth_place_count * 4
        )
        games = self.first_place_count + self.second_place_count + self.third_place_count + self.fourth_place_count
        return total / games if games > 0 else 0.0

    @property
    def avg_points_per_game(self) -> float:
        """场均得点."""
        return self.total_points / self.total_games if self.total_games > 0 else 0.0


def load_stats(player_id: str, players_dir: Path | str = "configs/players") -> PlayerStats:
    """加载指定玩家的 stats.

    Args:
        player_id: 玩家 ID
        players_dir: players 目录路径

    Returns:
        PlayerStats（如果文件不存在返回默认空统计）
    """
    players_path = Path(players_dir)
    stats_path = players_path / player_id / "stats.json"
    if not stats_path.exists():
        return PlayerStats()
    return PlayerStats.from_json(stats_path)


def save_stats(
    player_id: str,
    stats: PlayerStats,
    players_dir: Path | str = "configs/players",
) -> None:
    """保存 stats 到文件."""
    players_path = Path(players_dir)
    stats_path = players_path / player_id / "stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats.to_json(stats_path)


@dataclass
class MatchStats:
    """单局统计（用于更新 PlayerStats）."""

    wins: int = 0
    deal_ins: int = 0
    riichi_count: int = 0
    riichi_wins: int = 0
    riichi_deal_ins: int = 0
    points: int = 0
    hands: int = 0
    placement: int = 0  # 1-4

    def copy(self) -> "MatchStats":
        """创建副本（用于状态隔离）."""
        return MatchStats(
            wins=self.wins,
            deal_ins=self.deal_ins,
            riichi_count=self.riichi_count,
            riichi_wins=self.riichi_wins,
            riichi_deal_ins=self.riichi_deal_ins,
            points=self.points,
            hands=self.hands,
            placement=self.placement,
        )


class StatsAggregator:
    """聚合单局统计到长期统计."""

    def update(
        self,
        current_stats: PlayerStats,
        match_stats: MatchStats,
    ) -> PlayerStats:
        """根据单局统计更新长期统计."""
        return PlayerStats(
            total_games=current_stats.total_games + 1,
            total_hands=current_stats.total_hands + match_stats.hands,
            wins=current_stats.wins + match_stats.wins,
            deal_ins=current_stats.deal_ins + match_stats.deal_ins,
            riichi_count=current_stats.riichi_count + match_stats.riichi_count,
            riichi_wins=current_stats.riichi_wins + match_stats.riichi_wins,
            riichi_deal_ins=current_stats.riichi_deal_ins + match_stats.riichi_deal_ins,
            total_points=current_stats.total_points + match_stats.points,
            first_place_count=current_stats.first_place_count + (1 if match_stats.placement == 1 else 0),
            second_place_count=current_stats.second_place_count + (1 if match_stats.placement == 2 else 0),
            third_place_count=current_stats.third_place_count + (1 if match_stats.placement == 3 else 0),
            fourth_place_count=current_stats.fourth_place_count + (1 if match_stats.placement == 4 else 0),
            last_updated=datetime.now().isoformat(),
        )


def format_stats_for_prompt(stats: PlayerStats) -> str:
    """将 stats 格式化为 prompt 文本."""
    if stats.total_games == 0:
        return ""

    lines = [
        f"累计对局: {stats.total_games}场",
        f"和了率: {stats.win_rate:.1%}",
        f"放铳率: {stats.deal_in_rate:.1%}",
        f"立直率: {stats.riichi_rate:.1%}",
    ]

    if stats.riichi_count > 0:
        lines.append(f"立直成功率: {stats.riichi_success_rate:.1%}")

    lines.append(f"平均顺位: {stats.avg_placement:.1f}")

    return "\n".join(lines)
