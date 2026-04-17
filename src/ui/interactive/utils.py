"""交互式终端工具函数与常量."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


PLAYERS_DIR = Path("configs/players")
KERNEL_CONFIG_PATH = Path("configs/aima_kernel.yaml")
_INTERNAL_PROFILE_IDS = {"default"}


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


def list_profiles() -> list[dict[str, Any]]:
    """扫描 configs/players 目录，返回所有角色配置."""
    profiles = []
    if not PLAYERS_DIR.exists():
        return profiles

    for player_dir in sorted(PLAYERS_DIR.iterdir()):
        if not player_dir.is_dir():
            continue
        if player_dir.name in _INTERNAL_PROFILE_IDS:
            continue
        profile_path = player_dir / "profile.json"
        if profile_path.exists():
            try:
                data = json.loads(profile_path.read_text(encoding="utf-8"))
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


def load_profile_data(player_id: str) -> dict[str, Any] | None:
    """加载角色配置数据."""
    profile_path = PLAYERS_DIR / player_id / "profile.json"
    if not profile_path.exists():
        return None
    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_profile_stats(player_id: str) -> dict[str, Any] | None:
    """加载角色统计数据."""
    stats_path = PLAYERS_DIR / player_id / "stats.json"
    if not stats_path.exists():
        return None
    try:
        return json.loads(stats_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def create_profile(
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
    default_profile_path = PLAYERS_DIR / "default" / "profile.json"
    if not default_profile_path.exists():
        raise FileNotFoundError(f"缺少默认 profile 模板: {default_profile_path}")
    default_profile = json.loads(default_profile_path.read_text(encoding="utf-8"))

    profile = {
        "id": player_id,
        "name": name,
        "model": default_profile["model"],
        "provider": default_profile["provider"],
        "temperature": default_profile["temperature"],
        "max_tokens": default_profile["max_tokens"],
        "timeout_sec": default_profile["timeout_sec"],
        "persona_prompt": persona,
        "strategy_prompt": strategy,
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


def truncate_text(text: str, max_len: int) -> str:
    """智能截断文本，超过长度才添加省略号."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
