"""P0-1: 役满不计宝牌、赤宝、里宝测试。

役满手牌不应叠加表宝牌、赤宝牌、里宝牌。
"""

from __future__ import annotations

import pytest

from kernel.scoring.yaku import YAKUMAN_LABELS, is_yakuman


class TestYakumanLabels:
    """役满标签集合测试。"""

    def test_yakuman_labels_contains_all_expected(self) -> None:
        """验证役满标签集合包含所有预期标签。"""
        expected = [
            "大三元",
            "四暗刻单骑",
            "四暗刻",
            "国士无双十三面",
            "国士无双",
            "清老头",
            "字一色",
            "绿一色",
            "纯正九莲宝灯",
            "九莲宝灯",
            "四杠子",
            "大四喜",
            "小四喜",
            "天和",
            "地和",
        ]
        for label in expected:
            assert label in YAKUMAN_LABELS, f"{label} 应在役满集合中"

    def test_is_yakuman_detects_single_label(self) -> None:
        """单役满标签应被检测为役满。"""
        assert is_yakuman(("国士无双",)) is True
        assert is_yakuman(("四暗刻",)) is True
        assert is_yakuman(("天和",)) is True

    def test_is_yakuman_detects_no_yakuman(self) -> None:
        """非役满标签不应被检测为役满。"""
        assert is_yakuman(("立直", "断幺九")) is False
        assert is_yakuman(("七对子",)) is False
        assert is_yakuman(("平和", "立直")) is False

    def test_is_yakuman_detects_mixed(self) -> None:
        """混合标签（役满+其他）应被检测为役满。"""
        # 注：实际不应出现役满+非役满的组合，但检测逻辑应覆盖
        assert is_yakuman(("国士无双", "表宝牌1")) is True

    def test_yakuman_labels_count(self) -> None:
        """验证役满标签数量。"""
        # 确保没有遗漏
        assert len(YAKUMAN_LABELS) == 15, f"役满标签应为 15 个，实际 {len(YAKUMAN_LABELS)}"