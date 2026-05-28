"""Token budget management for context history.

Handles token-based truncation of context text.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenBudgetConfig:
    """Token budget configuration."""

    max_tokens: int
    reserved_tokens: int = 0

    @property
    def available_tokens(self) -> int:
        """Available tokens for content."""
        return max(0, self.max_tokens - self.reserved_tokens)


@dataclass(frozen=True, slots=True)
class TruncationResult:
    """Result of token-based truncation."""

    text: str
    original_tokens: int
    truncated_tokens: int
    prompt_truncated: bool


class TokenBudgetManager:
    """Manage token budget and truncation."""

    def __init__(self, config: TokenBudgetConfig) -> None:
        self._config = config
        self._estimator = TokenEstimator()

    def truncate(self, text: str) -> TruncationResult:
        """Truncate text to fit within token budget.

        Args:
            text: Text to potentially truncate

        Returns:
            Truncation result with truncated text and statistics
        """
        if not text:
            return TruncationResult(
                text="",
                original_tokens=0,
                truncated_tokens=0,
                prompt_truncated=False,
            )

        original_tokens = self._estimator.estimate(text)
        if original_tokens <= self._config.available_tokens:
            return TruncationResult(
                text=text,
                original_tokens=original_tokens,
                truncated_tokens=original_tokens,
                prompt_truncated=False,
            )

        # Need to truncate
        truncated = self._truncate_to_budget(text)
        truncated_tokens = self._estimator.estimate(truncated)

        return TruncationResult(
            text=truncated,
            original_tokens=original_tokens,
            truncated_tokens=truncated_tokens,
            prompt_truncated=True,
        )

    def _truncate_to_budget(self, text: str) -> str:
        """Truncate text to fit budget, preserving recent content."""
        # Binary search to find truncation point
        lines = text.split("\n")
        if not lines:
            return text

        # Try keeping more recent lines first
        budget = self._config.available_tokens
        result_lines: list[str] = []
        total_tokens = 0

        for line in reversed(lines):
            line_tokens = self._estimator.estimate(line) + 1  # +1 for newline
            if total_tokens + line_tokens > budget:
                break
            result_lines.insert(0, line)
            total_tokens += line_tokens

        if not result_lines:
            # Can't fit any line, take last line truncated
            last_line = lines[-1]
            char_budget = int(budget * 1.5)  # Approximate chars per token
            if len(last_line) > char_budget:
                return last_line[-char_budget:] + "…[截断]"
            return last_line

        if len(result_lines) < len(lines):
            # Add truncation indicator
            skipped = len(lines) - len(result_lines)
            result_lines.insert(0, f"[已截断 {skipped} 行]")

        return "\n".join(result_lines)


class TokenEstimator:
    """Estimate token count for text.

    Uses heuristic similar to DeepSeek token counting.
    """

    def __init__(
        self,
        ascii_weight: float = 0.3,
        cjk_weight: float = 0.6,
        other_weight: float = 0.6,
    ) -> None:
        self._ascii_weight = ascii_weight
        self._cjk_weight = cjk_weight
        self._other_weight = other_weight

    def estimate(self, text: str) -> int:
        """Estimate token count for text."""
        if not text:
            return 0

        import math

        total = 0.0
        for char in text:
            if char.isascii():
                total += self._ascii_weight
            elif self._is_cjk_like(char):
                total += self._cjk_weight
            else:
                total += self._other_weight

        return max(1, math.ceil(total))

    def _is_cjk_like(self, char: str) -> bool:
        """Check if character is CJK-like."""
        import unicodedata

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