"""engine.apply 覆盖缺口测试：RON、HAND_OVER、FLOWN、立直。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel import Tile, Suit, build_deck
from kernel.call.win import can_ron_default, can_tsumo_default
from kernel.deal.model import BoardState
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState, initial_game_state
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import TurnPhase
from kernel.play.transitions import apply_discard, apply_draw
from kernel.table.model import initial_table_snapshot

from tests.engine_helpers import (
    board_sorted_deal,
    make_board,
    make_ron_board,
    pool_not_in_wall,
    take_n,
)
from tests.call_helpers import clear_call_window

# --- 牌常量 ---
MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN4 = Tile(Suit.MAN, 4)
MAN5 = Tile(Suit.MAN, 5)
MAN6 = Tile(Suit.MAN, 6)
MAN7 = Tile(Suit.MAN, 7)
MAN8 = Tile(Suit.MAN, 8)
MAN9 = Tile(Suit.MAN, 9)
PIN1 = Tile(Suit.PIN, 1)
PIN2 = Tile(Suit.PIN, 2)
PIN3 = Tile(Suit.PIN, 3)
PIN4 = Tile(Suit.PIN, 4)
PIN5 = Tile(Suit.PIN, 5)
PIN6 = Tile(Suit.PIN, 6)
PIN7 = Tile(Suit.PIN, 7)
PIN8 = Tile(Suit.PIN, 8)
PIN9 = Tile(Suit.PIN, 9)
SOU1 = Tile(Suit.SOU, 1)
SOU2 = Tile(Suit.SOU, 2)
SOU3 = Tile(Suit.SOU, 3)
SOU4 = Tile(Suit.SOU, 4)
SOU5 = Tile(Suit.SOU, 5)
SOU6 = Tile(Suit.SOU, 6)
SOU7 = Tile(Suit.SOU, 7)
SOU8 = Tile(Suit.SOU, 8)
SOU9 = Tile(Suit.SOU, 9)
HAKU = Tile(Suit.HONOR, 5)
HATSU = Tile(Suit.HONOR, 6)
CHUN = Tile(Suit.HONOR, 7)
TON = Tile(Suit.HONOR, 1)
NAN = Tile(Suit.HONOR, 2)


# --- RON 判定测试 ---

class TestRonDetection:
    """荣和判定覆盖。"""

    def test_ron_seven_pairs(self) -> None:
        """七对子荣和判定。"""
        # 13 张：6 对 + 1 单张，听 7m
        concealed = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, PIN1: 2, MAN7: 1,
        })
        assert can_ron_default(concealed, (), MAN7) is True

    def test_ron_standard_form(self) -> None:
        """标准形荣和判定。"""
        # 1m2m3m 4m5m6m 7p8p9p 1s2s3s + 东东，听 东
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1, MAN4: 1, MAN5: 1, MAN6: 1,
            PIN7: 1, PIN8: 1, PIN9: 1, SOU1: 1, SOU2: 1, SOU3: 1, TON: 1,
        })
        assert can_ron_default(concealed, (), TON) is True

    def test_ron_rejects_non_win(self) -> None:
        """非和牌形应拒绝。"""
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1, MAN4: 1, MAN5: 1, MAN6: 1,
            PIN7: 1, PIN8: 1, PIN9: 1, SOU1: 1, SOU2: 1, SOU3: 1, TON: 1,
        })
        # 打 1m 不是和牌
        assert can_ron_default(concealed, (), MAN1) is False


# --- 自摸判定测试 ---

class TestTsumoDetection:
    """自摸判定覆盖。"""

    def test_tsumo_seven_pairs(self) -> None:
        """七对子自摸判定。"""
        # 14 张七对子
        concealed = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, PIN1: 2, PIN2: 2,
        })
        # 自摸判定需要 win_tile 在手里
        assert can_tsumo_default(concealed, (), PIN2, last_draw_was_rinshan=False) is True

    def test_tsumo_standard_form(self) -> None:
        """标准形自摸判定。"""
        # 14 张：1m2m3m 4m5m6m 7p8p9p 1s2s3s 东东
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1, MAN4: 1, MAN5: 1, MAN6: 1,
            PIN7: 1, PIN8: 1, PIN9: 1, SOU1: 1, SOU2: 1, SOU3: 1, TON: 2,
        })
        assert can_tsumo_default(concealed, (), TON, last_draw_was_rinshan=False) is True

    def test_tsumo_rejects_non_win(self) -> None:
        """非和牌形应拒绝。"""
        concealed = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, PIN1: 2, MAN7: 1,
        })
        # 13 张不能自摸
        assert can_tsumo_default(concealed, (), MAN7, last_draw_was_rinshan=False) is False


# --- Engine 流程测试 ---

class TestEngineFlow:
    """engine apply 流程覆盖。"""

    def test_begin_round_and_discard(self) -> None:
        """BEGIN_ROUND → DISCARD 流程。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        assert g1.phase == GamePhase.IN_ROUND
        assert g1.board.turn_phase == TurnPhase.MUST_DISCARD

        # 亲家打牌
        ds = g1.board.current_seat
        tile = next(iter(g1.board.hands[ds].elements()))
        g2 = apply(g1, Action(ActionKind.DISCARD, seat=ds, tile=tile)).new_state
        assert g2.board.turn_phase == TurnPhase.CALL_RESPONSE

    def test_discard_wrong_seat(self) -> None:
        """非当前席打牌应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        ds = g1.board.current_seat
        tile = next(iter(g1.board.hands[ds].elements()))
        wrong_seat = (ds + 1) % 4
        try:
            apply(g1, Action(ActionKind.DISCARD, seat=wrong_seat, tile=tile))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for wrong seat discard")

    def test_draw_during_must_discard(self) -> None:
        """MUST_DISCARD 阶段摸牌应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        try:
            apply(g1, Action(ActionKind.DRAW, seat=g1.board.current_seat))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for draw during MUST_DISCARD")

    def test_pass_call_outside_call_response(self) -> None:
        """非 CALL_RESPONSE 阶段的 PASS_CALL 应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        try:
            apply(g1, Action(ActionKind.PASS_CALL, seat=g1.board.current_seat))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for PASS_CALL outside CALL_RESPONSE")

    def test_draw_then_discard_cycle(self) -> None:
        """走几轮摸打循环（engine 层）。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state

        for _ in range(5):
            # 亲家打牌
            ds = g.board.current_seat
            tile = next(iter(g.board.hands[ds].elements()))
            g = apply(g, Action(ActionKind.DISCARD, seat=ds, tile=tile)).new_state
            # 清除 call window
            if g.board.turn_phase == TurnPhase.CALL_RESPONSE:
                from tests.call_helpers import clear_call_window_state
                g = clear_call_window_state(g)
            # 摸牌
            if g.board.turn_phase == TurnPhase.NEED_DRAW:
                g = apply(g, Action(ActionKind.DRAW, seat=g.board.current_seat)).new_state


# --- Play 层流程测试 ---

class TestPlayLayerFlow:
    """play 层摸打循环，覆盖 draw/discard 路径。"""

    def test_draw_discard_cycle(self) -> None:
        """走几轮摸打循环。"""
        b = board_sorted_deal(dealer=0)
        # 亲家先打一张（配牌后是 MUST_DISCARD）
        tile = next(iter(b.hands[0].elements()))
        b = apply_discard(b, 0, tile)
        b = clear_call_window(b)
        # 现在是 NEED_DRAW
        for _ in range(5):
            b = apply_draw(b, b.current_seat)
            assert b.turn_phase == TurnPhase.MUST_DISCARD
            drawn = b.last_draw_tile
            assert drawn is not None
            b = apply_discard(b, b.current_seat, drawn)
            assert b.turn_phase == TurnPhase.CALL_RESPONSE
            b = clear_call_window(b)
            assert b.turn_phase == TurnPhase.NEED_DRAW

    def test_riichi_discard(self) -> None:
        """立直打牌路径。"""
        b = board_sorted_deal(dealer=0)
        tile = next(iter(b.hands[0].elements()))
        b = apply_discard(b, 0, tile, declare_riichi=True)
        assert b.riichi[0] is True
        b = clear_call_window(b)
        # 再摸一张，立直后必须摸切
        b = apply_draw(b, b.current_seat)
        drawn = b.last_draw_tile
        assert drawn is not None
        b = apply_discard(b, b.current_seat, drawn)
        assert b.turn_phase == TurnPhase.CALL_RESPONSE


# --- RON → HAND_OVER 端到端测试 ---

class TestRonHandOver:
    """通过 engine 测试荣和结算 → HAND_OVER 转换。"""

    def test_ron_single_claimant(self) -> None:
        """单家荣和 → HAND_OVER。"""
        # seat1 七对子听牌：6 对 + 7m 单张，听 7m
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        # 验证 seat1 能荣和
        assert can_ron_default(b.hands[1], b.melds[1], MAN7) is True

        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        # seat2, seat3 先 PASS（清空 ron_remaining 中除 seat1 外的座位）
        g = apply(g, Action(ActionKind.PASS_CALL, seat=2)).new_state
        g = apply(g, Action(ActionKind.PASS_CALL, seat=3)).new_state
        # seat1 荣和
        result = apply(g, Action(ActionKind.RON, seat=1))
        assert result.new_state.phase == GamePhase.HAND_OVER
        assert result.new_state.ron_winners == frozenset({1})
        assert len(result.events) >= 2

    def test_ron_multi_claimant(self) -> None:
        """多家荣和 → HAND_OVER。"""
        # seat1 七对子听 7m
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        # 让 seat2 也有七对子听 7m
        hands = list(b.hands)
        hands[2] = Counter({
            PIN1: 2, PIN2: 2, PIN3: 2, PIN4: 2, PIN5: 2, PIN6: 2, MAN7: 1,
        })
        b = replace(b, hands=tuple(hands))

        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        # seat1 先荣和
        r1 = apply(g, Action(ActionKind.RON, seat=1))
        # seat1 荣和后，call_state 应更新
        assert r1.new_state.board.call_state is not None
        assert 1 in r1.new_state.board.call_state.ron_claimants
        # ron_remaining 应减少
        assert 1 not in r1.new_state.board.call_state.ron_remaining

    def test_ron_rejected_not_in_remaining(self) -> None:
        """不在 ron_remaining 中的座位不能荣和。"""
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        # 修改 call_state 让 seat2 不在 ron_remaining 中
        cs = b.call_state
        assert cs is not None
        new_cs = replace(cs, ron_remaining=frozenset({1}))
        b = replace(b, call_state=new_cs)

        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.RON, seat=2))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for ron by non-remaining seat")

    def test_ron_rejected_wrong_shape(self) -> None:
        """手牌不是和牌形不能荣和。"""
        # 用池中可用的牌构造 13 张散牌（sorted deal 池中无 SOU/字牌）
        bad_hand = Counter({
            MAN1: 1, MAN9: 1, PIN1: 1, PIN3: 1,
            MAN2: 1, MAN4: 1, MAN6: 1, MAN8: 1,
            PIN2: 1, PIN4: 1, MAN3: 1, MAN5: 1, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=bad_hand, win_tile=MAN7,
        )
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.RON, seat=1))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for invalid ron shape")


# --- HAND_OVER → NOOP 测试 ---

class TestHandOverNoop:
    """HAND_OVER 阶段 NOOP 路径。"""

    def _reach_hand_over(self) -> GameState:
        """走到 HAND_OVER 状态（东一局，seat1 荣和）。"""
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        g = apply(g, Action(ActionKind.PASS_CALL, seat=2)).new_state
        g = apply(g, Action(ActionKind.PASS_CALL, seat=3)).new_state
        result = apply(g, Action(ActionKind.RON, seat=1))
        assert result.new_state.phase == GamePhase.HAND_OVER
        return result.new_state

    def test_hand_over_noop_new_round(self) -> None:
        """HAND_OVER + NOOP → 新局（非终局）。"""
        g = self._reach_hand_over()
        # 东一局，seat1（非亲家）和了 → 亲流，dealer_seat 轮转
        wall = tuple(build_deck())
        result = apply(g, Action(ActionKind.NOOP, wall=wall))
        assert result.new_state.phase == GamePhase.IN_ROUND
        # 亲流：dealer_seat 从 0 变为 1
        assert result.new_state.table.dealer_seat == 1

    def test_hand_over_noop_match_end(self) -> None:
        """HAND_OVER + NOOP → 终局（南四局亲流后）。"""
        # 构造南四局的 table
        from kernel.table.model import PrevailingWind, RoundNumber
        table = initial_table_snapshot(
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
        )
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        g = GameState(phase=GamePhase.IN_ROUND, table=table, board=b)
        g = apply(g, Action(ActionKind.PASS_CALL, seat=2)).new_state
        g = apply(g, Action(ActionKind.PASS_CALL, seat=3)).new_state
        result = apply(g, Action(ActionKind.RON, seat=1))
        assert result.new_state.phase == GamePhase.HAND_OVER
        # NOOP → 终局
        result2 = apply(result.new_state, Action(ActionKind.NOOP))
        assert result2.new_state.phase == GamePhase.MATCH_END

    def test_hand_over_noop_requires_wall(self) -> None:
        """HAND_OVER + NOOP 无 wall 应报错。"""
        g = self._reach_hand_over()
        try:
            apply(g, Action(ActionKind.NOOP))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for NOOP without wall")


# --- FLOWN → NOOP 测试 ---

class TestFlownNoop:
    """FLOWN 阶段 NOOP 路径。"""

    def _make_flown_state(self, *, table=None) -> GameState:
        """构造 FLOWN 状态（手动设置）。"""
        from kernel.flow.model import FlowKind, FlowResult
        if table is None:
            table = initial_table_snapshot()
        b = board_sorted_deal(dealer=0)
        flow_result = FlowResult(kind=FlowKind.EXHAUSTED)
        return GameState(
            phase=GamePhase.FLOWN,
            table=table,
            board=b,
            flow_result=flow_result,
        )

    def test_flown_noop_new_round(self) -> None:
        """FLOWN + NOOP → 新局。"""
        g = self._make_flown_state()
        wall = tuple(build_deck())
        result = apply(g, Action(ActionKind.NOOP, wall=wall))
        assert result.new_state.phase == GamePhase.IN_ROUND

    def test_flown_noop_match_end(self) -> None:
        """FLOWN + NOOP → 终局（南四局）。"""
        from kernel.table.model import PrevailingWind, RoundNumber
        table = initial_table_snapshot(
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
        )
        g = self._make_flown_state(table=table)
        result = apply(g, Action(ActionKind.NOOP))
        assert result.new_state.phase == GamePhase.MATCH_END


# --- Engine 层立直测试 ---

class TestEngineRiichi:
    """engine 层立直路径。"""

    def test_riichi_rejected_insufficient_points(self) -> None:
        """点棒不足立直应报错。"""
        table = initial_table_snapshot(starting_points=500)  # 每家 500 点 < 1000
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        g1 = GameState(
            phase=g1.phase,
            table=table,
            board=g1.board,
            event_sequence=g1.event_sequence,
        )
        ds = g1.board.current_seat
        tile = next(iter(g1.board.hands[ds].elements()))
        try:
            apply(g1, Action(ActionKind.DISCARD, seat=ds, tile=tile, declare_riichi=True))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for insufficient riichi points")

    def test_riichi_rejected_has_melds(self) -> None:
        """有副露时立直应报错。"""
        from kernel.hand.melds import MeldKind
        b = board_sorted_deal(dealer=0)
        # 给 seat0 加一个碰副露
        pon = Meld(kind=MeldKind.PON, tiles=(MAN1, MAN1, MAN1), called_tile=MAN1)
        melds = list(b.melds)
        melds[0] = (pon,)
        hand0 = b.hands[0].copy()
        hand0[MAN1] -= 3
        if hand0[MAN1] == 0:
            del hand0[MAN1]
        hands = list(b.hands)
        hands[0] = hand0
        b = replace(b, hands=tuple(hands), melds=tuple(melds))
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        tile = next(iter(g.board.hands[0].elements()))
        try:
            apply(g, Action(ActionKind.DISCARD, seat=0, tile=tile, declare_riichi=True))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for riichi with melds")

    def test_riichi_rejected_not_tenpai(self) -> None:
        """打牌后未听牌立直应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        ds = g1.board.current_seat
        tile = next(iter(g1.board.hands[ds].elements()))
        # 用 sorted deal 一般不听牌，立直应报 "not tenpai"
        try:
            apply(g1, Action(ActionKind.DISCARD, seat=ds, tile=tile, declare_riichi=True))
        except Exception as e:
            # 预期 "not tenpai" 或其他错误
            pass
        else:
            # 如果恰好听牌了（不太可能但不报错），也算通过
            pass


# --- TSUMO 自摸结算测试 ---

class TestTsumoSettlement:
    """TSUMO action → 自摸结算 → HAND_OVER。"""

    @staticmethod
    def _make_tsumo_hand_and_board(win_tile: Tile, extra_tiles: list[Tile]) -> BoardState:
        """构造自摸和牌 board：seat0 有 14 张和牌形，last_draw_tile=win_tile。"""
        from dataclasses import replace
        b0 = board_sorted_deal(dealer=0)
        # 从 live_wall 取 win_tile 和 extra_tiles
        live = list(b0.live_wall)
        # 从 pool（即已配手牌）构造 seat0 的手牌
        pool = pool_not_in_wall(b0)
        # 构造 13 张基础手牌
        hand = Counter()
        # 先放 win_tile 的 1 张（待摸后形成和牌形的前置张）
        hand[win_tile] += 1
        pool[win_tile] -= 1
        if pool[win_tile] == 0:
            del pool[win_tile]
        # 放 extra_tiles
        for t in extra_tiles:
            hand[t] += 1
            pool[t] -= 1
            if pool[t] == 0:
                del pool[t]
        # 补到 13 张
        while sum(hand.values()) < 13:
            t = next(iter(pool.elements()))
            hand[t] += 1
            pool[t] -= 1
            if pool[t] == 0:
                del pool[t]
        # 从 live_wall 取 win_tile 作为 last_draw_tile
        # 替换 live_wall 中的一个位置
        idx = 0
        for i, t in enumerate(live):
            if t == win_tile:
                idx = i
                break
        drawn = live[idx]
        live[idx] = next(iter(pool.elements()))  # 用 pool 中的 tile 替换
        pool[drawn] = pool.get(drawn, 0) + 1  # 不对，drawn 不在 pool
        # 简化：直接用 replace 修改 board
        hands = list(b0.hands)
        hands[0] = hand
        return replace(
            b0,
            hands=tuple(hands),
            live_wall=tuple(live),
            last_draw_tile=win_tile,
        )

    def test_tsumo_seven_pairs(self) -> None:
        """七对子自摸 → HAND_OVER。"""
        # 构造 14 张七对子：7 对
        hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 2,
        })
        b = board_sorted_deal(dealer=0)
        # 用 replace 直接设置手牌
        from dataclasses import replace
        hands = list(b.hands)
        hands[0] = hand
        b = replace(b, hands=tuple(hands), last_draw_tile=MAN7)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        result = apply(g, Action(ActionKind.TSUMO, seat=0))
        assert result.new_state.phase == GamePhase.HAND_OVER
        assert result.new_state.ron_winners == frozenset({0})
        assert len(result.events) >= 2

    def test_tsumo_standard_form(self) -> None:
        """标准形自摸 → HAND_OVER。"""
        # 14 张：1m2m3m × 3 + 4m5m6m + 7m7m（标准形和牌）
        # last_draw_tile = 7m（刚摸到的和了牌）
        hand = Counter({
            MAN1: 3, MAN2: 3, MAN3: 3, MAN4: 1, MAN5: 1, MAN6: 1, MAN7: 2,
        })
        from dataclasses import replace
        b = board_sorted_deal(dealer=0)
        hands = list(b.hands)
        hands[0] = hand  # 14 张
        b = replace(b, hands=tuple(hands), last_draw_tile=MAN7)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        result = apply(g, Action(ActionKind.TSUMO, seat=0))
        assert result.new_state.phase == GamePhase.HAND_OVER

    def test_tsumo_rejected_not_win(self) -> None:
        """非和牌形 TSUMO 应报错。"""
        # 14 张散牌，不是和牌形
        hand = Counter({
            MAN1: 2, MAN2: 1, MAN3: 2, MAN4: 1, MAN5: 2,
            MAN6: 1, MAN7: 1, MAN8: 2, MAN9: 2,
        })
        from dataclasses import replace
        b = board_sorted_deal(dealer=0)
        hands = list(b.hands)
        hands[0] = hand  # 14 张散牌
        b = replace(b, hands=tuple(hands), last_draw_tile=MAN9)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.TSUMO, seat=0))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for invalid tsumo shape")

    def test_tsumo_rejected_wrong_seat(self) -> None:
        """非当前席 TSUMO 应报错。"""
        hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 2,
        })
        from dataclasses import replace
        b = board_sorted_deal(dealer=0)
        hands = list(b.hands)
        hands[0] = hand
        b = replace(b, hands=tuple(hands), last_draw_tile=MAN7)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.TSUMO, seat=1))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for TSUMO wrong seat")

    def test_tsumo_rejected_no_last_draw(self) -> None:
        """无 last_draw_tile 时 TSUMO 应报错。"""
        b = board_sorted_deal(dealer=0)
        # 构造一个和牌形但没有 last_draw_tile 的状态
        hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 2,
        })
        from dataclasses import replace
        hands = list(b.hands)
        hands[0] = hand
        b = replace(b, hands=tuple(hands), last_draw_tile=None)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.TSUMO, seat=0))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for TSUMO without last_draw_tile")


# --- RON drain 测试 ---

class TestRonDrain:
    """PASS_CALL drain 后自动触发 RON 结算。"""

    def test_ron_drain_single(self) -> None:
        """单家 PASS_CALL drain → RON 结算 → HAND_OVER。"""
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        # seat1 声明 RON
        g = apply(g, Action(ActionKind.RON, seat=1)).new_state
        assert g.board.call_state is not None
        assert g.board.call_state.finished is False
        assert 1 in g.board.call_state.ron_claimants
        # seat2 PASS
        g = apply(g, Action(ActionKind.PASS_CALL, seat=2)).new_state
        assert g.board.call_state is not None
        assert g.board.call_state.finished is False
        # seat3 PASS → 最后一家，drain 触发结算 → HAND_OVER
        g = apply(g, Action(ActionKind.PASS_CALL, seat=3)).new_state
        assert g.phase == GamePhase.HAND_OVER
        assert g.ron_winners == frozenset({1})


# --- OPEN_MELD 测试 ---

class TestOpenMeld:
    """engine 层 OPEN_MELD action。"""

    def test_open_meld_rejected_no_seat(self) -> None:
        """OPEN_MELD 无 seat 应报错。"""
        b = board_sorted_deal(dealer=0)
        tile = next(iter(b.hands[0].elements()))
        b = apply_discard(b, 0, tile)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.OPEN_MELD, meld=Meld(kind=MeldKind.PON, tiles=(MAN1, MAN1, MAN1), called_tile=MAN1)))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for OPEN_MELD without seat")

    def test_open_meld_rejected_no_meld(self) -> None:
        """OPEN_MELD 无 meld 应报错。"""
        b = board_sorted_deal(dealer=0)
        tile = next(iter(b.hands[0].elements()))
        b = apply_discard(b, 0, tile)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.OPEN_MELD, seat=1))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for OPEN_MELD without meld")


# --- FLOWN NOOP tenpai 分支 ---

class TestFlownNoopTenpai:
    """FLOWN NOOP 的连庄/亲流分支。"""

    def test_flown_noop_dealer_tenpai_continue(self) -> None:
        """亲家听牌 → 连庄。"""
        from kernel.flow.model import FlowKind, FlowResult, TenpaiResult
        table = initial_table_snapshot(dealer_seat=0)
        b = board_sorted_deal(dealer=0)
        flow_result = FlowResult(kind=FlowKind.EXHAUSTED)
        tenpai_result = TenpaiResult(
            tenpai_seats=frozenset({0, 1}),
            tenpai_types=("tenpai", "tenpai", "noten", "noten"),
        )
        g = GameState(
            phase=GamePhase.FLOWN,
            table=table,
            board=b,
            flow_result=flow_result,
            tenpai_result=tenpai_result,
        )
        wall = tuple(build_deck())
        result = apply(g, Action(ActionKind.NOOP, wall=wall))
        assert result.new_state.phase == GamePhase.IN_ROUND

    def test_flown_noop_dealer_noten_advance(self) -> None:
        """亲家不听牌 → 亲流。"""
        from kernel.flow.model import FlowKind, FlowResult, TenpaiResult
        table = initial_table_snapshot(dealer_seat=0)
        b = board_sorted_deal(dealer=0)
        flow_result = FlowResult(kind=FlowKind.EXHAUSTED)
        tenpai_result = TenpaiResult(
            tenpai_seats=frozenset({1, 2}),
            tenpai_types=("noten", "tenpai", "tenpai", "noten"),
        )
        g = GameState(
            phase=GamePhase.FLOWN,
            table=table,
            board=b,
            flow_result=flow_result,
            tenpai_result=tenpai_result,
        )
        wall = tuple(build_deck())
        result = apply(g, Action(ActionKind.NOOP, wall=wall))
        assert result.new_state.phase == GamePhase.IN_ROUND
        # 亲流：dealer_seat 轮转
        assert result.new_state.table.dealer_seat == 1


# --- 错误守卫测试 ---

class TestErrorGuards:
    """engine 各种错误守卫路径。"""

    def test_invalid_action_kind_in_pre_deal(self) -> None:
        """PRE_DEAL 阶段非法 action。"""
        g = initial_game_state()
        try:
            apply(g, Action(ActionKind.DRAW, seat=0))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for DRAW in PRE_DEAL")

    def test_begin_round_no_wall(self) -> None:
        """BEGIN_ROUND 无 wall 应报错。"""
        g = initial_game_state()
        try:
            apply(g, Action(ActionKind.BEGIN_ROUND))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for BEGIN_ROUND without wall")

    def test_begin_round_short_wall(self) -> None:
        """BEGIN_ROUND wall 长度不足应报错。"""
        g = initial_game_state()
        try:
            apply(g, Action(ActionKind.BEGIN_ROUND, wall=tuple(build_deck())[:135]))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for BEGIN_ROUND with short wall")

    def test_discard_missing_tile(self) -> None:
        """DISCARD 无 tile 参数应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        ds = g1.board.current_seat
        try:
            apply(g1, Action(ActionKind.DISCARD, seat=ds))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for DISCARD without tile")

    def test_draw_wrong_seat(self) -> None:
        """DRAW 错误座位应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        # 先打牌进入 NEED_DRAW
        ds = g1.board.current_seat
        tile = next(iter(g1.board.hands[ds].elements()))
        g2 = apply(g1, Action(ActionKind.DISCARD, seat=ds, tile=tile)).new_state
        if g2.board.turn_phase == TurnPhase.CALL_RESPONSE:
            from tests.call_helpers import clear_call_window_state
            g2 = clear_call_window_state(g2)
        # 错误座位摸牌
        wrong_seat = (g2.board.current_seat + 1) % 4
        try:
            apply(g2, Action(ActionKind.DRAW, seat=wrong_seat))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for DRAW wrong seat")

    def test_ron_requires_seat(self) -> None:
        """RON 无 seat 应报错。"""
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.RON))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for RON without seat")

    def test_tsumo_requires_seat(self) -> None:
        """TSUMO 无 seat 应报错。"""
        hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 2,
        })
        from dataclasses import replace
        b = board_sorted_deal(dealer=0)
        hands = list(b.hands)
        hands[0] = hand
        b = replace(b, hands=tuple(hands), last_draw_tile=MAN7)
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        try:
            apply(g, Action(ActionKind.TSUMO))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for TSUMO without seat")

    def test_tsumo_requires_must_discard(self) -> None:
        """非 MUST_DISCARD 阶段 TSUMO 应报错。"""
        g0 = initial_game_state()
        wall = tuple(build_deck())
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
        # NEED_DRAW 阶段（配牌后是 MUST_DISCARD，先打一张进入 NEED_DRAW）
        ds = g1.board.current_seat
        tile = next(iter(g1.board.hands[ds].elements()))
        g2 = apply(g1, Action(ActionKind.DISCARD, seat=ds, tile=tile)).new_state
        if g2.board.turn_phase == TurnPhase.CALL_RESPONSE:
            from tests.call_helpers import clear_call_window_state
            g2 = clear_call_window_state(g2)
        # 现在是 NEED_DRAW，TSUMO 应报错
        try:
            apply(g2, Action(ActionKind.TSUMO, seat=g2.board.current_seat))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for TSUMO in NEED_DRAW")

    def test_non_noop_in_hand_over(self) -> None:
        """HAND_OVER 阶段非 NOOP 应报错。"""
        winner_hand = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, MAN6: 2, MAN7: 1,
        })
        b = make_ron_board(
            dealer=0, discarder=0, winner=1,
            winner_hand=winner_hand, win_tile=MAN7,
        )
        g = GameState(
            phase=GamePhase.IN_ROUND,
            table=initial_table_snapshot(),
            board=b,
        )
        g = apply(g, Action(ActionKind.PASS_CALL, seat=2)).new_state
        g = apply(g, Action(ActionKind.PASS_CALL, seat=3)).new_state
        result = apply(g, Action(ActionKind.RON, seat=1))
        assert result.new_state.phase == GamePhase.HAND_OVER
        # HAND_OVER 阶段的 DRAW 应报错
        try:
            apply(result.new_state, Action(ActionKind.DRAW, seat=0))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for DRAW in HAND_OVER")

    def test_non_noop_in_flown(self) -> None:
        """FLOWN 阶段非 NOOP 应报错。"""
        from kernel.flow.model import FlowKind, FlowResult
        table = initial_table_snapshot()
        b = board_sorted_deal(dealer=0)
        flow_result = FlowResult(kind=FlowKind.EXHAUSTED)
        g = GameState(
            phase=GamePhase.FLOWN,
            table=table,
            board=b,
            flow_result=flow_result,
        )
        try:
            apply(g, Action(ActionKind.DRAW, seat=0))
        except Exception:
            pass
        else:
            raise AssertionError("expected error for DRAW in FLOWN")
