"""P0-1: 役满不计宝牌、赤宝、里宝测试。

役满手牌不应叠加表宝牌、赤宝牌、里宝牌。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from kernel.board import BoardState, TurnPhase, CallResolution
from kernel.hand.melds import Meld, MeldKind
from kernel.scoring.settle import settle_ron_table, settle_tsumo_table
from kernel.scoring.yaku import YAKUMAN_LABELS, is_yakuman
from kernel.table.model import TableSnapshot, initial_table_snapshot
from kernel.tiles.model import Suit, Tile
from kernel.deal import build_board_after_split
from kernel.wall.split import split_wall
from kernel.engine.state import GameState
from kernel.engine.phase import GamePhase
from tests.engine_helpers import make_custom_wall_for_hand


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


class TestYakumanNoDoraIntegration:
    """役满不计宝牌集成测试（完整牌山）。"""

    def test_kokushi_no_dora_label(self) -> None:
        """国士无双荣和不应追加表宝牌标签。"""
        # 国士十三面手牌（13张不含荣和牌）
        winner_hand_13 = Counter([
            Tile(Suit.MAN, 1),  # 一万（荣和后成对）
            Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3), Tile(Suit.HONOR, 4),
            Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ])
        win_tile = Tile(Suit.MAN, 1)

        # 构造牌山，确保 winner=0 可以拿到指定手牌
        # dealer=1 时，seat 0 是子家
        wall = make_custom_wall_for_hand(
            target_hand=winner_hand_13,
            target_seat=0,
            dealer=1,
            revealed_indicator=Tile(Suit.MAN, 1),  # 宝牌指示牌
        )
        board = build_board_after_split(split_wall(wall), dealer_seat=1)

        # 验证 seat 0 手牌正确
        assert board.hands[0][Tile(Suit.MAN, 1)] >= 1

        # 设置宝牌指示牌为一万（使二万成为表宝牌）
        board = replace(board, revealed_indicators=(Tile(Suit.MAN, 1),))

        # 构造荣和状态：seat 1 打出 win_tile
        discarder = 1
        new_hands = list(board.hands)
        h = new_hands[discarder].copy()
        # 如果 discarder 没有这张牌，需要从牌山中获取
        if h.get(win_tile, 0) < 1:
            # 使用特殊构造：假设 discarder 打出的牌来自牌山
            # 这里简化处理，直接构造 CALL_RESPONSE 状态
            pass
        else:
            h[win_tile] -= 1
            if h[win_tile] == 0:
                del h[win_tile]
            new_hands[discarder] = h

        # 直接构造荣和结算所需的状态
        winner_hand_with_win = Counter(winner_hand_13)
        winner_hand_with_win[win_tile] += 1  # 加上荣和牌

        # 使用简化的 board 构造
        table = initial_table_snapshot(dealer_seat=1)

        # 直接调用 settle_ron_table，手动构造 board
        from kernel.board import RiverEntry
        river_entry = RiverEntry(seat=discarder, tile=win_tile, tsumogiri=False, riichi=False)
        board_for_ron = replace(
            board,
            hands=(winner_hand_with_win, board.hands[1], board.hands[2], board.hands[3]),
            river=(river_entry,),
            turn_phase=TurnPhase.CALL_RESPONSE,
            call_state=CallResolution.initial_after_discard(discarder, 0, win_tile),
        )

        result = settle_ron_table(
            table,
            board_for_ron,
            ron_winners=frozenset({0}),
            discard_seat=discarder,
            win_tile=win_tile,
        )

        settlement = result[1][0]
        # 验证：役满标签存在，但不应有宝牌标签
        assert "国士无双" in settlement.yakus or "国士无双十三面" in settlement.yakus
        assert all("宝牌" not in y for y in settlement.yakus), f"役满不应有宝牌标签: {settlement.yakus}"
        # 验证番数：役满番数应为 13
        assert settlement.han == 13

    def test_suuankou_no_dora(self) -> None:
        """四暗刻自摸不应追加表宝牌标签。"""
        # 四暗刻手牌：3 组暗刻 + 1 对（11张不含自摸牌）
        hand_11 = Counter([
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1),  # 暗刻（三张）
            Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9),  # 暗刻
            Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1),  # 暗刻
            Tile(Suit.SOU, 1),  # 对子（单张等待自摸）
        ])
        win_tile = Tile(Suit.SOU, 1)

        # 构造牌山
        wall = make_custom_wall_for_hand(
            target_hand=hand_11,
            target_seat=0,
            dealer=0,
        )
        board = build_board_after_split(split_wall(wall), dealer_seat=0)

        # 补充两张一索到 seat 0（构造完整的四暗刻）
        hand_with_extra = Counter(board.hands[0])
        hand_with_extra[Tile(Suit.SOU, 1)] += 2  # 加两张形成对子
        hand_with_extra[win_tile] += 1  # 加自摸牌

        # 设置宝牌指示牌
        board = replace(
            board,
            hands=(hand_with_extra, board.hands[1], board.hands[2], board.hands[3]),
            revealed_indicators=(Tile(Suit.SOU, 1),),
            last_draw_tile=win_tile,
        )

        table = initial_table_snapshot(dealer_seat=0)

        result = settle_tsumo_table(
            table,
            board,
            winner=0,
            win_tile=win_tile,
        )

        settlement = result[1][0]
        assert "四暗刻" in settlement.yakus
        assert all("宝牌" not in y for y in settlement.yakus), f"役满不应有宝牌标签: {settlement.yakus}"
        assert settlement.han == 13