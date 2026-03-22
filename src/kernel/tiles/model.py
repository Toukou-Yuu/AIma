"""牌种与单张牌。行为对照 mahjong_rules/Mahjong_Soul.md §4。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Suit(Enum):
    """花色：万 / 筒 / 索 / 字牌。"""

    MAN = 0
    PIN = 1
    SOU = 2
    HONOR = 3


@dataclass(frozen=True, slots=True)
class Tile:
    """
    一张牌。字牌 rank 为 1–7，依次对应东南西北白发中。
    赤宝仅允许出现在数牌的 5（万/筒/索）。
    """

    suit: Suit
    rank: int
    is_red: bool = False

    def __post_init__(self) -> None:
        # 赤五：只能是 5m/5p/5s
        if self.is_red:
            if self.suit == Suit.HONOR or self.rank != 5:
                msg = "is_red is only valid for 5m / 5p / 5s"
                raise ValueError(msg)
        if self.suit == Suit.HONOR:
            if not 1 <= self.rank <= 7:
                msg = "honor rank must be 1..7"
                raise ValueError(msg)
        elif not 1 <= self.rank <= 9:
            msg = "suit rank must be 1..9"
            raise ValueError(msg)

    def to_code(self) -> str:
        """调试用短码，非 UI。字牌为 z1–z7。"""
        if self.suit == Suit.HONOR:
            return f"{self.rank}z"
        letter = {Suit.MAN: "m", Suit.PIN: "p", Suit.SOU: "s"}[self.suit]
        if self.rank == 5 and self.is_red:
            return f"5{letter}r"
        return f"{self.rank}{letter}"
