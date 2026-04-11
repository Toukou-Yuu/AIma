"""PromptBuilder - Prompt 构建组件.

职责：
- 构建 system prompt（整合 profile/memory/stats）
- 构建 user prompt（observation + legal_actions）
- 选择帧类型（keyframe vs delta）
- 注入历史文本
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm.agent.prompt_builder import (
    build_compressed_decision_prompt,
    build_decision_prompt,
    build_delta_decision_prompt,
    build_system_prompt,
)

if TYPE_CHECKING:
    from collections import Counter

    from kernel.api.legal_actions import LegalAction
    from kernel.api.observation import Observation
    from kernel.tiles.model import Tile
    from llm.agent.memory import PlayerMemory
    from llm.agent.profile import PlayerProfile
    from llm.agent.stats import PlayerStats
    from llm.protocol import ChatMessage

log = logging.getLogger(__name__)


class PromptBuilder:
    """Prompt 构建组件.

    负责将所有信息整合成完整的消息列表，供 LLM 调用使用。
    """

    def __init__(
        self,
        profile: "PlayerProfile",
        memory: "PlayerMemory",
        stats: "PlayerStats",
        system_prompt_base: str | None = None,
        use_compression: bool = True,
        use_delta: bool = True,
    ) -> None:
        """初始化 Prompt 构建器.

        Args:
            profile: 玩家 profile
            memory: 玩家 memory
            stats: 玩家 stats
            system_prompt_base: 基础系统提示词（从配置文件读取）
            use_compression: 是否启用压缩格式
            use_delta: 是否启用 delta 帧优化
        """
        self.profile = profile
        self.memory = memory
        self.stats = stats
        self.system_prompt_base = system_prompt_base
        self.use_compression = use_compression
        self.use_delta = use_delta

    def build_messages(
        self,
        observation: "Observation",
        legal_actions: tuple["LegalAction", ...],
        history_text: str | None = None,
        last_observation: "Observation | None" = None,
        last_hand: "Counter[Tile] | None" = None,
        should_send_keyframe: bool = True,
    ) -> list["ChatMessage"]:
        """构建完整的消息列表.

        Args:
            observation: 当前局面观测
            legal_actions: 合法动作列表
            history_text: 本局历史文本（可选）
            last_observation: 上一帧观测（用于 delta 帧）
            last_hand: 上一帧手牌（用于 delta 帧）
            should_send_keyframe: 是否发送关键帧

        Returns:
            消息列表（system + history + user）
        """
        from llm.protocol import ChatMessage

        messages: list[ChatMessage] = []

        # 1. System prompt
        system_content = build_system_prompt(
            self.profile,
            self.memory,
            self.stats,
            self.system_prompt_base,
        )
        messages.append(ChatMessage(role="system", content=system_content))

        # 2. History（如果有）
        if history_text:
            history_header = "本局关键事件" if self.use_compression else "本局前期决策历史"
            history_msg = ChatMessage(
                role="user",
                content=f"{history_header}：\n{history_text}\n---",
            )
            messages.append(history_msg)

        # 3. User prompt（根据帧类型选择）
        user_content = self._build_user_prompt(
            observation,
            legal_actions,
            last_observation,
            last_hand,
            should_send_keyframe,
        )
        messages.append(ChatMessage(role="user", content=user_content))

        return messages

    def _build_user_prompt(
        self,
        observation: "Observation",
        legal_actions: tuple["LegalAction", ...],
        last_observation: "Observation | None",
        last_hand: "Counter[Tile] | None",
        should_send_keyframe: bool,
    ) -> str:
        """构建 user prompt.

        Args:
            observation: 当前局面观测
            legal_actions: 合法动作列表
            last_observation: 上一帧观测
            last_hand: 上一帧手牌
            should_send_keyframe: 是否发送关键帧

        Returns:
            User prompt 内容
        """
        # Delta 帧优化
        if self.use_delta and not should_send_keyframe and last_observation is not None:
            from llm.observation_format import build_delta_observation

            delta_obs = build_delta_observation(observation, last_observation, last_hand)
            return build_delta_decision_prompt(delta_obs, legal_actions)

        # 关键帧
        if self.use_compression:
            return build_compressed_decision_prompt(observation, legal_actions)
        else:
            return build_decision_prompt(observation, legal_actions)

    def get_frame_type(
        self,
        should_send_keyframe: bool,
    ) -> str:
        """获取当前帧类型.

        Args:
            should_send_keyframe: 是否发送关键帧

        Returns:
            "keyframe" 或 "delta"
        """
        if self.use_delta and not should_send_keyframe:
            return "delta"
        return "keyframe"