"""Player Profile 读写与管理."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """玩家配置档案."""

    id: str
    name: str
    model: str
    provider: Literal["openai", "anthropic"] = "openai"
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout_sec: float = 120.0
    persona_prompt: str = ""
    strategy_prompt: str = ""

    @classmethod
    def from_json(cls, path: Path | str) -> PlayerProfile:
        """从 JSON 文件加载 profile."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_json(self, path: Path | str) -> None:
        """保存 profile 到 JSON 文件."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": self.id,
                    "name": self.name,
                    "model": self.model,
                    "provider": self.provider,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "timeout_sec": self.timeout_sec,
                    "persona_prompt": self.persona_prompt,
                    "strategy_prompt": self.strategy_prompt,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def load_profile(player_id: str, players_dir: Path | str = "configs/players") -> PlayerProfile | None:
    """加载指定玩家的 profile.

    Args:
        player_id: 玩家 ID
        players_dir: players 目录路径（默认 configs/players）

    Returns:
        PlayerProfile 或 None（如果文件不存在）
    """
    players_path = Path(players_dir)
    profile_path = players_path / player_id / "profile.json"
    if not profile_path.exists():
        return None
    return PlayerProfile.from_json(profile_path)


def list_players(players_dir: Path | str = "configs/players") -> list[str]:
    """列出所有可用的 player_id."""
    players_path = Path(players_dir)
    if not players_path.exists():
        return []
    return [
        d.name for d in players_path.iterdir()
        if d.is_dir() and (d / "profile.json").exists()
    ]
