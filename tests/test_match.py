"""kernel.match 模块测试。"""

from __future__ import annotations

from kernel.match import MatchResult


class TestMatchResult:
    def test_creation(self) -> None:
        r = MatchResult(
            ranking=(0, 1, 2, 3),
            scores=(45000, 25000, 20000, 10000),
            prevailing_wind="east",
            round_number="1-1",
        )
        assert r.ranking == (0, 1, 2, 3)
        assert r.scores == (45000, 25000, 20000, 10000)
        assert r.prevailing_wind == "east"
        assert r.round_number == "1-1"

    def test_import(self) -> None:
        from kernel.match import MatchResult as MR
        assert MR is MatchResult
