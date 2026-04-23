"""PromptProjector - 显式上下文投影组件."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from llm.agent.context_store import PersistentState, TurnContext
from llm.agent.prompt_builder import (
    build_compressed_decision_prompt,
    build_decision_prompt,
    build_delta_decision_prompt,
    build_system_prompt,
)
from llm.agent.session import LocalContextPolicy
from llm.agent.token_budget import (
    PromptBlock,
    PromptBlockVariant,
    PromptBudgetConfig,
    PromptBudgetPlanner,
    PromptDiagnostics,
    TokenEstimateService,
)

if TYPE_CHECKING:
    from llm.agent.context import EpisodeContext
    from llm.agent.context_store import CompressionLevel
    from llm.agent.profile import PlayerProfile
    from llm.protocol import ChatMessage

ProjectionMode = Literal["natural", "json"]

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PromptProjection:
    """Projected chat messages plus token diagnostics."""

    messages: list["ChatMessage"]
    diagnostics: PromptDiagnostics


class PromptProjector:
    """将结构化上下文投影为发送给 LLM 的消息。"""

    def __init__(
        self,
        profile: "PlayerProfile",
        *,
        prompt_mode: ProjectionMode,
        context_scope: str,
        use_delta: bool,
        history_budget: int,
        compression_level: "CompressionLevel",
        context_budget_tokens: int,
        reserved_output_tokens: int,
        safety_margin_tokens: int,
        system_prompt_base: str | None = None,
    ) -> None:
        self.profile = profile
        self.system_prompt_base = system_prompt_base
        self.prompt_mode = prompt_mode
        self.context_policy = LocalContextPolicy(scope=context_scope)
        self.use_delta = use_delta
        self.history_budget = max(0, history_budget)
        self.compression_level = compression_level
        self.archive_budget = 0
        if self.history_budget > 0:
            self.archive_budget = max(1, min(4, max(1, self.history_budget // 3)))
        self._estimator = TokenEstimateService()
        self._planner = PromptBudgetPlanner(
            PromptBudgetConfig(
                context_budget_tokens=context_budget_tokens,
                reserved_output_tokens=reserved_output_tokens,
                safety_margin_tokens=safety_margin_tokens,
            ),
            estimator=self._estimator,
        )

    def build_projection(
        self,
        turn_context: TurnContext,
        *,
        persistent_state: PersistentState,
        episode_ctx: "EpisodeContext",
        should_send_keyframe: bool = True,
    ) -> PromptProjection:
        """构建完整消息列表。"""
        from llm.protocol import ChatMessage

        system_content = build_system_prompt(
            self.profile,
            persistent_state.memory,
            persistent_state.stats,
            self.system_prompt_base,
        )
        user_content = self._build_user_prompt(
            turn_context,
            episode_ctx=episode_ctx,
            should_send_keyframe=should_send_keyframe,
        )
        window = self.context_policy.build_window()
        blocks = self._build_prompt_blocks(
            system_content=system_content,
            user_content=user_content,
            episode_ctx=episode_ctx,
            include_match_archive=window.include_match_archive,
            include_public_history=window.include_public_history,
            include_self_history=window.include_self_history,
        )
        plan = self._planner.plan(blocks)
        if plan.diagnostics is None:
            raise RuntimeError("prompt budget planner did not produce diagnostics")
        if plan.estimated_tokens > plan.prompt_budget_tokens:
            log.warning(
                "prompt over budget after compression seat=%s estimated=%s budget=%s",
                episode_ctx.seat,
                plan.estimated_tokens,
                plan.prompt_budget_tokens,
            )
        messages = [ChatMessage(role=block.role, content=block.text) for block in plan.blocks]
        return PromptProjection(messages=messages, diagnostics=plan.diagnostics)

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

    def _build_prompt_blocks(
        self,
        *,
        system_content: str,
        user_content: str,
        episode_ctx: "EpisodeContext",
        include_match_archive: bool,
        include_public_history: bool,
        include_self_history: bool,
    ) -> list[PromptBlock]:
        blocks: list[PromptBlock] = [
            PromptBlock(
                block_id="system",
                role="system",
                priority=0,
                required=True,
                variants=(PromptBlockVariant("full", system_content),),
            )
        ]

        if include_match_archive:
            archive_variants = self._build_archive_variants(episode_ctx)
            if archive_variants:
                blocks.append(
                    PromptBlock(
                        block_id="match_archive",
                        role="user",
                        priority=90,
                        required=False,
                        variants=archive_variants,
                    )
                )

        if include_public_history:
            public_variants = self._build_public_history_variants(episode_ctx)
            if public_variants:
                blocks.append(
                    PromptBlock(
                        block_id="public_history",
                        role="user",
                        priority=30,
                        required=False,
                        variants=public_variants,
                    )
                )

        if include_self_history:
            self_variants = self._build_self_history_variants(episode_ctx)
            if self_variants:
                blocks.append(
                    PromptBlock(
                        block_id="self_history",
                        role="user",
                        priority=60,
                        required=False,
                        variants=self_variants,
                    )
                )

        blocks.append(
            PromptBlock(
                block_id="current_turn",
                role="user",
                priority=0,
                required=True,
                variants=(PromptBlockVariant("full", user_content),),
            )
        )
        return blocks

    def _build_archive_variants(
        self,
        episode_ctx: "EpisodeContext",
    ) -> tuple[PromptBlockVariant, ...]:
        allowed = self._allowed_states()
        variants: list[PromptBlockVariant] = []
        for state in allowed:
            compression = self._state_to_compression(state)
            body = episode_ctx.project_match_history(
                archive_budget=self.archive_budget,
                compression_level=compression,
            )
            text = self._wrap_block("本场前情摘要", body)
            if text:
                variants.append(PromptBlockVariant(state, text))
        return self._dedupe_variants(variants)

    def _build_public_history_variants(
        self,
        episode_ctx: "EpisodeContext",
    ) -> tuple[PromptBlockVariant, ...]:
        allowed = self._allowed_states()
        variants: list[PromptBlockVariant] = []
        detailed = self.prompt_mode == "natural"
        header = "本局公共事件"
        for state in allowed:
            compression = self._state_to_compression(state)
            body = episode_ctx.project_public_history(
                detailed=detailed,
                history_budget=self.history_budget,
                compression_level=compression,
            )
            text = self._wrap_block(header, body)
            if text:
                variants.append(PromptBlockVariant(state, text))
        return self._dedupe_variants(variants)

    def _build_self_history_variants(
        self,
        episode_ctx: "EpisodeContext",
    ) -> tuple[PromptBlockVariant, ...]:
        allowed = self._allowed_states()
        variants: list[PromptBlockVariant] = []
        detailed = self.prompt_mode == "natural"
        header = "本局我的决策历史"
        for state in allowed:
            compression = self._state_to_compression(state)
            body = episode_ctx.project_history(
                detailed=detailed,
                history_budget=self.history_budget,
                compression_level=compression,
            )
            text = self._wrap_block(header, body)
            if text:
                variants.append(PromptBlockVariant(state, text))
        return self._dedupe_variants(variants)

    def _allowed_states(self) -> tuple[str, ...]:
        order = ("full", "snip", "micro", "collapse", "autocompact")
        cutoff = {
            "none": 0,
            "snip": 1,
            "micro": 2,
            "collapse": 3,
            "autocompact": 4,
        }[self.compression_level]
        return order[: cutoff + 1]

    def _state_to_compression(self, state: str) -> "CompressionLevel":
        mapping = {
            "full": "none",
            "snip": "snip",
            "micro": "micro",
            "collapse": "collapse",
            "autocompact": "autocompact",
        }
        return mapping[state]

    def _wrap_block(self, header: str, body: str) -> str:
        if not body:
            return ""
        return f"{header}：\n{body}\n---"

    def _dedupe_variants(
        self,
        variants: list[PromptBlockVariant],
    ) -> tuple[PromptBlockVariant, ...]:
        deduped: list[PromptBlockVariant] = []
        seen_texts: set[str] = set()
        for variant in variants:
            if not variant.text or variant.text in seen_texts:
                continue
            seen_texts.add(variant.text)
            deduped.append(variant)
        return tuple(deduped)
