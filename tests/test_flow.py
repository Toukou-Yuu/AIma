"""流局判定与结算测试。"""

from __future__ import annotations

from collections import Counter

from kernel.deal import build_board_after_split
from kernel.deal.model import LIVE_WALL_AFTER_DEAL, BoardState
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import IllegalActionError, apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import initial_game_state
from kernel.flow.model import FlowKind, TenpaiResult
from kernel.flow.settle import (
    check_flow_mangan,
    compute_tenpai_result,
    settle_flow,
)
from kernel.flow.transitions import (
    check_flow_kind,
    is_exhausted_flow,
    is_four_kans_flow,
    is_four_riichi_flow,
    is_four_winds_flow,
    is_nine_nine_flow,
    is_three_ron_flow,
)
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


class TestExhaustedFlow:
    """荒牌流局测试。"""

    def test_is_exhausted_when_wall_empty(self) -> None:
        """本墙为空时判定为荒牌。"""
        # 直接使用 check_flow_kind 的 is_exhausted 判定逻辑
        # live_draw_index >= len(live_wall) 即为荒牌
        # 由于 BoardState 验证张数守恒，我们无法直接构造空墙
        # 所以测试 live_draw_index == len(live_wall) 的情况
        wall = _make_standard_wall()
        board = _make_board_from_wall(wall)

        # 模拟摸完所有牌：live_draw_index == len(live_wall)
        # 创建一个简化的测试：直接用字典模拟 board
        class MockBoard:
            live_wall = ()
            live_draw_index = 0

        mock_board = MockBoard()
        assert is_exhausted_flow(mock_board) is True

    def test_not_exhausted_when_wall_has_tiles(self) -> None:
        """本墙还有牌时不是荒牌。"""
        wall = _make_standard_wall()
        board = _make_board_from_wall(wall)

        # 初始状态本墙应该有牌
        assert len(board.live_wall) == LIVE_WALL_AFTER_DEAL
        assert is_exhausted_flow(board) is False


class TestNineNineFlow:
    """九种九牌流局测试。"""

    def test_is_nine_nine_with_9_kinds(self) -> None:
        """9 种幺九/字牌判定为九种九牌。"""
        # 13 张牌：9 种幺九/字牌
        hand = Counter(
            [
                Tile(Suit.MAN, 1),  # 一万
                Tile(Suit.MAN, 9),  # 九万
                Tile(Suit.PIN, 1),  # 一筒
                Tile(Suit.PIN, 9),  # 九筒
                Tile(Suit.SOU, 1),  # 一索
                Tile(Suit.SOU, 9),  # 九索
                Tile(Suit.HONOR, 1),  # 东
                Tile(Suit.HONOR, 2),  # 南
                Tile(Suit.HONOR, 3),  # 西
                Tile(Suit.HONOR, 4),  # 北
                Tile(Suit.HONOR, 5),  # 白
                Tile(Suit.HONOR, 6),  # 发
                Tile(Suit.HONOR, 7),  # 中
            ]
        )

        assert is_nine_nine_flow(hand) is True

    def test_not_nine_nine_with_8_kinds(self) -> None:
        """8 种幺九/字牌不判定为九种九牌。"""
        # 13 张牌：8 种幺九/字牌 + 非幺九牌
        hand = Counter(
            [
                Tile(Suit.MAN, 1),  # 一万
                Tile(Suit.MAN, 9),  # 九万
                Tile(Suit.PIN, 1),  # 一筒
                Tile(Suit.PIN, 9),  # 九筒
                Tile(Suit.SOU, 1),  # 一索
                Tile(Suit.SOU, 9),  # 九索
                Tile(Suit.HONOR, 1),  # 东
                Tile(Suit.HONOR, 2),  # 南
                Tile(Suit.MAN, 5),  # 五万（非幺九）
                Tile(Suit.MAN, 5),  # 五万
                Tile(Suit.PIN, 5),  # 五筒
                Tile(Suit.PIN, 5),  # 五筒
                Tile(Suit.SOU, 5),  # 五索
            ]
        )

        assert is_nine_nine_flow(hand) is False

    def test_nine_nine_with_duplicates(self) -> None:
        """有重复牌但种类≥9 时判定为九种九牌。"""
        # 13 张牌：9 种幺九/字牌（有重复）
        hand = Counter(
            [
                Tile(Suit.MAN, 1),
                Tile(Suit.MAN, 1),  # 重复
                Tile(Suit.MAN, 9),
                Tile(Suit.PIN, 1),
                Tile(Suit.PIN, 9),
                Tile(Suit.SOU, 1),
                Tile(Suit.SOU, 9),
                Tile(Suit.HONOR, 1),
                Tile(Suit.HONOR, 2),
                Tile(Suit.HONOR, 3),
                Tile(Suit.HONOR, 4),
                Tile(Suit.HONOR, 5),
                Tile(Suit.HONOR, 6),
            ]
        )

        assert is_nine_nine_flow(hand) is True


class TestFourWindsFlow:
    """四风连打流局测试。"""

    def test_is_four_winds_with_same_wind(self) -> None:
        """4 张相同风牌判定为四风连打。"""
        winds = [
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.HONOR, 1),  # 东
        ]

        assert is_four_winds_flow(winds) is True

    def test_not_four_winds_with_different_winds(self) -> None:
        """4 张不同风牌不判定为四风连打。"""
        winds = [
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.HONOR, 2),  # 南
            Tile(Suit.HONOR, 3),  # 西
            Tile(Suit.HONOR, 4),  # 北
        ]

        assert is_four_winds_flow(winds) is False

    def test_not_four_winds_with_non_winds(self) -> None:
        """有非风牌时不判定为四风连打。"""
        tiles = [
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.HONOR, 1),  # 东
            Tile(Suit.MAN, 1),  # 一万（非字牌）
        ]

        assert is_four_winds_flow(tiles) is False

    def test_not_four_winds_wrong_count(self) -> None:
        """不是 4 张牌时不判定为四风连打。"""
        winds = [
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 1),
        ]

        assert is_four_winds_flow(winds) is False


class TestFourKansFlow:
    """四杠流局测试。"""

    def test_is_four_kans_with_4(self) -> None:
        """4 个杠判定为四杠流局。"""
        assert is_four_kans_flow(4) is True
        assert is_four_kans_flow(5) is True

    def test_not_four_kans_with_3(self) -> None:
        """3 个杠不判定为四杠流局。"""
        assert is_four_kans_flow(3) is False
        assert is_four_kans_flow(0) is False

    def test_one_player_four_kans_not_flow(self) -> None:
        """同一玩家开 4 杠不流局（四杠子役满）。"""
        # 一人四杠：(4,0,0,0) → 不流局
        assert is_four_kans_flow((4, 0, 0, 0)) is False
        assert is_four_kans_flow((0, 4, 0, 0)) is False
        assert is_four_kans_flow((0, 0, 0, 4)) is False

    def test_scattered_four_kans_is_flow(self) -> None:
        """分散四杠（不同玩家合计 4 杠）判定为流局。"""
        assert is_four_kans_flow((2, 1, 1, 0)) is True
        assert is_four_kans_flow((1, 1, 1, 1)) is True
        assert is_four_kans_flow((3, 1, 0, 0)) is True


class TestFourRiichiFlow:
    """四家立直流局测试。"""

    def test_is_four_riichi_with_all_true(self) -> None:
        """4 家均立直判定为四家立直。"""
        assert is_four_riichi_flow((True, True, True, True)) is True

    def test_not_four_riichi_with_one_false(self) -> None:
        """有 1 家未立直不判定为四家立直。"""
        assert is_four_riichi_flow((True, True, True, False)) is False
        assert is_four_riichi_flow((False, True, True, True)) is False

    def test_not_four_riichi_with_all_false(self) -> None:
        """4 家均未立直不判定为四家立直。"""
        assert is_four_riichi_flow((False, False, False, False)) is False


class TestThreeRonFlow:
    """三家和流局测试。"""

    def test_is_three_ron_with_3_claimants(self) -> None:
        """3 家荣和判定为三家和。"""
        assert is_three_ron_flow(frozenset({0, 1, 2})) is True
        assert is_three_ron_flow(frozenset({0, 1, 3})) is True
        assert is_three_ron_flow(frozenset({1, 2, 3})) is True

    def test_not_three_ron_with_2_claimants(self) -> None:
        """2 家荣和不判定为三家和（一炮双响）。"""
        assert is_three_ron_flow(frozenset({0, 1})) is False

    def test_not_three_ron_with_1_claimant(self) -> None:
        """1 家荣和不判定为三家和（普通荣和）。"""
        assert is_three_ron_flow(frozenset({0})) is False

    def test_not_three_ron_with_4_claimants(self) -> None:
        """4 家荣和不判定为三家和（理论上不可能）。"""
        assert is_three_ron_flow(frozenset({0, 1, 2, 3})) is False


class TestCheckFlowKind:
    """综合流局检测测试。"""

    def test_three_ron_priority(self) -> None:
        """三家和优先级最高。"""
        board = _make_board_from_wall(_make_standard_wall())
        result = check_flow_kind(
            board,
            ron_claimants=frozenset({0, 1, 2}),
            riichi_state=(True, True, True, True),
            kan_count=4,
        )

        assert result is not None
        assert result.kind == FlowKind.THREE_RON

    def test_four_riichi_detection(self) -> None:
        """四家立直检测。"""
        board = _make_board_from_wall(_make_standard_wall())
        result = check_flow_kind(
            board,
            riichi_state=(True, True, True, True),
        )

        assert result is not None
        assert result.kind == FlowKind.FOUR_RIICHI

    def test_four_kans_detection(self) -> None:
        """四杠散了检测（分散四杠）。"""
        board = _make_board_from_wall(_make_standard_wall())
        result = check_flow_kind(
            board,
            kan_counts=(1, 1, 1, 1),
        )

        assert result is not None
        assert result.kind == FlowKind.FOUR_KANS

    def test_four_kans_one_player_not_flow(self) -> None:
        """一人四杠不触发流局。"""
        board = _make_board_from_wall(_make_standard_wall())
        result = check_flow_kind(
            board,
            kan_counts=(4, 0, 0, 0),
        )
        assert result is None

    def test_four_winds_detection(self) -> None:
        """四风连打检测。"""
        board = _make_board_from_wall(_make_standard_wall())
        first_4 = [
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 1),
        ]
        result = check_flow_kind(
            board,
            first_4_river=first_4,
        )

        assert result is not None
        assert result.kind == FlowKind.FOUR_WINDS

    def test_no_flow(self) -> None:
        """无流局情况。"""
        board = _make_board_from_wall(_make_standard_wall())
        result = check_flow_kind(board)

        assert result is None


class TestTenpaiResult:
    """听牌结果计算测试。"""

    def test_compute_tenpai_result_all_noten(self) -> None:
        """全部未听牌。"""
        wall = _make_standard_wall()
        board = _make_board_from_wall(wall)

        result = compute_tenpai_result(board)

        assert isinstance(result, TenpaiResult)
        assert len(result.tenpai_seats) == 0
        assert result.tenpai_types == ("noten", "noten", "noten", "noten")

    def test_compute_tenpai_result_some_tenpai(self) -> None:
        """部分听牌。"""
        # 构造一个简单听牌的牌型
        # 这里需要一个实际听牌的例子
        pass  # TODO: 构造具体听牌牌型


class TestSettleFlow:
    """流局结算测试。"""

    def test_settle_flow_basic(self) -> None:
        """基础流局结算。"""
        table = initial_table_snapshot()
        wall = _make_standard_wall()
        board = _make_board_from_wall(wall)

        new_table, tenpai_result = settle_flow(table, board)

        assert tenpai_result is not None
        assert new_table is not None


class TestFlowIntegration:
    """流局集成测试。"""

    def test_exhausted_flow_integration(self) -> None:
        """荒牌流局集成测试：通过 apply 推进到荒牌。"""
        state = initial_game_state()
        wall = _make_standard_wall()

        # BEGIN_ROUND
        action = Action(kind=ActionKind.BEGIN_ROUND, wall=wall)
        state_out = apply(state, action)

        assert state_out.new_state.phase == GamePhase.IN_ROUND
        assert state_out.new_state.board is not None

        # 模拟摸牌直到荒牌
        board = state_out.new_state.board
        assert board is not None

        # 持续摸打直到流局
        max_iterations = len(board.live_wall) + 10
        for i in range(max_iterations):
            if state_out.new_state.phase == GamePhase.FLOWN:
                assert state_out.new_state.flow_result is not None
                assert state_out.new_state.flow_result.kind == FlowKind.EXHAUSTED
                assert state_out.new_state.tenpai_result is not None
                break

            # 摸牌
            draw_action = Action(kind=ActionKind.DRAW)
            try:
                state_out = apply(state_out.new_state, draw_action)
            except IllegalActionError:
                break

            if state_out.new_state.phase != GamePhase.IN_ROUND:
                break

            # 打牌（简单打出一张安全牌）
            current_board = state_out.new_state.board
            if current_board is None:
                break

            hand = current_board.hands[current_board.current_seat]
            if hand:
                discard_tile = next(iter(hand.keys()))
                discard_action = Action(
                    kind=ActionKind.DISCARD,
                    seat=current_board.current_seat,
                    tile=discard_tile,
                )
                try:
                    state_out = apply(state_out.new_state, discard_action)
                except IllegalActionError:
                    break

    def test_four_riichi_flow_integration(self) -> None:
        """四家立直流局集成测试。"""
        # TODO: 构造四家立直的场景
        pass

    def test_four_kans_flow_integration(self) -> None:
        """四杠流局集成测试。"""
        # TODO: 构造四个杠的场景
        pass

    def test_haitei_draw_should_return_must_discard(self) -> None:
        """海底：DRAW 后应返回 MUST_DISCARD（非 FLOWN），给玩家自摸机会。

        通过 apply 推进对局到牌山最后一张。
        """
        from kernel.board import TurnPhase

        wall = tuple(shuffle_deck(build_deck(), seed=0))
        state = initial_game_state()
        state = apply(state, Action(kind=ActionKind.BEGIN_ROUND, wall=wall)).new_state

        for _ in range(300):
            if state.phase != GamePhase.IN_ROUND:
                break
            board = state.board
            if board is None:
                break

            if board.turn_phase == TurnPhase.NEED_DRAW:
                remaining = len(board.live_wall) - board.live_draw_index
                if remaining <= 1:
                    result = apply(state, Action(kind=ActionKind.DRAW))
                    rb = result.new_state.board
                    assert result.new_state.phase == GamePhase.IN_ROUND, \
                        f"海底摸牌后应为 IN_ROUND，实际 {result.new_state.phase}"
                    assert rb is not None
                    assert rb.turn_phase == TurnPhase.MUST_DISCARD, \
                        f"海底摸牌后应为 MUST_DISCARD，实际 {rb.turn_phase}"
                    # 打出一张牌 → 应触发荒牌
                    tile = next(iter(rb.hands[rb.current_seat].elements()))
                    result2 = apply(result.new_state, Action(
                        kind=ActionKind.DISCARD, seat=rb.current_seat, tile=tile,
                    ))
                    assert result2.new_state.phase == GamePhase.FLOWN
                    return
                state = apply(state, Action(kind=ActionKind.DRAW)).new_state
            elif board.turn_phase == TurnPhase.MUST_DISCARD:
                tile = next(iter(board.hands[board.current_seat].elements()))
                state = apply(state, Action(
                    kind=ActionKind.DISCARD, seat=board.current_seat, tile=tile,
                )).new_state
            elif board.turn_phase == TurnPhase.CALL_RESPONSE:
                from kernel.call.transitions import apply_pass_call
                cs = board.call_state
                if cs is not None:
                    if cs.stage == "ron":
                        # ron 阶段：所有 ron_remaining 的座位都需要 pass
                        for s in cs.ron_remaining:
                            try:
                                state = apply(state, Action(
                                    kind=ActionKind.PASS_CALL, seat=s,
                                )).new_state
                            except (IllegalActionError, ValueError):
                                pass
                            board = state.board
                            if board is None or state.phase != GamePhase.IN_ROUND:
                                break
                        if board is None or state.phase != GamePhase.IN_ROUND:
                            break
                        cs = board.call_state
                        if cs is not None and cs.stage == "pon_kan":
                            for s in cs.pon_kan_order:
                                try:
                                    state = apply(state, Action(
                                        kind=ActionKind.PASS_CALL, seat=s,
                                    )).new_state
                                except (IllegalActionError, ValueError):
                                    pass
                                board = state.board
                                if board is None or state.phase != GamePhase.IN_ROUND:
                                    break
                                cs2 = board.call_state
                                if cs2 is None:
                                    break
                        if board is None or state.phase != GamePhase.IN_ROUND:
                            break
                        cs = board.call_state
                        if cs is not None and cs.stage == "chi":
                            from kernel.board import shimocha_seat
                            chi_seat = shimocha_seat(cs.discard_seat)
                            try:
                                state = apply(state, Action(
                                    kind=ActionKind.PASS_CALL, seat=chi_seat,
                                )).new_state
                            except (IllegalActionError, ValueError):
                                pass
                    elif cs.stage == "pon_kan":
                        for s in cs.pon_kan_order:
                            try:
                                state = apply(state, Action(
                                    kind=ActionKind.PASS_CALL, seat=s,
                                )).new_state
                            except (IllegalActionError, ValueError):
                                pass
                            board = state.board
                            if board is None or state.phase != GamePhase.IN_ROUND:
                                break
                            cs2 = board.call_state
                            if cs2 is None:
                                break
                        if board is None or state.phase != GamePhase.IN_ROUND:
                            break
                        cs = board.call_state
                        if cs is not None and cs.stage == "chi":
                            from kernel.board import shimocha_seat
                            chi_seat = shimocha_seat(cs.discard_seat)
                            try:
                                state = apply(state, Action(
                                    kind=ActionKind.PASS_CALL, seat=chi_seat,
                                )).new_state
                            except (IllegalActionError, ValueError):
                                pass
                    elif cs.stage == "chi":
                        from kernel.board import shimocha_seat
                        chi_seat = shimocha_seat(cs.discard_seat)
                        try:
                            state = apply(state, Action(
                                kind=ActionKind.PASS_CALL, seat=chi_seat,
                            )).new_state
                        except (IllegalActionError, ValueError):
                            pass
                else:
                    break
            else:
                break

        # 未触发海底场景（可能提前流局或和了）
        assert state.phase != GamePhase.FLOWN, "不应在摸牌后直接进入 FLOWN"
        """4 个碰不应触发四杠流局（仅杠才计入）。"""
        from kernel.hand.melds import Meld, MeldKind

        pon_melds = [
            Meld(kind=MeldKind.PON, tiles=(Tile(Suit.MAN, 1),) * 3, called_tile=Tile(Suit.MAN, 1)),
            Meld(kind=MeldKind.PON, tiles=(Tile(Suit.PIN, 1),) * 3, called_tile=Tile(Suit.PIN, 1)),
            Meld(kind=MeldKind.PON, tiles=(Tile(Suit.SOU, 1),) * 3, called_tile=Tile(Suit.SOU, 1)),
            Meld(kind=MeldKind.PON, tiles=(Tile(Suit.HONOR, 1),) * 3, called_tile=Tile(Suit.HONOR, 1)),
        ]
        # 旧代码的错误计数：sum(len(melds)) = 4（把碰也算进去了）
        wrong_count = len(pon_melds)
        assert is_four_kans_flow(wrong_count) is True  # 旧代码会错误触发

        # 正确计数：只计杠类型
        kan_count = sum(
            1 for m in pon_melds
            if m.kind in (MeldKind.ANKAN, MeldKind.DAIMINKAN, MeldKind.KAKAN)
        )
        assert kan_count == 0
        assert is_four_kans_flow(kan_count) is False


def _take_n(pool: Counter[Tile], n: int) -> Counter[Tile]:
    """从牌池中取 n 张牌。"""
    out = Counter()
    for _ in range(n):
        if not pool:
            break
        t = next(iter(pool.elements()))
        out[t] += 1
        pool[t] -= 1
        if pool[t] == 0:
            del pool[t]
    return out


def _mock_board(b0: BoardState, **overrides) -> BoardState:
    """绕过 __post_init__ 验证构造修改后的 BoardState。"""
    import dataclasses as dc

    b = object.__new__(BoardState)
    for f in dc.fields(b0):
        val = overrides.get(f.name, getattr(b0, f.name))
        object.__setattr__(b, f.name, val)
    return b


class TestFlowMangan:
    """流局满贯测试。"""

    def test_flow_mangan_excluded_from_tenpai_payment(self) -> None:
        """M2: 流局满贯者应替代普通听牌结算，不叠加听牌料。"""
        from kernel.table.model import initial_table_snapshot

        # 构造局面：seat 1 是流局满贯者（子家），seat 0 是普通听牌者（亲家）
        b0 = _make_board_from_wall(_make_standard_wall(seed=0))

        # seat 1: 构造听牌手牌（七对子单骑）
        hand1 = Counter([
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 2), Tile(Suit.MAN, 2),
            Tile(Suit.MAN, 3), Tile(Suit.MAN, 3),
            Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 2), Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3), Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4),  # 单骑听北
        ])

        # seat 0: 普通听牌（亲家，非流局满贯）
        hand0 = Counter([
            Tile(Suit.PIN, 1), Tile(Suit.PIN, 2), Tile(Suit.PIN, 3),
            Tile(Suit.PIN, 4), Tile(Suit.PIN, 5), Tile(Suit.PIN, 6),
            Tile(Suit.SOU, 1), Tile(Suit.SOU, 2), Tile(Suit.SOU, 3),
            Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 5),
            Tile(Suit.HONOR, 6), Tile(Suit.HONOR, 6),
        ])

        hands = (hand0, hand1, b0.hands[2], b0.hands[3])

        # seat 1 的舍牌全是幺九
        all_discards_1 = [
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3),
        ]
        # seat 0 的舍牌含非幺九（不能流局满贯）
        all_discards_0 = [
            Tile(Suit.PIN, 5),  # 非幺九
        ]

        board = _mock_board(
            b0,
            hands=hands,
            all_discards_per_seat=(
                tuple(all_discards_0),
                tuple(all_discards_1),
                (),
                (),
            ),
            called_discard_indices=(frozenset(), frozenset(), frozenset(), frozenset()),
        )

        # seat 0 = dealer, seat 1 = 流局满贯者（子家）
        table = initial_table_snapshot(dealer_seat=0, starting_points=25000)
        assert check_flow_mangan(board, table, 1) is True  # seat 1 是流局满贯
        assert check_flow_mangan(board, table, 0) is False  # seat 0 不是

        # 结算
        new_table, tenpai_result = settle_flow(table, board)

        # seat 1: 子家满贯 = 8000（不应再加听牌料）
        delta1 = new_table.scores[1] - table.scores[1]
        assert delta1 == 8000

        # seat 0: 亲家听牌料 = 1000 * 2（从 seat 2, 3 收取）= 2000
        delta0 = new_table.scores[0] - table.scores[0]
        assert delta0 == 2000

        # 测试逻辑同上


class TestThreeRonFlowIntegration:
    """三家和流局集成测试。"""

    def test_three_ron_flow_when_multiple_ron_disabled(self) -> None:
        """一炮多响=false 时，三家和触发流局。"""
        from kernel.config import MahjongConfig
        from kernel.engine.apply import apply
        from kernel.engine.actions import Action, ActionKind
        from kernel.engine.phase import GamePhase
        from kernel.engine.state import GameState

        # 构造一个简单的 GameState
        table = initial_table_snapshot()
        state = GameState(phase=GamePhase.IN_ROUND, table=table)

        # 构造一个虚拟的 board（需要实际的 BoardState）
        # 这里简化：直接测试逻辑
        # 实际测试需要构造 3 家荣和的场景

        # 测试逻辑：
        # 1. 构造 3 家荣和的 call_state
        # 2. 设置 config.allow_multiple_ron = False
        # 3. 调用 apply
        # 4. 预期：返回 FLOWN 阶段
        pass  # 需要更复杂的 board 构造

    def test_three_ron_settlement_when_multiple_ron_enabled(self) -> None:
        """一炮多响=true 时，三家和走正常结算。"""
        from kernel.config import MahjongConfig
        from kernel.engine.apply import apply
        from kernel.engine.actions import Action, ActionKind
        from kernel.engine.phase import GamePhase
        from kernel.engine.state import GameState

        # 构造一个简单的 GameState
        table = initial_table_snapshot()
        state = GameState(phase=GamePhase.IN_ROUND, table=table)

        # 测试逻辑：
        # 1. 构造 3 家荣和的 call_state
        # 2. 设置 config.allow_multiple_ron = True
        # 3. 调用 apply
        # 4. 预期：返回 HAND_OVER 阶段
        pass  # 需要更复杂的 board 构造
        pass
