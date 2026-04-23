"""Token budget display component for live match sidebars."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from llm.agent.token_budget import PromptDiagnostics
from ui.token_diagnostics import format_prompt_block_list


class TokenBudgetDisplay:
    """Render prompt token pressure without owning token estimation logic."""

    _BAR_WIDTH = 12

    def render_sidebar(
        self,
        diagnostics: PromptDiagnostics | None,
        *,
        compact: bool = False,
    ) -> Group:
        """Render token pressure for the live match sidebar."""
        if diagnostics is None:
            return Group(Text("暂无 LLM 请求", style="dim"))

        style = self._usage_style(diagnostics.usage_ratio)
        usage = self._format_usage(diagnostics)
        percent = self._format_percent(diagnostics.usage_ratio)
        status = self._status_text(diagnostics)

        if compact:
            return Group(
                Text.assemble(
                    (usage.replace(" / ", "/"), style),
                    (" · ", "dim"),
                    (percent, style),
                    (" · ", "dim"),
                    (diagnostics.max_compression_state, "bright_white"),
                    (" · ", "dim"),
                    (status, style),
                )
            )

        return Group(
            Text.assemble(
                (usage, style),
                (" -- ", "dim"),
                (self._bar(diagnostics.usage_ratio), style),
                (" ", "dim"),
                (percent, style),
            ),
            Text.assemble(
                (diagnostics.max_compression_state, "bright_white"),
                (" · ", "dim"),
                (status, style),
            ),
        )

    def _format_usage(self, diagnostics: PromptDiagnostics) -> str:
        return (
            f"{self._format_token_count(diagnostics.estimated_tokens)} / "
            f"{self._format_token_count(diagnostics.prompt_budget_tokens)}"
        )

    def _format_token_count(self, value: int) -> str:
        if abs(value) >= 1000:
            return f"{value / 1000:.1f}k"
        return str(value)

    def _format_percent(self, ratio: float) -> str:
        return f"{round(ratio * 100):d}%"

    def _bar(self, ratio: float) -> str:
        filled = max(0, min(self._BAR_WIDTH, round(ratio * self._BAR_WIDTH)))
        empty = self._BAR_WIDTH - filled
        return "[" + ("█" * filled) + ("░" * empty) + "]"

    def _usage_style(self, ratio: float) -> str:
        if ratio > 0.9:
            return "red"
        if ratio >= 0.7:
            return "yellow"
        return "green"

    def _status_text(self, diagnostics: PromptDiagnostics) -> str:
        if diagnostics.over_budget:
            return "超限"
        if diagnostics.trimmed_blocks:
            return "丢弃 " + format_prompt_block_list(diagnostics.trimmed_blocks)
        return "正常"
