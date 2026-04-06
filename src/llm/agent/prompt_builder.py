"""Prompt 拼装 - 整合 persona + observation + legal_actions.

Phase 4: 支持从 stats 注入统计数据.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation
from llm.observation_format import build_user_prompt

if TYPE_CHECKING:
    from llm.agent.memory import PlayerMemory
    from llm.agent.profile import PlayerProfile
    from llm.agent.stats import PlayerStats


def build_system_prompt(
    profile: PlayerProfile | None = None,
    memory: PlayerMemory | None = None,
    stats: PlayerStats | None = None,
    system_prompt: str | None = None,
) -> str:
    """构建系统提示.

    整合 system_prompt + persona + strategy + memory + stats.

    Args:
        profile: 玩家配置（包含 persona_prompt 和 strategy_prompt）
        memory: 玩家记忆（包含 play_bias 和 recent_patterns）
        stats: 玩家统计（包含胜率、放铳率等）
        system_prompt: 基础系统提示词（从配置文件读取）

    Returns:
        系统提示字符串

    Raises:
        ValueError: 当未提供 system_prompt 时
    """
    if system_prompt is None:
        raise ValueError(
            "未配置 system_prompt。请在 configs/aima_kernel.yaml 的 llm 部分 "
            "添加 system_prompt 配置，或参考 configs/aima_kernel_template.yaml"
        )

    sections = [system_prompt]

    if profile and profile.persona_prompt:
        sections.append(f"\n【人格】\n{profile.persona_prompt}")

    if profile and profile.strategy_prompt:
        sections.append(f"\n【策略】\n{profile.strategy_prompt}")

    # Phase 3: 注入 memory
    if memory:
        from llm.agent.memory import format_memory_for_prompt
        memory_text = format_memory_for_prompt(memory)
        if memory_text:
            sections.append(f"\n【历史表现】\n{memory_text}")

    # Phase 4: 注入 stats
    if stats and stats.total_games > 0:
        from llm.agent.stats import format_stats_for_prompt
        stats_text = format_stats_for_prompt(stats)
        if stats_text:
            sections.append(f"\n【统计数据】\n{stats_text}")

    return "\n".join(sections)


def build_decision_prompt(
    observation: Observation,
    legal_actions: tuple[LegalAction, ...],
) -> str:
    """构建决策提示（用户消息）.

    复用 observation_format.py 的现有逻辑.

    Args:
        observation: 当前局面观测
        legal_actions: 合法动作列表

    Returns:
        用户提示字符串（JSON 格式）
    """
    return build_user_prompt(observation, legal_actions)


def build_compressed_decision_prompt(
    observation: Observation,
    legal_actions: tuple[LegalAction, ...],
) -> str:
    """构建压缩版决策提示（用户消息）.

    使用压缩观测减少 token 消耗.

    Args:
        observation: 当前局面观测
        legal_actions: 合法动作列表

    Returns:
        用户提示字符串（JSON 格式）
    """
    from llm.observation_format import build_compressed_observation

    compressed_obs = build_compressed_observation(observation)
    body = {
        "observation": compressed_obs,
        "legal_actions": [legal_action_to_wire(la) for la in legal_actions],
    }
    return json.dumps(body, ensure_ascii=False, indent=2)
