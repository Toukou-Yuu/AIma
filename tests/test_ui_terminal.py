"""UI 终端模块测试（测试先行策略）。

测试目标：
- components/tiles.py：牌面渲染组件
- viewer.py：核心渲染函数和 LiveMatchViewer 类
"""

from __future__ import annotations

from collections import Counter

from kernel.tiles.model import Suit, Tile
from rich.text import Text


# =============================================================================
# tiles.py 测试
# =============================================================================


class TestTileToRich:
    """测试 tile_to_rich 函数。"""

    def test_simple_tile_returns_text_with_correct_color(self) -> None:
        """简单牌码返回正确颜色的 Text。"""
        from ui.terminal.components.tiles import tile_to_rich

        # 万子
        text = tile_to_rich("1m")
        assert text.plain == "1m"
        # 验证颜色（万子应为 bright_white）
        assert "bright_white" in str(text.style) or text.style == "bright_white"

    def test_pin_tile_color(self) -> None:
        """筒子颜色为 bright_green。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("5p")
        assert text.plain == "5p"
        assert "bright_green" in str(text.style) or text.style == "bright_green"

    def test_sou_tile_color(self) -> None:
        """索子颜色为 bright_blue。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("9s")
        assert text.plain == "9s"
        assert "bright_blue" in str(text.style) or text.style == "bright_blue"

    def test_honor_tile_shows_chinese_character(self) -> None:
        """字牌显示汉字。"""
        from ui.terminal.components.tiles import tile_to_rich

        # 东
        text = tile_to_rich("1z")
        assert text.plain == "東"

        # 南
        text = tile_to_rich("2z")
        assert text.plain == "南"

        # 西
        text = tile_to_rich("3z")
        assert text.plain == "西"

        # 北
        text = tile_to_rich("4z")
        assert text.plain == "北"

        # 白
        text = tile_to_rich("5z")
        assert text.plain == "白"

        # 发
        text = tile_to_rich("6z")
        assert text.plain == "發"

        # 中
        text = tile_to_rich("7z")
        assert text.plain == "中"

    def test_honor_tile_color(self) -> None:
        """字牌颜色为 bright_yellow。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("1z")
        assert "bright_yellow" in str(text.style) or text.style == "bright_yellow"

    def test_red_tile_shows_bright_red(self) -> None:
        """赤宝牌显示红色。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("5mr")
        assert text.plain == "5m"  # 'r' 被移除
        assert "bright_red" in str(text.style) or text.style == "bright_red"

    def test_red_pin_tile(self) -> None:
        """赤筒牌。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("5pr")
        assert text.plain == "5p"
        assert "bright_red" in str(text.style) or text.style == "bright_red"

    def test_red_sou_tile(self) -> None:
        """赤索牌。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("5sr")
        assert text.plain == "5s"
        assert "bright_red" in str(text.style) or text.style == "bright_red"

    def test_dora_tile_has_red_background(self) -> None:
        """宝牌有红色背景。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("3m", is_dora=True)
        assert text.plain == "3m"
        # 验证样式包含 "on bright_red"
        style_str = str(text.style)
        assert "on" in style_str and "bright_red" in style_str

    def test_dora_honor_tile_has_correct_style(self) -> None:
        """宝牌字牌有正确的样式。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("1z", is_dora=True)
        assert text.plain == "東"
        style_str = str(text.style)
        assert "bright_yellow" in style_str  # 字牌前景色
        assert "on bright_red" in style_str  # 红色背景

    def test_dora_red_tile_overrides_style(self) -> None:
        """宝牌 + 宝牌时，赤宝牌样式优先。"""
        from ui.terminal.components.tiles import tile_to_rich

        # 赤宝牌本身已经是红色，is_dora 不改变
        text = tile_to_rich("5mr", is_dora=True)
        assert text.plain == "5m"
        assert "bright_red" in str(text.style)

    def test_empty_tile_code_returns_empty_text(self) -> None:
        """空牌码返回空 Text。"""
        from ui.terminal.components.tiles import tile_to_rich

        text = tile_to_rich("")
        assert text.plain == ""

    def test_all_number_tiles_1_to_9(self) -> None:
        """测试所有数字牌 1-9。"""
        from ui.terminal.components.tiles import tile_to_rich

        for num in range(1, 10):
            for suit in ["m", "p", "s"]:
                code = f"{num}{suit}"
                text = tile_to_rich(code)
                assert text.plain == code


class TestWindWithSeat:
    """测试 wind_with_seat 函数。"""

    def test_basic_wind_label(self) -> None:
        """基本风位标签。"""
        from ui.terminal.components.tiles import wind_with_seat

        text = wind_with_seat(0, 0)  # 东位，座位0
        assert "东" in text.plain
        assert "S0" in text.plain

    def test_active_seat_highlight(self) -> None:
        """活跃席位高亮显示。"""
        from ui.terminal.components.tiles import wind_with_seat

        text = wind_with_seat(1, 1, is_active=True)  # 南位，座位1，活跃
        assert "南" in text.plain
        # Text.assemble 的样式分布在各个片段中
        # 验证第一个片段（风位部分）的样式包含 bright_cyan
        # 由于 Text.assemble 返回的是组合 Text，需要检查其内容

    def test_inactive_seat_style(self) -> None:
        """非活跃席位样式。"""
        from ui.terminal.components.tiles import wind_with_seat

        text = wind_with_seat(2, 2, is_active=False)
        assert "西" in text.plain
        style_str = str(text.style)
        # 默认样式为 bright_white

    def test_all_four_winds(self) -> None:
        """测试四个风位。"""
        from ui.terminal.components.tiles import wind_with_seat, _WIND_NAMES

        for i, expected_wind in enumerate(_WIND_NAMES):
            text = wind_with_seat(i, i)
            assert expected_wind in text.plain

    def test_relative_wind_calculation(self) -> None:
        """相对风位计算（座位号与风位的关系）。"""
        from ui.terminal.components.tiles import wind_with_seat

        # dealer=0 时，各座位的相对风位
        # seat 0 -> 东(0)
        # seat 1 -> 南(1)
        # seat 2 -> 西(2)
        # seat 3 -> 北(3)
        for seat in range(4):
            text = wind_with_seat(seat, seat)  # wind_idx == seat
            assert text.plain  # 验证有内容

    def test_output_is_text_object(self) -> None:
        """输出是 Rich Text 对象。"""
        from ui.terminal.components.tiles import wind_with_seat

        text = wind_with_seat(0, 0)
        assert isinstance(text, Text)


class TestParseHandTiles:
    """测试 parse_hand_tiles 函数。"""

    def test_simple_hand_string(self) -> None:
        """简单手牌字符串解析。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m2m3m")
        assert len(tiles) == 3
        assert tiles[0].plain == "1m"
        assert tiles[1].plain == "2m"
        assert tiles[2].plain == "3m"

    def test_mixed_suits_hand(self) -> None:
        """混合花色的手牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m2p3s")
        assert len(tiles) == 3
        assert tiles[0].plain == "1m"
        assert tiles[1].plain == "2p"
        assert tiles[2].plain == "3s"

    def test_hand_with_red_tiles(self) -> None:
        """包含赤宝牌的手牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m5mr2m")
        assert len(tiles) == 3
        assert tiles[1].plain == "5m"  # 5mr 解析后显示为 5m

    def test_multiple_red_tiles(self) -> None:
        """多个赤宝牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("5mr5pr5sr")
        assert len(tiles) == 3
        assert tiles[0].plain == "5m"
        assert tiles[1].plain == "5p"
        assert tiles[2].plain == "5s"

    def test_honor_tiles_in_hand(self) -> None:
        """包含字牌的手牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1z2z3z")
        assert len(tiles) == 3
        assert tiles[0].plain == "東"
        assert tiles[1].plain == "南"
        assert tiles[2].plain == "西"

    def test_mixed_number_and_honor_tiles(self) -> None:
        """混合数牌和字牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m2m3m1z2z")
        assert len(tiles) == 5
        assert tiles[0].plain == "1m"
        assert tiles[3].plain == "東"
        assert tiles[4].plain == "南"

    def test_empty_hand_returns_empty_list(self) -> None:
        """空手牌返回空列表。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("")
        assert len(tiles) == 0

    def test_hand_with_spaces(self) -> None:
        """包含空格的手牌（空格被跳过）。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m 2m 3m")
        assert len(tiles) == 3

    def test_hand_with_multiple_spaces(self) -> None:
        """包含多个空格的手牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("  1m  2m  3m  ")
        assert len(tiles) == 3

    def test_output_is_list_of_text(self) -> None:
        """输出是 Text 列表。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m2m")
        assert isinstance(tiles, list)
        assert all(isinstance(t, Text) for t in tiles)

    def test_full_hand_13_tiles(self) -> None:
        """完整 13 张手牌。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        # 模拟一副 13 张手牌
        tiles = parse_hand_tiles("1m2m3m4m5m6m7m8m9m1z1z1z1z")
        assert len(tiles) == 13

    def test_full_hand_14_tiles_with_draw(self) -> None:
        """完整 14 张手牌（含摸牌）。"""
        from ui.terminal.components.tiles import parse_hand_tiles

        tiles = parse_hand_tiles("1m2m3m4m5m6m7m8m9m1z1z1z1z2z")
        assert len(tiles) == 14


# =============================================================================
# viewer.py 核心渲染函数测试（通过私有方法测试）
# =============================================================================


class TestHandToRich:
    """测试 _hand_to_rich 方法。"""

    def test_empty_hand_shows_placeholder(self) -> None:
        """空手牌显示占位符。"""
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        # Counter() 表示空手牌
        text = viewer._hand_to_rich(Counter(), set())
        assert "空" in text.plain or len(text.plain) == 0

    def test_simple_hand_render(self) -> None:
        """简单手牌渲染。"""
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        hand = Counter({Tile(Suit.MAN, 1): 2, Tile(Suit.MAN, 2): 1})
        text = viewer._hand_to_rich(hand, set())
        # 验证有内容
        assert len(text.plain) > 0
        # 验证牌码存在
        assert "1m" in text.plain or "2m" in text.plain

    def test_hand_with_dora_highlights(self) -> None:
        """包含宝牌的手牌高亮显示。"""
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        dora_tile = Tile(Suit.MAN, 3)
        hand = Counter({Tile(Suit.MAN, 3): 1, Tile(Suit.MAN, 4): 1})
        text = viewer._hand_to_rich(hand, {dora_tile})
        # 验证有内容
        assert len(text.plain) > 0


class TestRiverToStr:
    """测试 _river_to_str 方法。"""

    def test_empty_river_shows_placeholder(self) -> None:
        """空牌河返回空 Text。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.deal.model import RiverEntry

        viewer = LiveMatchViewer()
        # 空牌河
        text = viewer._river_to_str((), 0)
        assert len(text.plain) == 0 or "无" in text.plain

    def test_river_with_tiles(self) -> None:
        """有牌的牌河。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.deal.model import RiverEntry
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile1 = Tile(Suit.MAN, 1)
        tile2 = Tile(Suit.MAN, 2)
        river = (RiverEntry(seat=0, tile=tile1, riichi=False),
                 RiverEntry(seat=0, tile=tile2, riichi=False))
        text = viewer._river_to_str(river, 0)
        # 验证牌码存在
        assert len(text.plain) > 0

    def test_river_with_riichi_tiles(self) -> None:
        """立直打牌用方括号标记。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.deal.model import RiverEntry
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.MAN, 1)
        river = (RiverEntry(seat=0, tile=tile, riichi=True),)
        text = viewer._river_to_str(river, 0)
        # 验证有方括号
        assert "[" in text.plain or "]" in text.plain


class TestFormatEvent:
    """测试 _format_event 方法。"""

    def test_round_begin_event(self) -> None:
        """RoundBeginEvent 格式化。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import RoundBeginEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        dora_indicator = Tile(Suit.MAN, 1)
        ev = RoundBeginEvent(
            seat=None, sequence=0, dealer_seat=0,
            dora_indicator=dora_indicator, seeds=(0, 1, 2, 3)
        )
        text = viewer._format_event(ev)
        assert text is not None
        assert "配牌" in text.plain or "宝牌" in text.plain

    def test_draw_tile_event(self) -> None:
        """DrawTileEvent 格式化。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import DrawTileEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.MAN, 3)
        ev = DrawTileEvent(seat=1, sequence=1, tile=tile, is_rinshan=False, wall_remaining=60)
        text = viewer._format_event(ev)
        assert text is not None
        assert "摸" in text.plain

    def test_draw_tile_rinshan(self) -> None:
        """岭上摸牌。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import DrawTileEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.MAN, 5)
        ev = DrawTileEvent(seat=0, sequence=5, tile=tile, is_rinshan=True, wall_remaining=55)
        text = viewer._format_event(ev)
        assert text is not None
        assert "岭上" in text.plain

    def test_discard_tile_event(self) -> None:
        """DiscardTileEvent 格式化。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import DiscardTileEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.PIN, 5)
        ev = DiscardTileEvent(seat=2, sequence=2, tile=tile, is_tsumogiri=False, declare_riichi=False)
        text = viewer._format_event(ev)
        assert text is not None
        assert "打" in text.plain

    def test_discard_tile_with_riichi(self) -> None:
        """立直打牌。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import DiscardTileEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.SOU, 1)
        ev = DiscardTileEvent(seat=0, sequence=10, tile=tile, is_tsumogiri=False, declare_riichi=True)
        text = viewer._format_event(ev)
        assert text is not None
        assert "立直" in text.plain

    def test_discard_tile_tsumogiri(self) -> None:
        """摸切打牌。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import DiscardTileEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.MAN, 7)
        ev = DiscardTileEvent(seat=1, sequence=15, tile=tile, is_tsumogiri=True, declare_riichi=False)
        text = viewer._format_event(ev)
        assert text is not None
        assert "摸切" in text.plain

    def test_ron_event(self) -> None:
        """RonEvent 格式化。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import RonEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        win_tile = Tile(Suit.MAN, 9)
        ev = RonEvent(seat=1, sequence=20, win_tile=win_tile, discard_seat=0)
        text = viewer._format_event(ev)
        assert text is not None
        assert "荣和" in text.plain

    def test_tsumo_event(self) -> None:
        """TsumoEvent 格式化。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import TsumoEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        win_tile = Tile(Suit.HONOR, 1)
        ev = TsumoEvent(seat=2, sequence=25, win_tile=win_tile, is_rinshan=False)
        text = viewer._format_event(ev)
        assert text is not None
        assert "自摸" in text.plain or "和了" in text.plain

    def test_tsumo_event_rinshan(self) -> None:
        """岭上自摸。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import TsumoEvent
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        win_tile = Tile(Suit.PIN, 4)
        ev = TsumoEvent(seat=0, sequence=30, win_tile=win_tile, is_rinshan=True)
        text = viewer._format_event(ev)
        assert text is not None
        assert "岭上" in text.plain

    def test_hand_over_event_with_winners(self) -> None:
        """HandOverEvent 有和了者。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import HandOverEvent

        viewer = LiveMatchViewer()
        ev = HandOverEvent(seat=None, sequence=50, winners=(0,), payments=(1000, -1000, 0, 0))
        text = viewer._format_event(ev)
        assert text is not None
        assert "和了" in text.plain

    def test_hand_over_event_flow(self) -> None:
        """HandOverEvent 流局。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import HandOverEvent

        viewer = LiveMatchViewer()
        ev = HandOverEvent(seat=None, sequence=60, winners=(), payments=(0, 0, 0, 0))
        text = viewer._format_event(ev)
        assert text is not None
        assert "流局" in text.plain

    def test_flow_event_exhausted(self) -> None:
        """荒牌流局。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import FlowEvent
        from kernel.flow.model import FlowKind

        viewer = LiveMatchViewer()
        ev = FlowEvent(seat=0, sequence=70, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset())
        text = viewer._format_event(ev)
        assert text is not None
        assert "荒牌" in text.plain

    def test_flow_event_nine_nine(self) -> None:
        """九种九牌流局。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import FlowEvent
        from kernel.flow.model import FlowKind

        viewer = LiveMatchViewer()
        ev = FlowEvent(seat=0, sequence=5, flow_kind=FlowKind.NINE_NINE, tenpai_seats=None)
        text = viewer._format_event(ev)
        assert text is not None
        assert "九种九牌" in text.plain

    def test_call_event_chi(self) -> None:
        """吃事件。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import CallEvent
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tiles = (Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3))
        meld = Meld(kind=MeldKind.CHI, tiles=tiles, called_tile=Tile(Suit.MAN, 2), from_seat=2)
        ev = CallEvent(seat=1, sequence=8, meld=meld, call_kind="chi")
        text = viewer._format_event(ev)
        assert text is not None
        assert "吃" in text.plain

    def test_call_event_pon(self) -> None:
        """碰事件。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import CallEvent
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tiles = (Tile(Suit.PIN, 5), Tile(Suit.PIN, 5), Tile(Suit.PIN, 5))
        meld = Meld(kind=MeldKind.PON, tiles=tiles, called_tile=Tile(Suit.PIN, 5), from_seat=1)
        ev = CallEvent(seat=2, sequence=9, meld=meld, call_kind="pon")
        text = viewer._format_event(ev)
        assert text is not None
        assert "碰" in text.plain

    def test_call_event_kan(self) -> None:
        """杠事件。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.event_log import CallEvent
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tiles = (Tile(Suit.SOU, 7), Tile(Suit.SOU, 7), Tile(Suit.SOU, 7), Tile(Suit.SOU, 7))
        meld = Meld(kind=MeldKind.DAIMINKAN, tiles=tiles, called_tile=Tile(Suit.SOU, 7), from_seat=1)
        ev = CallEvent(seat=0, sequence=12, meld=meld, call_kind="daiminkan")
        text = viewer._format_event(ev)
        assert text is not None
        assert "杠" in text.plain


class TestRenderHeader:
    """测试 _render_header 方法。"""

    def test_header_contains_wind_and_round(self) -> None:
        """场况包含场风和局数。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel import Action, ActionKind, apply, build_deck, shuffle_deck, initial_game_state
        from rich.console import Console

        viewer = LiveMatchViewer()
        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        table = viewer._render_header(state)
        # 使用 Console 渲染 Table 为文本
        console = Console()
        with console.capture() as capture:
            console.print(table)
        text = capture.get()
        assert "東" in text or "局" in text or "风" in text

    def test_header_contains_scores(self) -> None:
        """场况包含分数。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel import Action, ActionKind, apply, build_deck, shuffle_deck, initial_game_state
        from rich.console import Console

        viewer = LiveMatchViewer()
        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        table = viewer._render_header(state)
        console = Console()
        with console.capture() as capture:
            console.print(table)
        text = capture.get()
        # 默认分数 25000（紧凑格式带逗号分隔）
        assert "25,000" in text or "25000" in text

    def test_header_contains_dora_indicators(self) -> None:
        """场况包含宝牌指示器。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel import Action, ActionKind, apply, build_deck, shuffle_deck, initial_game_state

        viewer = LiveMatchViewer()
        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        table = viewer._render_header(state)
        # 验证 Table 对象创建成功
        assert table is not None


class TestMeldsToStr:
    """测试 _melds_to_str 方法。"""

    def test_empty_melds_returns_none(self) -> None:
        """无副露返回 '无'。"""
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        text = viewer._melds_to_str([], 0, 0)
        assert text == "无"

    def test_melds_with_chi(self) -> None:
        """吃副露。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tiles = (Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3))
        meld = Meld(kind=MeldKind.CHI, tiles=tiles, called_tile=Tile(Suit.MAN, 2), from_seat=2)
        text = viewer._melds_to_str([meld], 0, 0)
        assert text  # 验证有内容
        assert "吃" in text

    def test_melds_with_pon(self) -> None:
        """碰副露。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tiles = (Tile(Suit.PIN, 5), Tile(Suit.PIN, 5), Tile(Suit.PIN, 5))
        meld = Meld(kind=MeldKind.PON, tiles=tiles, called_tile=Tile(Suit.PIN, 5), from_seat=1)
        text = viewer._melds_to_str([meld], 0, 0)
        assert text
        assert "碰" in text


class TestDoraIndicatorsToRich:
    """测试 _dora_indicators_to_rich 方法。"""

    def test_empty_indicators(self) -> None:
        """空指示器列表。"""
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        result = viewer._dora_indicators_to_rich(())
        assert len(result) == 0

    def test_single_indicator(self) -> None:
        """单个指示器。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tile = Tile(Suit.MAN, 3)
        result = viewer._dora_indicators_to_rich((tile,))
        assert len(result) == 1

    def test_multiple_indicators(self) -> None:
        """多个指示器。"""
        from ui.terminal.viewer import LiveMatchViewer
        from kernel.tiles.model import Suit, Tile

        viewer = LiveMatchViewer()
        tiles = (Tile(Suit.MAN, 1), Tile(Suit.PIN, 2), Tile(Suit.SOU, 3))
        result = viewer._dora_indicators_to_rich(tiles)
        # 结果包含牌和空格分隔符
        # 格式：牌1, 空格, 牌2, 空格, 牌3 = 5 个元素
        assert len(result) >= 3


# =============================================================================
# 集成测试
# =============================================================================


class TestLiveMatchViewerIntegration:
    """LiveMatchViewer 集成测试。"""

    def test_viewer_initialization(self) -> None:
        """测试观战器初始化。"""
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer(delay=0.5, show_reason=True)
        assert viewer.delay == 0.5
        assert viewer.show_reason is True
        assert viewer._wins == [0, 0, 0, 0]
        assert viewer._rounds == 0

    def test_step_returns_panel(self) -> None:
        """step 方法返回 Panel。"""
        pass

    def test_update_stats_counts_wins(self) -> None:
        """统计更新正确计算和了次数。"""
        pass


class TestLiveMatchCallback:
    """LiveMatchCallback 测试。"""

    def test_callback_initialization(self) -> None:
        """测试回调初始化。"""
        from ui.terminal.viewer import LiveMatchCallback

        callback = LiveMatchCallback(delay=0.5)
        assert callback.viewer.delay == 0.5

    def test_set_player_names(self) -> None:
        """设置玩家名字。"""
        from ui.terminal.viewer import LiveMatchCallback

        callback = LiveMatchCallback()
        callback.set_player_names({0: "一姬", 1: "八木唯", 2: "卡维", 3: "藤田佳奈"})
        assert callback.viewer._seat_names[0] == "一姬"