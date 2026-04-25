"""PromptProjector - 显式上下文投影组件."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from llm.agent.context_compactor import ContextCompactor
from llm.agent.context_store import PersistentState, TurnContext
from llm.agent.prompt_builder import (
    build_compressed_decision_prompt,
    build_decision_prompt,
    build_system_prompt,
    build_turn_state_message,
)
from llm.agent.session import LocalContextPolicy
from llm.agent.token_budget import (
    PromptBlock,
    PromptBlockVariant,
    PromptBudgetConfig,
    PromptBudgetPlanner,
    PromptDiagnostics,
    PromptPlan,
    TokenEstimateService,
)

if TYPE_CHECKING:
    from llm.agent.context import EpisodeContext
    from llm.agent.context_store import CompressionLevel
    from llm.agent.message_ledger import LedgerMessage
    from llm.agent.profile import PlayerProfile
    from llm.protocol import ChatMessage, CompletionClient

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
        history_budget: int,
        compression_level: "CompressionLevel",
        max_context_tokens: int,
        max_output_tokens: int,
        context_compression_threshold: float,
        system_prompt_base: str | None = None,
    ) -> None:
        self.profile = profile
        self.system_prompt_base = system_prompt_base
        self.prompt_mode = prompt_mode
        self.context_policy = LocalContextPolicy(scope=context_scope)
        self.history_budget = max(0, history_budget)
        self.compression_level = compression_level
        self.archive_budget = 0
        if self.history_budget > 0:
            self.archive_budget = max(1, min(4, max(1, self.history_budget // 3)))
        self._estimator = TokenEstimateService()
        self._planner = PromptBudgetPlanner(
            PromptBudgetConfig(
                max_context_tokens=max_context_tokens,
                max_output_tokens=max_output_tokens,
                context_compression_threshold=context_compression_threshold,
            ),
            estimator=self._estimator,
        )
        self._compactor = ContextCompactor()

    def build_projection(
        self,
        turn_context: TurnContext,
        *,
        persistent_state: PersistentState,
        episode_ctx: "EpisodeContext",
        compaction_client: "CompletionClient | None" = None,
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
        )
        window = self.context_policy.build_window()
        history_messages = []
        if window.include_public_history or window.include_self_history:
            history_messages = episode_ctx.project_message_history(
                history_budget=self.history_budget,
                compression_level=self.compression_level,
            )
        archive_content = ""
        if window.include_match_archive:
            archive_content = episode_ctx.project_match_history(
                archive_budget=self.archive_budget,
                compression_level=self.compression_level,
            )
        blocks = self._build_prompt_blocks(
            system_content=system_content,
            archive_content=archive_content,
            history_messages=history_messages,
            user_content=user_content,
        )
        plan = self._planner.plan(blocks)
        if plan.diagnostics is None:
            raise RuntimeError("prompt budget planner did not produce diagnostics")
        if self._should_semantic_compact(plan, compaction_client):
            compacted_history = self._build_semantic_compacted_history(
                episode_ctx,
                compaction_client=compaction_client,
            )
            if compacted_history:
                blocks = self._build_prompt_blocks(
                    system_content=system_content,
                    archive_content=archive_content,
                    history_messages=compacted_history,
                    user_content=user_content,
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

    def _should_semantic_compact(
        self,
        plan: PromptPlan,
        compaction_client: "CompletionClient | None",
    ) -> bool:
        if self.compression_level != "autocompact":
            return False
        if compaction_client is None or plan.diagnostics is None:
            return False
        if plan.diagnostics.over_budget:
            return True
        return any(block_id.startswith("turn_") for block_id in plan.diagnostics.trimmed_blocks)

    def _build_semantic_compacted_history(
        self,
        episode_ctx: "EpisodeContext",
        *,
        compaction_client: "CompletionClient | None",
    ) -> list["LedgerMessage"]:
        if compaction_client is None:
            return []
        turn_indexes = episode_ctx.message_ledger.turn_indexes()
        if len(turn_indexes) <= 2:
            return []

        recent_turns = set(turn_indexes[-2:])
        older_turns = set(turn_indexes[:-2])
        older_messages = episode_ctx.message_ledger.messages_for_turns(older_turns)
        recent_messages = episode_ctx.message_ledger.messages_for_turns(recent_turns)
        target_tokens = max(128, self._planner.config.prompt_budget_tokens // 5)
        summary = self._compactor.compact(
            client=compaction_client,
            messages=older_messages,
            hand_number=episode_ctx.hand_number,
            target_tokens=target_tokens,
        )
        if summary is None:
            return []
        return [summary, *recent_messages]

    def _build_user_prompt(
        self,
        turn_context: TurnContext,
        *,
        episode_ctx: "EpisodeContext",
    ) -> str:
        """构建当前回合的 user prompt。"""
        observation = turn_context.observation
        legal_actions = turn_context.legal_actions

        if self.prompt_mode == "json":
            base_prompt = build_compressed_decision_prompt(observation, legal_actions)
        else:
            base_prompt = build_decision_prompt(observation, legal_actions)

        public_summary = ""
        if self.context_policy.scope != "stateless":
            public_summary = episode_ctx.build_recent_public_summary(
                history_budget=max(1, min(self.history_budget, 6)),
                compression_level="micro"
                if self.compression_level in {"collapse", "autocompact"}
                else self.compression_level,
            )
        return build_turn_state_message(
            base_prompt=base_prompt,
            public_summary=public_summary,
        )

    def _build_prompt_blocks(
        self,
        *,
        system_content: str,
        archive_content: str,
        history_messages: list["LedgerMessage"],
        user_content: str,
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

        if archive_content:
            archive_variants = self._build_archive_variants(archive_content)
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

        total_history = len(history_messages)
        for index, message in enumerate(history_messages):
            blocks.append(
                PromptBlock(
                    block_id=message.message_id,
                    role=message.role,
                    priority=total_history - index,
                    required=False,
                    variants=(PromptBlockVariant(message.compression_state, message.content),),
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
        archive_content: str,
    ) -> tuple[PromptBlockVariant, ...]:
        text = self._wrap_block("本场前情摘要", archive_content)
        if not text:
            return ()
        return (PromptBlockVariant("full", text),)

    def _wrap_block(self, header: str, body: str) -> str:
        if not body:
            return ""
        return f"{header}：\n{body}\n---"
