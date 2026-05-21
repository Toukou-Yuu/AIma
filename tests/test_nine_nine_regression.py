"""回归测试 R-07: 九种九牌未完整接线。

Root cause: `check_nine_nine_declaration()` 已定义但从未被调用，缺失 ActionKind 和 apply 处理。
Expected behavior:
- 首巡 + 无副露 + 9 种以上幺九牌时，legal_actions 应包含 DECLARE_NINE_NINE 选项
- DECLARE_NINE_NINE 动作执行后 → FLOWN with FlowKind.NINE_NINE
- 有副露时 → 无九种九牌选项
- 非首巡时 → 无九种九牌选项

测试要求：
1. 首巡 + 无副露 + 9 种幺九牌 → legal_actions 应含 NINE_NINE（当前缺失）
2. DECLARE_NINE_NINE 动作 → FLOWN with FlowKind.NINE_NINE（当前缺失）
3. 负向：有副露 → 无九种九牌选项
4. 负向：非首巡 → 无九种九牌选项

注意：当前 ActionKind 中无 DECLARE_NINE_NINE，legal_actions 中无九种九牌暴露，
      apply 中无九种九牌处理。此测试文档化这些缺失。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import dataclasses as dc

import pytest

from kernel.board import BoardState, TurnPhase, RiverEntry
from kernel.deal import build_board_after_split
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import ApplyOutcome, apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState, initial_game_state
from kernel.api.legal_actions import legal_actions, LegalAction
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.table.model import initial_table_snapshot
from kernel.tiles.deck import build_deck, shuffle_deck
from kernel.tiles.model import Suit, Tile
from kernel.wall.split import split_wall


def _make_standard_wall(seed: int = 0) -> tuple[Tile, ...]:
    """生成标准 136 张牌山。"""
    return tuple(shuffle_deck(build_deck(), seed=seed))


def _make_board_from_wall(wall: tuple[Tile, ...], dealer_seat: int = 0) -> BoardState:
    """从牌山构建 BoardState。"""
    split = split_wall(wall)
    return build_board_after_split(split, dealer_seat)


def _mock_board(b0: BoardState, **overrides) -> BoardState:
    """绕过 __post_init__ 验证构造修改后的 BoardState。"""
    b = object.__new__(BoardState)
    for f in dc.fields(b0):
        val = overrides.get(f.name, getattr(b0, f.name))
        object.__setattr__(b, f.name, val)
    return b


# 幺九牌定义（用于九种九牌检测）
TERMINAL_HONOR_TILES = [
    # 19 牌
    Tile(Suit.MAN, 1), Tile(Suit.MAN, 9),
    Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
    Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
    # 字牌
    Tile(Suit.HONOR, 1),  # 东
    Tile(Suit.HONOR, 2),  # 南
    Tile(Suit.HONOR, 3),  # 西
    Tile(Suit.HONOR, 4),  # 北
    Tile(Suit.HONOR, 5),  # 白
    Tile(Suit.HONOR, 6),  # 发
    Tile(Suit.HONOR, 7),  # 中
]


MAN1 = Tile(Suit.MAN, 1)
MAN9 = Tile(Suit.MAN, 9)
PIN1 = Tile(Suit.PIN, 1)
PIN9 = Tile(Suit.PIN, 9)
SOU1 = Tile(Suit.SOU, 1)
SOU9 = Tile(Suit.SOU, 9)
TON = Tile(Suit.HONOR, 1)
NAN = Tile(Suit.HONOR, 2)
SHA = Tile(Suit.HONOR, 3)
PEI = Tile(Suit.HONOR, 4)
HAKU = Tile(Suit.HONOR, 5)
HATSU = Tile(Suit.HONOR, 6)
CHUN = Tile(Suit.HONOR, 7)


class TestNineNineDetection:
    """九种九牌检测逻辑测试。"""

    def test_is_nine_nine_flow_with_9_kinds(self) -> None:
        """9 种幺九牌判定为九种九牌。"""
        from kernel.flow.transitions import is_nine_nine_flow

        hand = Counter([
            MAN1, MAN9,
            PIN1, PIN9,
            SOU1, SOU9,
            TON, NAN, SHA,
            HAKU, HATSU,
            CHUN, TON,  # 多一张东
        ])

        assert is_nine_nine_flow(hand) is True

    def test_is_nine_nine_flow_with_10_kinds(self) -> None:
        """10 种幺九牌也判定为九种九牌。"""
        from kernel.flow.transitions import is_nine_nine_flow

        hand = Counter([
            MAN1, MAN9,
            PIN1, PIN9,
            SOU1, SOU9,
            TON, NAN, SHA, PEI,
            HAKU, HATSU, CHUN,
        ])

        assert is_nine_nine_flow(hand) is True

    def test_is_nine_nine_flow_with_8_kinds(self) -> None:
        """8 种幺九牌不判定为九种九牌。"""
        from kernel.flow.transitions import is_nine_nine_flow

        hand = Counter([
            MAN1, MAN9,
            PIN1, PIN9,
            SOU1, SOU9,
            TON, NAN,
            # 缺少 SHA, PEI, HAKU, HATSU, CHUN
            Tile(Suit.MAN, 5),  # 补齐 13 张（非幺九）
            Tile(Suit.MAN, 5),
            Tile(Suit.PIN, 5),
            Tile(Suit.PIN, 5),
            Tile(Suit.SOU, 5),
        ])

        assert is_nine_nine_flow(hand) is False

    def test_is_nine_nine_flow_with_duplicates(self) -> None:
        """有重复牌但种类≥9 时判定为九种九牌。"""
        from kernel.flow.transitions import is_nine_nine_flow

        hand = Counter([
            MAN1, MAN1,  # 重复
            MAN9,
            PIN1, PIN9,
            SOU1, SOU9,
            TON, NAN, SHA,
            HAKU,
        ])

        assert is_nine_nine_flow(hand) is True

    def test_check_nine_nine_declaration(self) -> None:
        """check_nine_nine_declaration 应正确检测。"""
        from kernel.flow.transitions import check_nine_nine_declaration

        hand_9 = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, HAKU, HATSU, CHUN, PEI,
        ])
        assert check_nine_nine_declaration(hand_9) is True

        hand_8 = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN,
            Tile(Suit.MAN, 5), Tile(Suit.MAN, 5),
            Tile(Suit.PIN, 5), Tile(Suit.PIN, 5),
            Tile(Suit.SOU, 5),
        ])
        assert check_nine_nine_declaration(hand_8) is False


class TestNineNineActionWiring:
    """九种九牌动作接线测试（当前缺失）。"""

    def test_legal_actions_should_expose_nine_nine(self) -> None:
        """legal_actions 应在首巡 + 无副露 + 9 种幺九牌时暴露九种九牌选项。"""
        # 构造一个首巡状态：亲家配牌后处于 MUST_DISCARD，含 9+ 种幺九牌
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌：9 种幺九牌 + 4 张其他牌凑成 13 张，再加 last_draw_tile 凑 14 张
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,  # 6 种
            TON, NAN, SHA, PEI,  # 4 种字牌 = 10 种
            HAKU, HATSU,  # 补 2 张凑 13 张
        ])

        # 用一张幺九牌作为 last_draw_tile（凑 14 张）
        last_tile = CHUN

        # 构造完整 14 张手牌
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        # Mock board: 首巡（无舍牌）、无副露、MUST_DISCARD
        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,  # 亲家
            last_draw_tile=last_tile,
            all_discards_per_seat=((), (), (),()),  # 首巡：无舍牌
            melds=((), (), (),()),  # 无副露
        )

        # 构造 GameState
        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        # 验证：legal_actions 应包含 DECLARE_NINE_NINE
        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE in action_kinds

    def test_apply_should_handle_nine_nine(self) -> None:
        """apply 应处理 DECLARE_NINE_NINE 动作 → FLOWN。"""
        # 构造九种九牌条件满足的状态
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌：10 种幺九牌（满足九种九牌条件）
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, PEI,
            HAKU, HATSU, CHUN,  # 13 张
        ])
        last_tile = Tile(Suit.MAN, 5)  # 补一张凑 14 张（非幺九）
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((), (), (),()),
            melds=((), (), (),()),
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        # 执行 DECLARE_NINE_NINE
        outcome = apply(state, Action(ActionKind.DECLARE_NINE_NINE, seat=0))

        # 验证：结果应为 FLOWN 状态
        assert outcome.new_state.phase == GamePhase.FLOWN
        assert outcome.new_state.flow_result is not None
        assert outcome.new_state.flow_result.kind == FlowKind.NINE_NINE


class TestNineNineConditions:
    """九种九牌条件测试。"""

    def test_first_turn_condition(self) -> None:
        """首巡定义验证：river 为空，亲家处于 MUST_DISCARD（已自动摸牌）。

        首巡判断逻辑：
        - 配牌后第一巡（river 为空）
        - 亲家已自动摸牌，处于 MUST_DISCARD
        - 其他三家处于 NEED_DRAW（等待摸牌）
        """
        wall = _make_standard_wall(seed=42)
        board = _make_board_from_wall(wall, dealer_seat=0)

        # 配牌后 river 应为空
        assert len(board.river) == 0

        # 当前家为亲家（seat 0），配牌后亲家已自动摸牌，处于 MUST_DISCARD
        assert board.current_seat == 0
        assert board.turn_phase == TurnPhase.MUST_DISCARD

    def test_no_melds_condition(self) -> None:
        """无副露条件验证。"""
        wall = _make_standard_wall(seed=42)
        board = _make_board_from_wall(wall, dealer_seat=0)

        # 配牌后所有家无副露
        for s in range(4):
            assert len(board.melds[s]) == 0

    def test_first_turn_with_melds_no_nine_nine(self) -> None:
        """首巡 + 有副露 → 无九种九牌选项。"""
        # 构造首巡状态，但某家有副露（模拟碰）
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌含 9+ 种幺九牌
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, PEI, HAKU, HATSU, CHUN,
        ])
        last_tile = Tile(Suit.MAN, 5)
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        # 模拟一个碰副露（座位 1 有碰）
        fake_meld = Meld(
            kind=MeldKind.PON,
            tiles=(TON, TON, TON),
            called_tile=TON,
            from_seat=0,  # 从座位 0 鸣牌
        )

        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((), (), (),()),
            melds=((), (fake_meld,), (),()),  # 座位 1 有副露
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        # 验证：legal_actions 不应包含 DECLARE_NINE_NINE
        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE not in action_kinds

    def test_not_first_turn_no_nine_nine(self) -> None:
        """非首巡 → 无九种九牌选项。"""
        # 构造非首巡状态：座位 0 已有舍牌
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌含 9+ 种幺九牌
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, PEI, HAKU, HATSU, CHUN,
        ])
        last_tile = Tile(Suit.MAN, 5)
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        # 座位 0 已有舍牌（非首巡）
        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((MAN1,), (), (),()),  # 座位 0 已舍牌
            melds=((), (), (),()),
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        # 验证：legal_actions 不应包含 DECLARE_NINE_NINE
        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE not in action_kinds


class TestNineNineIntegration:
    """九种九牌集成测试。"""

    def test_full_nine_nine_flow(self) -> None:
        """完整流程：配牌 → 检测九种九牌 → 宣言 → FLOWN。"""
        # 构造满足九种九牌条件的状态
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌含 10 种幺九牌
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, PEI,
            HAKU, HATSU, CHUN,
        ])
        last_tile = Tile(Suit.PIN, 5)
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((), (), (),()),
            melds=((), (), (),()),
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        # Step 1: legal_actions 应包含 DECLARE_NINE_NINE
        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE in action_kinds

        # Step 2: 执行 DECLARE_NINE_NINE
        outcome = apply(state, Action(ActionKind.DECLARE_NINE_NINE, seat=0))

        # Step 3: 验证 FLOWN 状态
        assert outcome.new_state.phase == GamePhase.FLOWN
        assert outcome.new_state.flow_result is not None
        assert outcome.new_state.flow_result.kind == FlowKind.NINE_NINE


class TestNineNineNegativeConditions:
    """负向条件测试。"""

    def test_melds_block_nine_nine(self) -> None:
        """有副露时不应有九种九牌选项。"""
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌含 10 种幺九牌（理论上满足九种九牌）
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, PEI, HAKU, HATSU, CHUN,
        ])
        last_tile = Tile(Suit.MAN, 5)
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        # 座位 0 有副露（即使手牌满足条件，副露阻断）
        fake_meld = Meld(
            kind=MeldKind.PON,
            tiles=(TON, TON, TON),
            called_tile=TON,
            from_seat=3,
        )

        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((), (), (),()),
            melds=((fake_meld,), (), (),()),  # 座位 0 有副露
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE not in action_kinds

    def test_not_first_turn_blocks_nine_nine(self) -> None:
        """非首巡时不应有九种九牌选项。"""
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌含 10 种幺九牌（理论上满足九种九牌）
        nine_nine_hand = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,
            TON, NAN, SHA, PEI, HAKU, HATSU, CHUN,
        ])
        last_tile = Tile(Suit.MAN, 5)
        full_hand = Counter(nine_nine_hand)
        full_hand[last_tile] += 1

        # 座位 0 已舍牌（非首巡阻断）
        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((PIN1,), (MAN9,), (TON,), ()),  # 多家有舍牌
            melds=((), (), (),()),
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE not in action_kinds

    def test_less_than_9_kinds_blocks_nine_nine(self) -> None:
        """少于 9 种幺九牌时不应有九种九牌选项。"""
        wall = _make_standard_wall(seed=42)
        board0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造手牌仅含 8 种幺九牌（不满足九种九牌条件）
        hand_8_kinds = Counter([
            MAN1, MAN9, PIN1, PIN9, SOU1, SOU9,  # 6 种
            TON, NAN,  # 2 种字牌 = 8 种
            Tile(Suit.MAN, 5), Tile(Suit.MAN, 5),  # 补非幺九牌凑 13 张
            Tile(Suit.PIN, 5), Tile(Suit.PIN, 5),
            Tile(Suit.SOU, 5),
        ])
        last_tile = Tile(Suit.MAN, 3)  # 补一张凑 14 张（非幺九）
        full_hand = Counter(hand_8_kinds)
        full_hand[last_tile] += 1

        mock_board = _mock_board(
            board0,
            hands=(full_hand, board0.hands[1], board0.hands[2], board0.hands[3]),
            turn_phase=TurnPhase.MUST_DISCARD,
            current_seat=0,
            last_draw_tile=last_tile,
            all_discards_per_seat=((), (), (),()),  # 首巡
            melds=((), (), (),()),  # 无副露
        )

        state = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=mock_board,
        )

        actions = legal_actions(state, seat=0)
        action_kinds = {a.kind for a in actions}
        assert ActionKind.DECLARE_NINE_NINE not in action_kinds


class TestFlowKindNineNine:
    """FlowKind.NINE_NINE 存在性验证。"""

    def test_nine_nine_flow_kind_exists(self) -> None:
        """FlowKind.NINE_NINE 应存在（验证已存在）。"""
        assert FlowKind.NINE_NINE.value == "nine_nine"

    def test_flow_result_with_nine_nine(self) -> None:
        """FlowResult 应支持 FlowKind.NINE_NINE。"""
        from kernel.flow.model import FlowResult

        result = FlowResult(kind=FlowKind.NINE_NINE)
        assert result.kind == FlowKind.NINE_NINE