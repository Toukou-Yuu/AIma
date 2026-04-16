"""PromptProjector - 显式上下文投影组件."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from llm.agent.context_store import PersistentState, TurnContext
from llm.agent.prompt_builder import (
    build_compressed_decision_prompt,
    build_decision_prompt,
    build_delta_decision_prompt,
    build_system_prompt,
)

if TYPE_CHECKING:
    from llm.agent.context import EpisodeContext
    from llm.agent.context_store import CompressionLevel
    from llm.agent.profile import PlayerProfile
    from llm.protocol import ChatMessage

ProjectionMode = Literal["natural", "json"]

log = logging.getLogger(__name__)


class PromptProjector:
    """将结构化上下文投影为发送给 LLM 的消息。"""

    def __init__(
        self,
        profile: "PlayerProfile",
        *,
        system_prompt_base: str | None = None,
        prompt_mode: ProjectionMode = "natural",
        use_delta: bool = True,
        history_budget: int = 10,
        compression_level: "CompressionLevel" = "collapse",
    ) -> None:
        self.profile = profile
        self.system_prompt_base = system_prompt_base
        self.prompt_mode = prompt_mode
        self.use_delta = use_delta
        self.history_budget = max(0, history_budget)
        self.compression_level = compression_level

    def build_messages(
        self,
        turn_context: TurnContext,
        *,
        persistent_state: PersistentState,
        episode_ctx: "EpisodeContext",
        should_send_keyframe: bool = True,
    ) -> list["ChatMessage"]:
        """构建完整消息列表。"""
        from llm.protocol import ChatMessage

        messages: list[ChatMessage] = []

        system_content = build_system_prompt(
            self.profile,
            persistent_state.memory,
            persistent_state.stats,
            self.system_prompt_base,
        )
        messages.append(ChatMessage(role="system", content=system_content))

        history_text = episode_ctx.project_history(
            detailed=self.prompt_mode == "natural",
            history_budget=self.history_budget,
            compression_level=self.compression_level,
        )
        if history_text:
            header = "本局关键事件" if self.prompt_mode == "json" else "本局历史摘要"
            messages.append(
                ChatMessage(
                    role="user",
                    content=f"{header}：\n{history_text}\n---",
                )
            )

        user_content = self._build_user_prompt(
            turn_context,
            episode_ctx=episode_ctx,
            should_send_keyframe=should_send_keyframe,
        )
        messages.append(ChatMessage(role="user", content=user_content))
        return messages

    def _build_user_prompt(
        self,
        turn_context: TurnContext,
        *,
        episode_ctx: "EpisodeContext",
        should_send_keyframe: bool,
    ) -> str:
        """构建当前回合的 user prompt。"""
        observation = turn_context.observation
        legal_actions = turn_context.legal_actions

        if self._should_use_delta(episode_ctx, should_send_keyframe):
            from llm.observation_format import build_delta_observation

            delta_obs = build_delta_observation(
                observation,
                episode_ctx.last_observation,
                episode_ctx.last_hand,
            )
            return build_delta_decision_prompt(delta_obs, legal_actions)

        if self.prompt_mode == "json":
            return build_compressed_decision_prompt(observation, legal_actions)
        return build_decision_prompt(observation, legal_actions)

    def get_frame_type(
        self,
        episode_ctx: "EpisodeContext",
        should_send_keyframe: bool,
    ) -> str:
        """返回当前投影帧类型。"""
        if self._should_use_delta(episode_ctx, should_send_keyframe):
            return "delta"
        return "keyframe"

    def _should_use_delta(
        self,
        episode_ctx: "EpisodeContext",
        should_send_keyframe: bool,
    ) -> bool:
        """仅 JSON 模式允许 delta 帧。"""
        return (
            self.prompt_mode == "json"
            and self.use_delta
            and not should_send_keyframe
            and episode_ctx.last_observation is not None
        )
