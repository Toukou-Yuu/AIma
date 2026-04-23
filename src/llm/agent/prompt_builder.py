"""Prompt 拼装 - 整合 persona + observation + legal_actions.

Phase 4: 支持从 stats 注入统计数据.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation
from llm.observation_format import build_user_prompt
from llm.wire import legal_action_to_wire

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
    from llm.wire import legal_action_to_wire

    compressed_obs = build_compressed_observation(observation)
    body = {
        "observation": compressed_obs,
        "legal_actions": [legal_action_to_wire(la) for la in legal_actions],
    }
    # 添加输出格式说明（json 格式专用）
    format_hint = (
        "\n\n【输出要求】选择 legal_actions 中的一项，用 JSON 输出，含 why 字段。"
        "\n示例: {\"kind\":\"discard\",\"seat\":0,\"tile\":\"3m\",\"why\":\"现物安全\"}"
    )
    return json.dumps(body, ensure_ascii=False, indent=2) + format_hint


def build_delta_decision_prompt(
    delta_obs: dict[str, Any],
    legal_actions: tuple[LegalAction, ...],
) -> str:
    """构建变化帧决策提示（用户消息）.

    Phase 2: 只发送变化信息，大幅减少 token.

    Args:
        delta_obs: 变化帧观测（由 build_delta_observation 生成）
        legal_actions: 合法动作列表

    Returns:
        用户提示字符串（JSON 格式）
    """
    from llm.wire import legal_action_to_wire

    body = {
        "frame_type": "delta",
        "delta": delta_obs,
        "legal_actions": [legal_action_to_wire(la) for la in legal_actions],
    }
    # 添加输出格式说明（json 格式专用）
    format_hint = (
        "\n\n【输出要求】选择 legal_actions 中的一项，用 JSON 输出，含 why 字段。"
        "\n示例: {\"kind\":\"discard\",\"seat\":0,\"tile\":\"3m\",\"why\":\"现物安全\"}"
    )
    return json.dumps(body, ensure_ascii=False, indent=2) + format_hint


def build_turn_state_message(
    *,
    base_prompt: str,
    public_summary: str = "",
) -> str:
    """Build the user turn-state message appended to the local ledger."""
    sections: list[str] = []
    if public_summary:
        sections.append("【公开事件摘要】")
        sections.append(public_summary)
    sections.append("【当前决策】")
    sections.append(base_prompt)
    return "\n\n".join(sections)


def build_assistant_turn_message(
    action,
    why: str | None,
) -> str:
    """Build the canonical assistant reply stored in the local ledger."""
    payload: dict[str, Any] = {
        "action": legal_action_to_wire(action),
        "why": why or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
