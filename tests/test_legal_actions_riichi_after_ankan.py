"""H-31 回归测试：暗杠后立直资格。

根因：legal_actions 中使用 `len(melds) == 0` 或 `if melds` 检查门清，
将暗杠误判为非门清，拒绝立直选项。

规则：暗杠 (ANKAN) 不破门前清，暗杠后仍可立直（需听牌）。
明副露（碰/吃/大明杠/加杠）破门清，不可立直。

影响文件：
- legal_actions.py:306 使用 `_is_menzen(melds)` 判断立直资格
- apply.py:706 使用 `_is_menzen(board.melds[seat])` 验证立直合法性
"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    BoardState,
    GamePhase,
    GameState,
    LegalAction,
    Meld,
    MeldKind,
    Suit,
    Tile,
    TurnPhase,
    apply,
    build_board_after_split,
    build_deck,
    initial_table_snapshot,
    legal_actions,
    split_wall,
)
from kernel.engine.state import GameState
from kernel.riichi.tenpai import _is_menzen, is_tenpai_default

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


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    """未洗牌牌山，测试用砌牌可复现。"""
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


# ============================================================================
# 测试 1：_is_menzen 函数直接测试
# ============================================================================


class TestIsMenzenFunction:
    """直接测试 _is_menzen 函数的门清判定逻辑。"""

    def test_empty_melds_is_menzen(self) -> None:
        """无副露时为门清。"""
        assert _is_menzen(()) is True

    def test_single_ankan_is_menzen(self) -> None:
        """单个暗杠为门清。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        assert _is_menzen((ankan,)) is True

    def test_two_ankan_is_menzen(self) -> None:
        """两个暗杠仍为门清。"""
        ankan1 = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        ankan2 = Meld(MeldKind.ANKAN, (PIN5, PIN5, PIN5, PIN5), called_tile=None)
        assert _is_menzen((ankan1, ankan2)) is True

    def test_pon_is_not_menzen(self) -> None:
        """碰为非门清。"""
        pon = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), called_tile=MAN5)
        assert _is_menzen((pon,)) is False

    def test_chi_is_not_menzen(self) -> None:
        """吃为非门清。"""
        chi = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), called_tile=MAN2)
        assert _is_menzen((chi,)) is False

    def test_daiminkan_is_not_menzen(self) -> None:
        """大明杠为非门清。"""
        minkan = Meld(MeldKind.DAIMINKAN, (MAN1, MAN1, MAN1, MAN1), called_tile=MAN1)
        assert _is_menzen((minkan,)) is False

    def test_kakan_is_not_menzen(self) -> None:
        """加杠为非门清。"""
        kakan = Meld(MeldKind.KAKAN, (SOU9, SOU9, SOU9, SOU9), called_tile=SOU9)
        assert _is_menzen((kakan,)) is False

    def test_ankan_plus_pon_is_not_menzen(self) -> None:
        """暗杠 + 碰 = 非门清。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        pon = Meld(MeldKind.PON, (SOU9, SOU9, SOU9), called_tile=SOU9)
        assert _is_menzen((ankan, pon)) is False

    def test_ankan_plus_chi_is_not_menzen(self) -> None:
        """暗杠 + 吃 = 靶门清。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        chi = Meld(MeldKind.CHI, (PIN1, PIN2, PIN3), called_tile=PIN2)
        assert _is_menzen((ankan, chi)) is False


# ============================================================================
# 测试 2：暗杠后 legal_actions 返回立直选项
# ============================================================================


class TestAnkanLegalActionsRiichi:
    """暗杠后听牌时，legal_actions 应返回 declare_riichi=True 的动作。"""

    def test_ankan_tenpai_legal_actions_has_riichi_option(self) -> None:
        """暗杠后听牌，legal_actions 应返回含 declare_riichi=True 的动作。"""
        # 暗杠 5m
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        # 听牌手牌：亲家暗杠后 11 张（含 last_draw_tile）
        # 123m + 456p + 78s + 11p + last_draw PIN3 = 11 张
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1,
            PIN4: 1, PIN5: 1, PIN6: 1,
            SOU7: 1, SOU8: 1,
            PIN1: 2, PIN3: 1,
        })

        b0 = _board_sorted_deal(dealer=0)
        hands: list[Counter[Tile]] = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in ankan.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=1,  # 已摸一张（seat 0 自摸）
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((ankan,), (), (), ()),
            last_draw_tile=PIN3,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        actions = legal_actions(g, 0)

        # 验证存在 declare_riichi=True 的 DISCARD 动作
        riichi_actions = [a for a in actions if a.kind == ActionKind.DISCARD and a.declare_riichi]
        assert len(riichi_actions) >= 1, (
            f"暗杠后听牌应有立直选项，实际 riichi_actions={riichi_actions}"
        )

    def test_ankan_tenpai_which_tile_can_declare_riichi(self) -> None:
        """验证暗杠后立直选项仅在听牌打牌时出现。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1,
            PIN4: 1, PIN5: 1, PIN6: 1,
            SOU7: 1, SOU8: 1,
            PIN1: 2, PIN3: 1,
        })

        b0 = _board_sorted_deal(dealer=0)
        hands: list[Counter[Tile]] = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in ankan.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=1,  # 已摸一张
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((ankan,), (), (), ()),
            last_draw_tile=PIN3,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        actions = legal_actions(g, 0)
        riichi_tiles = {a.tile for a in actions if a.kind == ActionKind.DISCARD and a.declare_riichi}

        # 验证：打出听牌（即打牌后仍听牌）才可立直
        melds = b.melds[0]
        for tile in riichi_tiles:
            hand_after = Counter(b.hands[0])
            hand_after[tile] -= 1
            if hand_after[tile] == 0:
                del hand_after[tile]
            assert is_tenpai_default(hand_after, melds), (
                f"打掉 {tile} 后应仍听牌，实际 is_tenpai_default=False"
            )

    def test_ankan_not_tenpai_no_riichi_option(self) -> None:
        """暗杠后不听牌，无立直选项。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        # 不听牌手牌：11 张
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1, MAN4: 1,
            PIN4: 1, PIN5: 1, PIN6: 1,
            SOU7: 1, SOU8: 1,
            PIN1: 1, PIN3: 1,
        })

        b0 = _board_sorted_deal(dealer=0)
        hands: list[Counter[Tile]] = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in ankan.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=1,  # 已摸一张
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((ankan,), (), (), ()),
            last_draw_tile=PIN3,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        actions = legal_actions(g, 0)
        riichi_actions = [a for a in actions if a.kind == ActionKind.DISCARD and a.declare_riichi]

        # 不听牌时无立直选项
        assert len(riichi_actions) == 0, (
            f"暗杠后不听牌不应有立直选项，实际 riichi_actions={riichi_actions}"
        )


# ============================================================================
# 测试 3：碰/吃后 legal_actions 不返回立直选项
# ============================================================================


class TestPonChiLegalActionsNoRiichi:
    """碰/吃后（即使听牌），legal_actions 不应返回立直选项。"""

    def test_pon_tenpai_no_riichi_option(self) -> None:
        """碰后（即使听牌），legal_actions 不应返回立直选项。"""
        pon = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), called_tile=MAN5)
        concealed = Counter({
            MAN1: 1, MAN2: 1, MAN3: 1, MAN4: 1, MAN6: 1,
            PIN1: 2, PIN2: 1, PIN3: 1,
            SOU1: 2,
        })

        b0 = _board_sorted_deal(dealer=0)
        hands: list[Counter[Tile]] = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in pon.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((pon,), (), (), ()),
            last_draw_tile=PIN3,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        actions = legal_actions(g, 0)
        riichi_actions = [a for a in actions if a.kind == ActionKind.DISCARD and a.declare_riichi]

        # 碰后无立直选项
        assert len(riichi_actions) == 0, (
            f"碰后不应有立直选项，实际 riichi_actions={riichi_actions}"
        )

    def test_chi_tenpai_no_riichi_option(self) -> None:
        """吃后（即使听牌），legal_actions 不应返回立直选项。"""
        chi = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), called_tile=MAN2)
        # 亲家吃后：11 张（含 last_draw_tile）
        concealed = Counter({
            MAN4: 1, MAN5: 1, MAN6: 1,
            PIN1: 2, PIN2: 1, PIN3: 1,
            SOU1: 2, SOU7: 1, PIN4: 1,
        })

        b0 = _board_sorted_deal(dealer=0)
        hands: list[Counter[Tile]] = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in chi.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((chi,), (), (), ()),
            last_draw_tile=PIN4,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        actions = legal_actions(g, 0)
        riichi_actions = [a for a in actions if a.kind == ActionKind.DISCARD and a.declare_riichi]

        # 吃后无立直选项
        assert len(riichi_actions) == 0, (
            f"吃后不应有立直选项，实际 riichi_actions={riichi_actions}"
        )

    def test_daiminkan_tenpai_no_riichi_option(self) -> None:
        """大明杠后（即使听牌），legal_actions 不应返回立直选项。"""
        minkan = Meld(MeldKind.DAIMINKAN, (MAN1, MAN1, MAN1, MAN1), called_tile=MAN1)
        # 亲家大明杠后：11 张（含 last_draw_tile）
        concealed = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1, MAN5: 1, MAN6: 1,
            PIN1: 2, PIN2: 1,
            SOU1: 2,
        })

        b0 = _board_sorted_deal(dealer=0)
        hands: list[Counter[Tile]] = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in minkan.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((minkan,), (), (), ()),
            last_draw_tile=PIN3,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
        actions = legal_actions(g, 0)
        riichi_actions = [a for a in actions if a.kind == ActionKind.DISCARD and a.declare_riichi]

        # 大明杠后无立直选项
        assert len(riichi_actions) == 0, (
            f"大明杠后不应有立直选项，实际 riichi_actions={riichi_actions}"
        )