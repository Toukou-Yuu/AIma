"""Token estimation and prompt budget planning."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from llm.protocol import ChatMessage

CompressionState = Literal["full", "snip", "micro", "collapse", "autocompact", "drop"]
_COMPRESSION_ORDER: dict[CompressionState, int] = {
    "full": 0,
    "snip": 1,
    "micro": 2,
    "collapse": 3,
    "autocompact": 4,
    "drop": 5,
}


def _role_from_wire(value: object) -> Literal["system", "user", "assistant"]:
    role = str(value)
    if role not in ("system", "user", "assistant"):
        raise ValueError(f"invalid prompt block role: {role!r}")
    return cast(Literal["system", "user", "assistant"], role)


def _compression_state_from_wire(value: object) -> CompressionState:
    state = str(value)
    if state not in _COMPRESSION_ORDER:
        raise ValueError(f"invalid compression state: {state!r}")
    return cast(CompressionState, state)


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
    role: Literal["system", "user", "assistant"]
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
    role: Literal["system", "user", "assistant"]
    priority: int
    required: bool
    state: CompressionState
    text: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class BlockTokenUsage:
    """Token usage of one selected prompt block."""

    block_id: str
    role: Literal["system", "user", "assistant"]
    priority: int
    required: bool
    state: CompressionState
    estimated_tokens: int

    def to_wire(self) -> dict[str, Any]:
        """Serialize for replay/session logs."""
        return {
            "block_id": self.block_id,
            "role": self.role,
            "priority": self.priority,
            "required": self.required,
            "state": self.state,
            "estimated_tokens": self.estimated_tokens,
        }

    @staticmethod
    def from_wire(data: dict[str, Any]) -> "BlockTokenUsage":
        """Deserialize from replay/session logs."""
        return BlockTokenUsage(
            block_id=str(data["block_id"]),
            role=_role_from_wire(data["role"]),
            priority=int(data["priority"]),
            required=bool(data["required"]),
            state=_compression_state_from_wire(data["state"]),
            estimated_tokens=int(data["estimated_tokens"]),
        )


@dataclass(frozen=True, slots=True)
class PromptDiagnostics:
    """Prompt token diagnostics produced by the LLM context projector."""

    estimated_tokens: int
    prompt_budget_tokens: int
    context_budget_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    selected_blocks: tuple[BlockTokenUsage, ...]
    trimmed_blocks: tuple[str, ...]
    max_compression_state: CompressionState
    over_budget: bool
    latest_user_tokens: int = 0
    history_message_count: int = 0
    collapsed_message_count: int = 0

    @property
    def usage_ratio(self) -> float:
        """Prompt budget utilization ratio."""
        if self.prompt_budget_tokens <= 0:
            return 1.0 if self.estimated_tokens > 0 else 0.0
        return self.estimated_tokens / self.prompt_budget_tokens

    def to_wire(self) -> dict[str, Any]:
        """Serialize for replay/session logs."""
        return {
            "estimated_tokens": self.estimated_tokens,
            "prompt_budget_tokens": self.prompt_budget_tokens,
            "context_budget_tokens": self.context_budget_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "safety_margin_tokens": self.safety_margin_tokens,
            "max_compression_state": self.max_compression_state,
            "over_budget": self.over_budget,
            "latest_user_tokens": self.latest_user_tokens,
            "history_message_count": self.history_message_count,
            "collapsed_message_count": self.collapsed_message_count,
            "trimmed_blocks": list(self.trimmed_blocks),
            "selected_blocks": [block.to_wire() for block in self.selected_blocks],
        }

    @staticmethod
    def from_wire(data: dict[str, Any]) -> "PromptDiagnostics":
        """Deserialize from replay/session logs."""
        selected_raw = data.get("selected_blocks", [])
        selected_blocks = tuple(
            BlockTokenUsage.from_wire(item)
            for item in selected_raw
            if isinstance(item, dict)
        )
        return PromptDiagnostics(
            estimated_tokens=int(data["estimated_tokens"]),
            prompt_budget_tokens=int(data["prompt_budget_tokens"]),
            context_budget_tokens=int(data["context_budget_tokens"]),
            reserved_output_tokens=int(data["reserved_output_tokens"]),
            safety_margin_tokens=int(data["safety_margin_tokens"]),
            selected_blocks=selected_blocks,
            trimmed_blocks=tuple(str(item) for item in data.get("trimmed_blocks", [])),
            max_compression_state=_compression_state_from_wire(
                data["max_compression_state"]
            ),
            over_budget=bool(data["over_budget"]),
            latest_user_tokens=int(data.get("latest_user_tokens", 0)),
            history_message_count=int(data.get("history_message_count", 0)),
            collapsed_message_count=int(data.get("collapsed_message_count", 0)),
        )


@dataclass(frozen=True, slots=True)
class PromptDiagnosticsSummary:
    """Aggregated prompt token diagnostics for one match."""

    request_count: int
    latest: PromptDiagnostics | None
    peak: PromptDiagnostics | None
    average_estimated_tokens: int
    over_budget_count: int
    compression_state_counts: tuple[tuple[str, int], ...]
    trimmed_block_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class PromptBudgetConfig:
    """Prompt budgeting configuration."""

    context_budget_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int

    @property
    def prompt_budget_tokens(self) -> int:
        return max(
            0,
            self.context_budget_tokens - self.reserved_output_tokens - self.safety_margin_tokens,
        )


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
            context_budget_tokens=self._config.context_budget_tokens,
            reserved_output_tokens=self._config.reserved_output_tokens,
            safety_margin_tokens=self._config.safety_margin_tokens,
            selected_blocks=selected_usages,
            trimmed_blocks=tuple(dropped),
            max_compression_state=max_state,
            over_budget=total > self._config.prompt_budget_tokens,
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


def summarize_prompt_diagnostics(
    diagnostics: tuple[PromptDiagnostics | None, ...],
) -> PromptDiagnosticsSummary:
    """Aggregate prompt diagnostics for result screens."""
    valid = [item for item in diagnostics if item is not None]
    if not valid:
        return PromptDiagnosticsSummary(
            request_count=0,
            latest=None,
            peak=None,
            average_estimated_tokens=0,
            over_budget_count=0,
            compression_state_counts=(),
            trimmed_block_counts=(),
        )

    state_counts: dict[str, int] = {}
    trimmed_counts: dict[str, int] = {}
    total_tokens = 0
    over_budget_count = 0
    for item in valid:
        total_tokens += item.estimated_tokens
        if item.over_budget:
            over_budget_count += 1
        state_counts[item.max_compression_state] = (
            state_counts.get(item.max_compression_state, 0) + 1
        )
        for block_id in item.trimmed_blocks:
            trimmed_counts[block_id] = trimmed_counts.get(block_id, 0) + 1

    peak = max(valid, key=lambda item: item.usage_ratio)
    average = math.ceil(total_tokens / len(valid))
    state_items = tuple(
        sorted(
            state_counts.items(),
            key=lambda pair: _COMPRESSION_ORDER.get(pair[0], _COMPRESSION_ORDER["drop"]),
        )
    )
    trimmed_items = tuple(sorted(trimmed_counts.items(), key=lambda pair: pair[0]))
    return PromptDiagnosticsSummary(
        request_count=len(valid),
        latest=valid[-1],
        peak=peak,
        average_estimated_tokens=average,
        over_budget_count=over_budget_count,
        compression_state_counts=state_items,
        trimmed_block_counts=trimmed_items,
    )
