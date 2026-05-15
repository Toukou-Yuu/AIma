"""Prompt diagnostics data models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from llm.agent.models.prompt_block import (
    BlockTokenUsage,
    CompressionState,
    _COMPRESSION_ORDER,
    _compression_state_from_wire,
)


@dataclass(frozen=True, slots=True)
class PromptDiagnostics:
    """Prompt token diagnostics produced by the LLM context projector."""

    estimated_tokens: int
    prompt_budget_tokens: int
    max_context_tokens: int
    max_output_tokens: int
    context_compression_threshold: float
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
            "max_context_tokens": self.max_context_tokens,
            "max_output_tokens": self.max_output_tokens,
            "context_compression_threshold": self.context_compression_threshold,
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
            max_context_tokens=int(data["max_context_tokens"]),
            max_output_tokens=int(data["max_output_tokens"]),
            context_compression_threshold=float(data["context_compression_threshold"]),
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