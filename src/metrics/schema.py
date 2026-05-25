"""Metrics schema: dataclasses for metric records and aggregations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MetricKind = Literal[
    "match_end",
    "hand_over",
    "decision",
    "ron",
    "tsumo",
    "riichi",
    "call",
    "flow",
]


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """Single metric record extracted from raw data."""

    kind: MetricKind
    match_id: str
    job_id: str
    seat: int | None = None
    hand_index: int | None = None
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MatchMetrics:
    """Match-level aggregated metrics (M2).

    Covers per-match statistics including outcome, duration,
    token usage, and reliability metrics.
    """

    match_id: str
    job_id: str
    seed: int

    # Outcome
    outcome: Literal["completed", "step_limit_exceeded"]
    step_count: int
    hand_count: int
    total_duration_ms: float

    # Points
    final_points: tuple[int, int, int, int]
    point_delta: tuple[int, int, int, int]
    starting_points: tuple[int, int, int, int]

    # Wins
    ron_count: tuple[int, int, int, int]
    tsumo_count: tuple[int, int, int, int]
    riichi_count: tuple[int, int, int, int]
    riichi_success_count: tuple[int, int, int, int]

    # Tokens (aggregated from decisions)
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_prompt_tokens_per_decision: float
    avg_completion_tokens_per_decision: float
    peak_prompt_tokens: int
    memory_injected_tokens_total: int

    # Reliability
    decision_count: int
    parse_success_count: int
    parse_fallback_count: int
    parse_error_count: int
    avg_latency_ms: float
    p99_latency_ms: float


@dataclass(frozen=True, slots=True)
class DecisionMetrics:
    """Decision-level metrics extracted from raw decision records."""

    match_id: str
    job_id: str
    seat: int
    hand_index: int
    step_index: int

    # Parse status
    parse_status: Literal["ok", "fallback", "error"]
    fallback_used: bool

    # Latency
    latency_ms: float | None

    # Tokens (from diagnostics if available)
    prompt_tokens: int | None
    completion_tokens: int | None
    memory_injected_tokens: int | None

    # Action kind
    action_kind: str


@dataclass(frozen=True, slots=True)
class PlayerMetrics:
    """Cross-match aggregated metrics for one player (seat)."""

    seat: int
    match_count: int

    # Points
    avg_final_points: float
    avg_point_delta: float
    total_point_delta: int

    # Wins
    total_ron_count: int
    total_tsumo_count: int
    total_riichi_count: int
    riichi_success_rate: float

    # Tokens
    avg_prompt_tokens: float
    avg_completion_tokens: float
    total_tokens: int
    avg_memory_injected_tokens: float

    # Reliability
    total_decisions: int
    parse_success_rate: float
    avg_latency_ms: float
    p99_latency_ms: float


@dataclass(frozen=True, slots=True)
class ReliabilitySummary:
    """Aggregated reliability metrics across all matches."""

    total_decisions: int
    parse_success_count: int
    parse_fallback_count: int
    parse_error_count: int

    parse_success_rate: float
    parse_fallback_rate: float
    parse_error_rate: float

    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    avg_prompt_tokens: float
    avg_completion_tokens: float
    avg_memory_injected_tokens: float

    matches_with_over_budget: int
    over_budget_rate: float