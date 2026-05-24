"""Pipeline result types for agent decision pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction

# Parse status: result of parsing LLM output
ParseStatus = Literal["matched", "parse_failed", "match_failed"]

# Ground status: result of grounding parsed choice to legal action
GroundStatus = Literal["grounded", "no_match"]


@dataclass(frozen=True, slots=True)
class ParseResult:
    """LLM output parsing result."""

    choice: dict[str, Any] | None
    why: str | None
    status: ParseStatus
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GroundResult:
    """Action grounding result."""

    legal_action: "LegalAction | None"
    status: GroundStatus
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Final result from agent pipeline execution."""

    action: "LegalAction | None"
    parse_status: ParseStatus
    fallback_used: bool
    raw_output: str
    diagnostics: dict[str, Any]
    latency_ms: float