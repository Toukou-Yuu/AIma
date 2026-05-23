"""H-34 修复测试：settle_ron/settle_tsumo 内部 ValueError → IllegalActionError。

测试要点：
1. settle_ron 内部 ValueError → IllegalActionError
2. settle_tsumo 内部 ValueError → IllegalActionError
3. 异常链保留（from e）

策略：使用字符串路径 mock apply 模块导入的 settlement 函数，
让 settle_ron/settle_tsumo 被调用时直接抛出 ValueError，验证 apply 层正确转换。
"""

from __future__ import annotations

import sys
import dataclasses as dc
from dataclasses import replace
from unittest.mock import patch

import pytest

from kernel.board import BoardState, CallResolution, RiverEntry, TurnPhase
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import IllegalActionError, apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.table.model import initial_table_snapshot
from kernel.tiles.model import Suit, Tile

from tests.engine_helpers import board_sorted_deal

MAN3 = Tile(Suit.MAN, 3)
TON = Tile(Suit.HONOR, 1)


def _bypass_board_validation(b0, **overrides):
    """绕过 BoardState __post_init__ 验证构造修改后的状态。"""
    b = object.__new__(BoardState)
    for f in dc.fields(b0):
        val = overrides.get(f.name, getattr(b0, f.name))
        object.__setattr__(b, f.name, val)
    return b


# ===== PASS_CALL 流程中 settle_ron ValueError 转换 =====


class TestPassCallSettleRonValueError:
    """PASS_CALL 流程中 settle_ron ValueError → IllegalActionError。"""

    def test_settle_ron_value_error_converted(self) -> None:
        """PASS_CALL 触发荣和结算时，settle_ron ValueError 被转换为 IllegalActionError。"""
        b0 = board_sorted_deal(dealer=0)

        entry = RiverEntry(seat=0, tile=MAN3, tsumogiri=False, riichi=False)
        cs = CallResolution(
            discard_seat=0,
            claimed_tile=MAN3,
            river_index=0,
            stage="ron",
            ron_remaining=frozenset({3}),
            ron_claimants=frozenset({1}),
            pon_kan_order=(1, 2, 3),
            pon_kan_idx=3,
            finished=False,
        )

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.CALL_RESPONSE,
            call_state=cs,
            river=(entry,),
            riichi=(False, True, False, False),
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        finished_cs = replace(
            cs,
            ron_remaining=frozenset(),
            ron_claimants=frozenset({1}),
            finished=True,
        )
        finished_board = _bypass_board_validation(
            board,
            call_state=finished_cs,
        )

        # 使用字符串路径 mock apply 模块中导入的函数
        with patch(
            "kernel.engine.apply.apply_pass_call",
            return_value=finished_board,
        ), patch(
            "kernel.engine.apply.settle_ron",  # apply 模块的导入
            side_effect=ValueError("荣和须至少一番役（ドラ不可单独计和）"),
        ), patch.object(
            sys.modules["kernel.engine.apply"],
            "_replace_board",
            side_effect=lambda b, **kw: b,
        ):
            with pytest.raises(IllegalActionError, match="荣和须至少一番役"):
                apply(state, Action(kind=ActionKind.PASS_CALL, seat=3))

    def test_settle_ron_value_error_chain_preserved(self) -> None:
        """PASS_CALL settle_ron ValueError → IllegalActionError 异常链保留。"""
        b0 = board_sorted_deal(dealer=0)

        entry = RiverEntry(seat=0, tile=MAN3, tsumogiri=False, riichi=False)
        cs = CallResolution(
            discard_seat=0,
            claimed_tile=MAN3,
            river_index=0,
            stage="ron",
            ron_remaining=frozenset({3}),
            ron_claimants=frozenset({1}),
            pon_kan_order=(1, 2, 3),
            pon_kan_idx=3,
            finished=False,
        )

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.CALL_RESPONSE,
            call_state=cs,
            river=(entry,),
            riichi=(False, True, False, False),
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        finished_cs = replace(
            cs,
            ron_remaining=frozenset(),
            ron_claimants=frozenset({1}),
            finished=True,
        )
        finished_board = _bypass_board_validation(
            board,
            call_state=finished_cs,
        )

        original_error = ValueError("chain test error")
        with patch(
            "kernel.engine.apply.apply_pass_call",
            return_value=finished_board,
        ), patch(
            "kernel.engine.apply.settle_ron",
            side_effect=original_error,
        ), patch.object(
            sys.modules["kernel.engine.apply"],
            "_replace_board",
            side_effect=lambda b, **kw: b,
        ):
            try:
                apply(state, Action(kind=ActionKind.PASS_CALL, seat=3))
            except IllegalActionError as e:
                assert e.__cause__ is original_error
                assert "chain test error" in str(e)
            else:
                pytest.fail("应抛出 IllegalActionError")


# ===== RON 动作流程中 settle_ron ValueError 转换 =====


class TestRonActionSettleRonValueError:
    """RON 动作流程中 settle_ron ValueError → IllegalActionError。"""

    def test_settle_ron_after_ron_value_error_converted(self) -> None:
        """RON 动作触发结算时，settle_ron ValueError 被转换为 IllegalActionError。"""
        b0 = board_sorted_deal(dealer=0)

        entry = RiverEntry(seat=0, tile=MAN3, tsumogiri=False, riichi=False)
        cs = CallResolution(
            discard_seat=0,
            claimed_tile=MAN3,
            river_index=0,
            stage="ron",
            ron_remaining=frozenset({1, 2, 3}),
            ron_claimants=frozenset(),
            pon_kan_order=(1, 2, 3),
            pon_kan_idx=0,
            finished=False,
        )

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.CALL_RESPONSE,
            call_state=cs,
            river=(entry,),
            riichi=(False, True, False, False),
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        apply_module = sys.modules["kernel.engine.apply"]

        finished_cs = replace(
            cs,
            ron_remaining=frozenset(),
            ron_claimants=frozenset({1}),
            finished=True,
        )
        finished_board = _bypass_board_validation(
            board,
            call_state=finished_cs,
        )

        with patch.object(
            apply_module,
            "_ron_non_dora_han",
            return_value=1,
        ), patch(
            "kernel.engine.apply.apply_ron",
            return_value=finished_board,
        ), patch(
            "kernel.engine.apply.settle_ron",
            side_effect=ValueError("荣和须至少一番役"),
        ):
            with pytest.raises(IllegalActionError, match="荣和须至少一番役"):
                apply(state, Action(kind=ActionKind.RON, seat=1))

    def test_settle_ron_after_ron_chain_preserved(self) -> None:
        """RON 动作 settle_ron ValueError → IllegalActionError 异常链保留。"""
        b0 = board_sorted_deal(dealer=0)

        entry = RiverEntry(seat=0, tile=MAN3, tsumogiri=False, riichi=False)
        cs = CallResolution(
            discard_seat=0,
            claimed_tile=MAN3,
            river_index=0,
            stage="ron",
            ron_remaining=frozenset({1, 2, 3}),
            ron_claimants=frozenset(),
            pon_kan_order=(1, 2, 3),
            pon_kan_idx=0,
            finished=False,
        )

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.CALL_RESPONSE,
            call_state=cs,
            river=(entry,),
            riichi=(False, True, False, False),
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        apply_module = sys.modules["kernel.engine.apply"]

        finished_cs = replace(
            cs,
            ron_remaining=frozenset(),
            ron_claimants=frozenset({1}),
            finished=True,
        )
        finished_board = _bypass_board_validation(
            board,
            call_state=finished_cs,
        )

        original_error = ValueError("ron chain test")
        with patch.object(
            apply_module,
            "_ron_non_dora_han",
            return_value=1,
        ), patch(
            "kernel.engine.apply.apply_ron",
            return_value=finished_board,
        ), patch(
            "kernel.engine.apply.settle_ron",
            side_effect=original_error,
        ):
            try:
                apply(state, Action(kind=ActionKind.RON, seat=1))
            except IllegalActionError as e:
                assert e.__cause__ is original_error
            else:
                pytest.fail("应抛出 IllegalActionError")


# ===== TSUMO 动作流程中 settle_tsumo ValueError 转换 =====


class TestTsumoActionSettleTsumoValueError:
    """TSUMO 动作流程中 settle_tsumo ValueError → IllegalActionError。"""

    def test_settle_tsumo_value_error_converted(self) -> None:
        """TSUMO 动作触发结算时，settle_tsumo ValueError 被转换为 IllegalActionError。"""
        b0 = board_sorted_deal(dealer=0)

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=TON,
            riichi=(False, False, False, False),
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        apply_module = sys.modules["kernel.engine.apply"]

        with patch(
            "kernel.engine.apply.can_tsumo_default",
            return_value=True,
        ), patch.object(
            apply_module,
            "_tsumo_non_dora_han",
            return_value=1,
        ), patch(
            "kernel.engine.apply.settle_tsumo",
            side_effect=ValueError("自摸须至少一番役"),
        ):
            with pytest.raises(IllegalActionError, match="自摸须至少一番役"):
                apply(state, Action(kind=ActionKind.TSUMO, seat=0))

    def test_settle_tsumo_value_error_chain_preserved(self) -> None:
        """TSUMO 动作 settle_tsumo ValueError → IllegalActionError 异常链保留。"""
        b0 = board_sorted_deal(dealer=0)

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=TON,
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        apply_module = sys.modules["kernel.engine.apply"]

        original_error = ValueError("tsumo chain test")
        with patch(
            "kernel.engine.apply.can_tsumo_default",
            return_value=True,
        ), patch.object(
            apply_module,
            "_tsumo_non_dora_han",
            return_value=1,
        ), patch(
            "kernel.engine.apply.settle_tsumo",
            side_effect=original_error,
        ):
            try:
                apply(state, Action(kind=ActionKind.TSUMO, seat=0))
            except IllegalActionError as e:
                assert e.__cause__ is original_error
            else:
                pytest.fail("应抛出 IllegalActionError")


# ===== 天和（庄家配牌自摸）场景 =====


class TestDealerInitialTsumoSettleTsumoValueError:
    """庄家配牌 14 张自摸（天和）场景中 settle_tsumo ValueError → IllegalActionError。"""

    def test_dealer_initial_tsumo_value_error_converted(self) -> None:
        """庄家配牌自摸时 settle_tsumo ValueError 被转换为 IllegalActionError。"""
        b0 = board_sorted_deal(dealer=0)

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.MUST_DISCARD,
            last_draw_tile=None,
            river=(),
            melds=((), (), (), ()),
            current_seat=0,
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        apply_module = sys.modules["kernel.engine.apply"]

        with patch(
            "kernel.engine.apply.can_win_seven_pairs_concealed_14",
            return_value=True,
        ), patch(
            "kernel.engine.apply.can_win_standard_form_concealed_total",
            return_value=False,
        ), patch.object(
            apply_module,
            "_tsumo_non_dora_han",
            return_value=1,
        ), patch(
            "kernel.engine.apply.settle_tsumo",
            side_effect=ValueError("自摸须至少一番役"),
        ):
            with pytest.raises(IllegalActionError, match="自摸须至少一番役"):
                apply(state, Action(kind=ActionKind.TSUMO, seat=0))

    def test_dealer_initial_tsumo_chain_preserved(self) -> None:
        """庄家配牌自摸时 settle_tsumo ValueError → IllegalActionError 异常链保留。"""
        b0 = board_sorted_deal(dealer=0)

        board = _bypass_board_validation(
            b0,
            turn_phase=TurnPhase.MUST_DISCARD,
            last_draw_tile=None,
            river=(),
            melds=((), (), (), ()),
            current_seat=0,
        )

        table = initial_table_snapshot()
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=table,
            board=board,
            ron_winners=None,
            event_sequence=0,
        )

        apply_module = sys.modules["kernel.engine.apply"]

        original_error = ValueError("tenhou chain test")
        with patch(
            "kernel.engine.apply.can_win_seven_pairs_concealed_14",
            return_value=True,
        ), patch(
            "kernel.engine.apply.can_win_standard_form_concealed_total",
            return_value=False,
        ), patch.object(
            apply_module,
            "_tsumo_non_dora_han",
            return_value=1,
        ), patch(
            "kernel.engine.apply.settle_tsumo",
            side_effect=original_error,
        ):
            try:
                apply(state, Action(kind=ActionKind.TSUMO, seat=0))
            except IllegalActionError as e:
                assert e.__cause__ is original_error
            else:
                pytest.fail("应抛出 IllegalActionError")