"""比赛终局模块：终局结果与名次确定。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchResult:
    """
    比赛终局结果。

    Attributes:
        ranking: 名次元组 ``(1 位席次，2 位席次，3 位席次，4 位席次)``
        scores: 终局点棒 ``(席次 0 分数，席次 1 分数，席次 2 分数，席次 3 分数)``
        prevailing_wind: 终局时场风
        round_number: 终局时局序
    """

    ranking: tuple[int, ...]
    scores: tuple[int, int, int, int]
    prevailing_wind: str
    round_number: str


__all__ = ["MatchResult"]
