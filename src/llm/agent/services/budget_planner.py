"""Budget planning service for prompt blocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from llm.agent.models.budget_config import PromptBudgetConfig
from llm.agent.models.diagnostics import BlockTokenUsage, PromptDiagnostics
from llm.agent.models.prompt_block import (
    PromptBlock,
    SelectedPromptBlock,
    _COMPRESSION_ORDER,
)
from llm.agent.services.token_estimator import TokenEstimateService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, slots=True)
class PromptPlan:
    """Budget planning result."""

    blocks: tuple[SelectedPromptBlock, ...]
    estimated_tokens: int
    prompt_budget_tokens: int
    trimmed_blocks: tuple[str, ...] = ()
    diagnostics: PromptDiagnostics | None = None


class PromptBudgetPlanner:
    """Budget-aware selector for prompt blocks."""

    def __init__(
        self,
        config: PromptBudgetConfig,
        estimator: TokenEstimateService | None = None,
    ) -> None:
        self._config = config
        self._estimator = estimator or TokenEstimateService()

    @property
    def config(self) -> PromptBudgetConfig:
        """Return immutable budget config."""
        return self._config

    def plan(self, blocks: list[PromptBlock]) -> PromptPlan:
        """Choose block variants that fit within the configured prompt budget."""
        validated = [self._validate_block(block) for block in blocks]
        variant_indexes = [0 for _ in validated]
        dropped: list[str] = []

        total = self._estimate_total(validated, variant_indexes)
        if total <= self._config.prompt_budget_tokens:
            return self._build_plan(validated, variant_indexes, dropped)

        order = self._compression_order(validated)
        while total > self._config.prompt_budget_tokens:
            progressed = False
            for idx in order:
                if variant_indexes[idx] < 0:
                    continue
                block = validated[idx]
                if variant_indexes[idx] + 1 >= len(block.variants):
                    continue
                variant_indexes[idx] += 1
                total = self._estimate_total(validated, variant_indexes)
                progressed = True
                if total <= self._config.prompt_budget_tokens:
                    return self._build_plan(validated, variant_indexes, dropped)
            if not progressed:
                break

        for idx in order:
            if total <= self._config.prompt_budget_tokens:
                break
            block = validated[idx]
            if block.required or variant_indexes[idx] < 0:
                continue
            variant_indexes[idx] = -1
            dropped.append(block.block_id)
            total = self._estimate_total(validated, variant_indexes)

        return self._build_plan(validated, variant_indexes, dropped)

    def _validate_block(self, block: PromptBlock) -> PromptBlock:
        block.validate()
        return block

    def _compression_order(self, blocks: list[PromptBlock]) -> list[int]:
        optional = [i for i, block in enumerate(blocks) if not block.required]
        required = [i for i, block in enumerate(blocks) if block.required]
        optional.sort(key=lambda index: blocks[index].priority, reverse=True)
        required.sort(key=lambda index: blocks[index].priority, reverse=True)
        return optional + required

    def _estimate_total(self, blocks: list[PromptBlock], variant_indexes: list[int]) -> int:
        total = 0
        for block, variant_index in zip(blocks, variant_indexes, strict=True):
            if variant_index < 0:
                continue
            total += self._estimator.estimate_text(block.variants[variant_index].text)
        return total

    def _build_plan(
        self,
        blocks: list[PromptBlock],
        variant_indexes: list[int],
        dropped: list[str],
    ) -> PromptPlan:
        selected: list[SelectedPromptBlock] = []
        for block, variant_index in zip(blocks, variant_indexes, strict=True):
            if variant_index < 0:
                continue
            variant = block.variants[variant_index]
            selected.append(
                SelectedPromptBlock(
                    block_id=block.block_id,
                    role=block.role,
                    priority=block.priority,
                    required=block.required,
                    state=variant.state,
                    text=variant.text,
                    estimated_tokens=self._estimator.estimate_text(variant.text),
                )
            )
        total = sum(block.estimated_tokens for block in selected)
        selected_usages = tuple(
            BlockTokenUsage(
                block_id=block.block_id,
                role=block.role,
                priority=block.priority,
                required=block.required,
                state=block.state,
                estimated_tokens=block.estimated_tokens,
            )
            for block in selected
        )
        selected_states = [block.state for block in selected]
        if dropped:
            selected_states.append("drop")
        max_state = (
            max(selected_states, key=lambda state: _COMPRESSION_ORDER[state])
            if selected_states
            else "full"
        )
        latest_user_tokens = next(
            (
                block.estimated_tokens
                for block in reversed(selected)
                if block.block_id == "current_turn" or block.role == "user"
            ),
            0,
        )
        history_message_count = sum(
            1
            for block in selected
            if block.block_id not in {"system", "match_archive", "current_turn"}
        )
        collapsed_message_count = sum(
            1 for block in selected if "summary" in block.block_id
        )
        diagnostics = PromptDiagnostics(
            estimated_tokens=total,
            prompt_budget_tokens=self._config.prompt_budget_tokens,
            max_context_tokens=self._config.max_context_tokens,
            max_output_tokens=self._config.max_output_tokens,
            context_compression_threshold=self._config.context_compression_threshold,
            selected_blocks=selected_usages,
            trimmed_blocks=tuple(dropped),
            max_compression_state=max_state,
            over_budget=total + self._config.max_output_tokens > self._config.context_limit_tokens,
            latest_user_tokens=latest_user_tokens,
            history_message_count=history_message_count,
            collapsed_message_count=collapsed_message_count,
        )
        return PromptPlan(
            blocks=tuple(selected),
            estimated_tokens=total,
            prompt_budget_tokens=self._config.prompt_budget_tokens,
            trimmed_blocks=tuple(dropped),
            diagnostics=diagnostics,
        )