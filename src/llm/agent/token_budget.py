"""Token estimation and prompt budget planning."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from llm.protocol import ChatMessage

CompressionState = Literal["full", "snip", "micro", "collapse", "autocompact", "drop"]


def _is_cjk_like(char: str) -> bool:
    """Return True when ``char`` should use the conservative CJK estimate."""
    codepoint = ord(char)
    if 0x4E00 <= codepoint <= 0x9FFF:
        return True
    if 0x3400 <= codepoint <= 0x4DBF:
        return True
    if 0x3040 <= codepoint <= 0x30FF:
        return True
    if 0xAC00 <= codepoint <= 0xD7AF:
        return True
    return unicodedata.east_asian_width(char) in {"W", "F"}


@dataclass(frozen=True, slots=True)
class TokenEstimateService:
    """Estimate tokens from text using the agreed DeepSeek heuristic."""

    ascii_weight: float = 0.3
    cjk_weight: float = 0.6
    other_weight: float = 0.6

    def estimate_text(self, text: str) -> int:
        """Estimate prompt tokens for a single text block."""
        if not text:
            return 0
        total = 0.0
        for char in text:
            if char.isascii():
                total += self.ascii_weight
            elif _is_cjk_like(char):
                total += self.cjk_weight
            else:
                total += self.other_weight
        return max(1, math.ceil(total))

    def estimate_messages(self, messages: list["ChatMessage"]) -> int:
        """Estimate tokens for a chat request."""
        total = 0
        for message in messages:
            total += self.estimate_text(message.content)
        return total


@dataclass(frozen=True, slots=True)
class PromptBlockVariant:
    """A single compression candidate of a prompt block."""

    state: CompressionState
    text: str


@dataclass(frozen=True, slots=True)
class PromptBlock:
    """A prompt block with ordered compression variants."""

    block_id: str
    role: Literal["system", "user"]
    priority: int
    required: bool
    variants: tuple[PromptBlockVariant, ...]

    def validate(self) -> None:
        if not self.variants:
            raise ValueError(f"prompt block {self.block_id!r} must provide at least one variant")


@dataclass(frozen=True, slots=True)
class SelectedPromptBlock:
    """Selected prompt block variant after budget planning."""

    block_id: str
    role: Literal["system", "user"]
    priority: int
    required: bool
    state: CompressionState
    text: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class PromptBudgetConfig:
    """Prompt budgeting configuration."""

    context_budget_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int

    @property
    def prompt_budget_tokens(self) -> int:
        return max(0, self.context_budget_tokens - self.reserved_output_tokens - self.safety_margin_tokens)


@dataclass(frozen=True, slots=True)
class PromptPlan:
    """Budget planning result."""

    blocks: tuple[SelectedPromptBlock, ...]
    estimated_tokens: int
    prompt_budget_tokens: int
    trimmed_blocks: tuple[str, ...] = ()


class PromptBudgetPlanner:
    """Budget-aware selector for prompt blocks."""

    def __init__(
        self,
        config: PromptBudgetConfig,
        estimator: TokenEstimateService | None = None,
    ) -> None:
        self._config = config
        self._estimator = estimator or TokenEstimateService()

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
        return PromptPlan(
            blocks=tuple(selected),
            estimated_tokens=total,
            prompt_budget_tokens=self._config.prompt_budget_tokens,
            trimmed_blocks=tuple(dropped),
        )
