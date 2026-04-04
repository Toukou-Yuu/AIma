"""Prompt 拼装 - 整合 persona + observation + legal_actions.

Phase 3: 支持从 memory 注入历史表现.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation
from llm.observation_format import SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from llm.agent.memory import PlayerMemory
    from llm.agent.profile import PlayerProfile


def build_system_prompt(
    profile: PlayerProfile | None = None,
    memory: PlayerMemory | None = None,
) -> str:
    """构建系统提示.

    整合 SYSTEM_PROMPT + persona + strategy + memory.

    Args:
        profile: 玩家配置（包含 persona_prompt 和 strategy_prompt）
        memory: 玩家记忆（包含 play_bias 和 recent_patterns）

    Returns:
        系统提示字符串
    """
    sections = [SYSTEM_PROMPT]

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
