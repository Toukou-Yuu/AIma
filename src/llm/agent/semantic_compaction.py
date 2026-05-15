"""Semantic compaction for prompt history compression."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from llm.agent.context_compactor import ContextCompactor

if TYPE_CHECKING:
    from llm.agent.context import EpisodeContext
    from llm.agent.context_store import CompressionLevel
    from llm.agent.message_ledger import LedgerMessage
    from llm.agent.token_budget import PromptPlan
    from llm.protocol import CompletionClient

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SemanticCompactionResult:
    """Result of semantic compaction."""

    should_compact: bool
    compacted_history: list["LedgerMessage"]


class SemanticCompactor:
    """判断并执行语义压缩。"""

    def __init__(
        self,
        *,
        compression_level: "CompressionLevel",
        prompt_budget_tokens: int,
    ) -> None:
        self.compression_level = compression_level
        self.prompt_budget_tokens = prompt_budget_tokens
        self._compactor = ContextCompactor()

    def should_compact(
        self,
        plan: "PromptPlan",
        compaction_client: "CompletionClient | None",
    ) -> bool:
        """判断是否需要语义压缩。"""
        if self.compression_level != "autocompact":
            return False
        if compaction_client is None or plan.diagnostics is None:
            return False
        if plan.diagnostics.over_budget:
            return True
        return any(block_id.startswith("turn_") for block_id in plan.diagnostics.trimmed_blocks)

    def compact_history(
        self,
        episode_ctx: "EpisodeContext",
        *,
        compaction_client: "CompletionClient | None",
    ) -> list["LedgerMessage"]:
        """构建语义压缩后的历史。"""
        if compaction_client is None:
            return []
        turn_indexes = episode_ctx.message_ledger.turn_indexes()
        if len(turn_indexes) <= 2:
            return []

        recent_turns = set(turn_indexes[-2:])
        older_turns = set(turn_indexes[:-2])
        older_messages = episode_ctx.message_ledger.messages_for_turns(older_turns)
        recent_messages = episode_ctx.message_ledger.messages_for_turns(recent_turns)
        target_tokens = max(128, self.prompt_budget_tokens // 5)
        summary = self._compactor.compact(
            client=compaction_client,
            messages=older_messages,
            hand_number=episode_ctx.hand_number,
            target_tokens=target_tokens,
        )
        if summary is None:
            return []
        return [summary, *recent_messages]

    def compact_if_needed(
        self,
        plan: "PromptPlan",
        episode_ctx: "EpisodeContext",
        *,
        compaction_client: "CompletionClient | None",
    ) -> SemanticCompactionResult:
        """按需执行语义压缩。"""
        if not self.should_compact(plan, compaction_client):
            return SemanticCompactionResult(should_compact=False, compacted_history=[])
        compacted = self.compact_history(episode_ctx, compaction_client=compaction_client)
        return SemanticCompactionResult(should_compact=True, compacted_history=compacted)