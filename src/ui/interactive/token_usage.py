"""Interactive token diagnostics panels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from llm.agent.token_budget import PromptDiagnostics, summarize_prompt_diagnostics
from ui.interactive.chrome import render_summary_panel
from ui.token_diagnostics import format_prompt_block_counts

if TYPE_CHECKING:
    from rich.panel import Panel


def render_token_summary_panel(
    diagnostics: tuple[PromptDiagnostics | None, ...],
) -> "Panel":
    """Render aggregate token diagnostics for match result screens."""
    summary = summarize_prompt_diagnostics(diagnostics)
    if summary.request_count == 0:
        rows = [("状态", Text("暂无 token 记录", style="dim"))]
        return render_summary_panel("上下文诊断", rows, border_style="bright_magenta")

    latest = summary.latest
    peak = summary.peak
    rows = [
        ("请求数", str(summary.request_count)),
        ("最近占用", _format_diagnostics_usage(latest)),
        ("峰值占用", _format_diagnostics_usage(peak)),
        ("平均占用", _format_token_count(summary.average_estimated_tokens)),
        ("超预算次数", str(summary.over_budget_count)),
        ("压缩等级", _format_counts(summary.compression_state_counts)),
        ("丢弃模块", _format_counts(summary.trimmed_block_counts) or "无"),
    ]
    return render_summary_panel("上下文诊断", rows, border_style="bright_magenta")


def _format_diagnostics_usage(diagnostics: PromptDiagnostics | None) -> str:
    if diagnostics is None:
        return "无"
    return (
        f"{_format_token_count(diagnostics.estimated_tokens)} / "
        f"{_format_token_count(diagnostics.prompt_budget_tokens)} "
        f"({_format_percent(diagnostics.usage_ratio)})"
    )


def _format_token_count(value: int) -> str:
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k"
    return str(value)


def _format_percent(ratio: float) -> str:
    return f"{round(ratio * 100):d}%"


def _format_counts(counts: tuple[tuple[str, int], ...]) -> str:
    return format_prompt_block_counts(counts)
