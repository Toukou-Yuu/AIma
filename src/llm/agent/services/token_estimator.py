"""Token estimation service.

Provides heuristic token counting for DeepSeek-style models.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.protocol import ChatMessage


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