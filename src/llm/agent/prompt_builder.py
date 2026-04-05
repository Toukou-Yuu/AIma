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
    """
    # 使用传入的 system_prompt 或默认提示词
    if system_prompt is None:
        # 默认提示词（硬编码后备）
        base_prompt = (
            "你是日式麻将（立直麻将）的牌手代理。你只能从给出的 legal_actions 中"
            "**精确选择一条**执行。\n"
            "\n"
            "【牌面编码说明】\n"
            "- 万子：1m-9m（如 1m=一万，5m=五万）\n"
            "- 筒子：1p-9p（如 1p=一筒，5p=五筒）\n"
            "- 索子：1s-9s（如 1s=一索，5s=五索）\n"
            "- 字牌：1z=東，2z=南，3z=西，4z=北，5z=白，6z=發，7z=中\n"
            "\n"
            "输出要求：仅输出一行 JSON 对象，不要 markdown 代码块，不要 JSON 以外的文字。\n"
            "JSON 中除下列动作字段外，**必须**包含字符串字段 ``why``："
            "用符合你人设的语气说明**为何**选这一手（不超过40字）。\n"
            "**重要**：`why` 字段必须体现你的人设性格，用角色特有的说话方式，禁止机械分析。\n"
            "动作字段必须与所选 legal_actions 中某一项完全一致"
            "（含 kind、seat；discard 须含 tile；需要时含 declare_riichi、meld）。\n"
            '示例：{"kind":"discard","seat":0,"tile":"3m","why":"现物且维持一向听"}\n'
            '示例：{"kind":"pass_call","seat":1,"why":"无役无法荣和"}'
        )
    else:
        base_prompt = system_prompt

    sections = [base_prompt]

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
