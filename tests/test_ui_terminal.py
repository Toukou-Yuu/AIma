"""UI 终端模块测试（测试先行策略）。

测试目标：
- components/tiles.py：牌面渲染组件
- viewer.py：核心渲染函数和 LiveMatchViewer 类
"""

from __future__ import annotations

from collections import Counter

from rich.cells import cell_len
from rich.text import Text

from kernel.tiles.model import Suit, Tile


def _make_event_formatter():
    from ui.terminal.components import EventFormatter, NameResolver

    return EventFormatter(NameResolver())


def _make_hand_display(names: dict[int, str] | None = None):
    from ui.terminal.components import HandDisplay, NameResolver, TileRenderer

    resolver = NameResolver()
    if names:
        resolver.set_seat_names(names)
    return HandDisplay(TileRenderer(), resolver)


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


class TestTileCodeLocalization:
    """测试牌码文本本地化。"""

    def test_tile_code_to_display_translates_honor_tiles(self) -> None:
        from ui.terminal.components.tiles import tile_code_to_display

        assert tile_code_to_display("1z") == "東"
        assert tile_code_to_display("2z") == "南"

    def test_localize_tile_codes_keeps_suited_tiles_and_translates_honors(self) -> None:
        from ui.terminal.components.tiles import localize_tile_codes

        assert localize_tile_codes("打牌 1z 2m") == "打牌 東 2m"
        assert localize_tile_codes("碰[1z1z1z]") == "碰[東東東]"


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
        # 默认样式为 bright_white

    def test_all_four_winds(self) -> None:
        """测试四个风位。"""
        from ui.terminal.components.tiles import _WIND_NAMES, wind_with_seat

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


class TestNameResolverHandLabels:
    """测试手牌区标签格式。"""

    def test_format_hand_label_uses_name_and_relative_wind(self) -> None:
        from ui.terminal.components.name_resolver import NameResolver

        resolver = NameResolver({0: "一姬", 1: "超级长名字"})

        assert resolver.format_hand_label(0, 0) == "一姬[东]："
        assert resolver.format_hand_label(1, 0) == "超级长名字[南]："


class TestHandDisplayLabels:
    """测试手牌区标签对齐。"""

    def test_render_hand_label_uses_fixed_column_width(self) -> None:
        from ui.terminal.components.hand_display import HandDisplay
        from ui.terminal.components.name_resolver import NameResolver
        from ui.terminal.components.render import TileRenderer

        resolver = NameResolver({0: "一姬", 1: "超级长名字"})
        display = HandDisplay(TileRenderer(), resolver)
        labels = [
            resolver.format_hand_label(0, 0),
            resolver.format_hand_label(1, 0),
        ]

        width = display._compute_label_width(labels)
        short_label = display._render_hand_label(labels[0], width, False)
        long_label = display._render_hand_label(labels[1], width, False)

        assert cell_len(short_label.plain) == width
        assert cell_len(long_label.plain) == width

    def test_compact_mode_preserves_tree_and_separate_detail_lines(self) -> None:
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.components.hand_display import HandDisplay
        from ui.terminal.components.name_resolver import NameResolver
        from ui.terminal.components.render import TileRenderer

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        state = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck)).new_state

        display = HandDisplay(TileRenderer(), NameResolver({0: "一姬"}))
        group = display.render_player_tree(state, mode="compact")

        rendered = "\n".join(segment.plain for segment in group.renderables)
        assert "一姬[东]：" in rendered
        assert "├── 一姬[东]：" in rendered
        assert "25,000" not in rendered
        assert "和0" not in rendered
        assert "│   ├── 副露:" in rendered
        assert "│   └── 牌河:" in rendered
        assert "牌河: 无" in rendered
        assert "河尾" not in rendered

    def test_full_mode_preserves_each_seat_reason(self) -> None:
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.components.hand_display import HandDisplay
        from ui.terminal.components.name_resolver import NameResolver
        from ui.terminal.components.render import TileRenderer

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        state = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck)).new_state

        display = HandDisplay(TileRenderer(), NameResolver({0: "一姬", 1: "二阶堂"}))
        group = display.render_player_tree(
            state,
            last_actor_seat=1,
            seat_reasons={0: "东家旧理由", 1: "南家新理由"},
            show_reason=True,
            mode="full",
        )

        rendered = "\n".join(segment.plain for segment in group.renderables)
        assert "理由: 东家旧理由" in rendered
        assert "理由: 南家新理由" in rendered
        assert "│   ├── 牌河:" in rendered
        assert "│   └── 理由: 东家旧理由" in rendered


class TestCharacterCardLayout:
    """测试角色卡片布局约束。"""

    def test_memory_bias_wraps_by_display_width(self) -> None:
        from ui.terminal.components.character_card import INFO_CONTENT_WIDTH, _wrap_text_by_cells

        label_width = cell_len("整体风格: ")
        long_bias = "极端进攻型但会在危险巡目突然转向绝对防守" * 3
        lines = _wrap_text_by_cells(long_bias, INFO_CONTENT_WIDTH - label_width)

        assert len(lines) > 1
        assert all(cell_len(line) <= INFO_CONTENT_WIDTH - label_width for line in lines)


class TestLayoutBuilderResponsive:
    """测试 live 布局的响应式分栏。"""

    def test_build_panel_uses_sidebar_panels(self) -> None:
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.components.event_formatter import EventFormatter
        from ui.terminal.components.hand_display import HandDisplay
        from ui.terminal.components.layout_builder import LayoutBuilder
        from ui.terminal.components.name_resolver import NameResolver
        from ui.terminal.components.render import TileRenderer
        from ui.terminal.components.stats_tracker import StatsTracker

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        renderer = TileRenderer()
        resolver = NameResolver({0: "一姬"})
        stats = StatsTracker()
        stats.update_from_events(outcome.events)
        layout = LayoutBuilder(
            renderer,
            stats,
            EventFormatter(resolver),
            HandDisplay(renderer, resolver),
            resolver,
        )

        panel = layout.build_panel(
            state,
            outcome.events,
            viewport_width=120,
            viewport_height=24,
        )

        assert panel.title is None
        assert panel.renderable is not None

    def test_sidebar_status_panel_keeps_only_table_status(self) -> None:
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.components.event_formatter import EventFormatter
        from ui.terminal.components.hand_display import HandDisplay
        from ui.terminal.components.layout_builder import LayoutBuilder
        from ui.terminal.components.name_resolver import NameResolver
        from ui.terminal.components.render import TileRenderer
        from ui.terminal.components.stats_tracker import StatsTracker

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        renderer = TileRenderer()
        resolver = NameResolver({0: "一姬", 1: "二阶堂"})
        stats = StatsTracker({0: "一姬", 1: "二阶堂"})
        layout = LayoutBuilder(
            renderer,
            stats,
            EventFormatter(resolver),
            HandDisplay(renderer, resolver),
            resolver,
        )
        layout.set_session_summary(seed=42, target_label="单局演示")

        profile = layout._select_profile(120, 30)
        lines = layout._build_sidebar_status_lines(
            state,
            active_seat=0,
            profile=profile,
        )
        rendered = "\n".join(line.plain for line in lines)

        assert "对局设置" in rendered
        assert "seed 42" in rendered
        assert "目标 单局演示" in rendered
        assert "点数 / 和了统计（已终局 0 局）" in rendered
        assert "一姬 25,000点" in rendered
        assert "二阶堂 25,000点" in rendered
        assert "和了 0/0局 · 和了率 --" in rendered
        assert "宝牌" in rendered


class TestStatsTrackerSidebar:
    """测试右栏和了统计。"""

    def test_render_sidebar_uses_player_names(self) -> None:
        from ui.terminal.components.stats_tracker import StatsTracker

        tracker = StatsTracker({0: "一姬", 1: "二阶堂", 2: "三上", 3: "四宫"})
        sidebar = tracker.render_sidebar(dealer_seat=0)
        rendered = "\n".join(line.plain for line in sidebar.renderables)

        assert "一姬" in rendered
        assert "二阶堂" in rendered
        assert "和了 0/0局" in rendered
        assert "和了率 --" in rendered
        assert "东家" not in rendered


class TestTokenBudgetDisplay:
    """测试上下文 token 压力展示。"""

    def test_full_sidebar_uses_compact_two_line_layout(self) -> None:
        from llm.agent.token_budget import BlockTokenUsage, PromptDiagnostics
        from ui.terminal.components.token_budget_display import TokenBudgetDisplay

        diagnostics = PromptDiagnostics(
            estimated_tokens=4800,
            prompt_budget_tokens=6656,
            max_context_tokens=8192,
            max_output_tokens=1024,
            context_compression_threshold=0.9375,
            selected_blocks=(
                BlockTokenUsage(
                    block_id="current_turn",
                    role="user",
                    priority=0,
                    required=True,
                    state="collapse",
                    estimated_tokens=4800,
                ),
            ),
            trimmed_blocks=(),
            max_compression_state="collapse",
            over_budget=False,
        )

        group = TokenBudgetDisplay().render_sidebar(diagnostics)
        rendered = "\n".join(line.plain for line in group.renderables)

        assert "4.8k / 6.7k -- [" in rendered
        assert "72%" in rendered
        assert "collapse · 正常" in rendered

    def test_compact_sidebar_mentions_trimmed_blocks(self) -> None:
        from llm.agent.token_budget import PromptDiagnostics
        from ui.terminal.components.token_budget_display import TokenBudgetDisplay

        diagnostics = PromptDiagnostics(
            estimated_tokens=9,
            prompt_budget_tokens=10,
            max_context_tokens=11,
            max_output_tokens=1,
            context_compression_threshold=1.0,
            selected_blocks=(),
            trimmed_blocks=("public_history",),
            max_compression_state="drop",
            over_budget=False,
        )

        group = TokenBudgetDisplay().render_sidebar(diagnostics, compact=True)
        rendered = "\n".join(line.plain for line in group.renderables)

        assert "9/10 · 90% · drop · 丢弃 公共事件" in rendered

    def test_inline_context_uses_full_request_token_count(self) -> None:
        from llm.agent.token_budget import BlockTokenUsage, PromptDiagnostics
        from ui.terminal.components.token_budget_display import TokenBudgetDisplay

        diagnostics = PromptDiagnostics(
            estimated_tokens=4800,
            prompt_budget_tokens=6656,
            max_context_tokens=8192,
            max_output_tokens=1024,
            context_compression_threshold=0.9375,
            selected_blocks=(
                BlockTokenUsage(
                    block_id="public_history",
                    role="user",
                    priority=30,
                    required=False,
                    state="collapse",
                    estimated_tokens=3700,
                ),
                BlockTokenUsage(
                    block_id="current_turn",
                    role="user",
                    priority=0,
                    required=True,
                    state="full",
                    estimated_tokens=1100,
                ),
            ),
            trimmed_blocks=(),
            max_compression_state="collapse",
            over_budget=False,
        )

        line = TokenBudgetDisplay().render_inline(diagnostics, active=True)

        assert "█████████░░░ 72% (4.8k / 6.7k)" in line.plain
        assert "本轮请求 4.8k" in line.plain
        assert "status: collapse · 正常" in line.plain


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
# terminal components 公共 API 测试
# =============================================================================


class TestTileRendererHand:
    """测试 TileRenderer.render_hand。"""

    def test_empty_hand_shows_placeholder(self) -> None:
        """空手牌显示占位符。"""
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        # Counter() 表示空手牌
        text = renderer.render_hand(Counter(), set())
        assert "空" in text.plain or len(text.plain) == 0

    def test_simple_hand_render(self) -> None:
        """简单手牌渲染。"""
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        hand = Counter({Tile(Suit.MAN, 1): 2, Tile(Suit.MAN, 2): 1})
        text = renderer.render_hand(hand, set())
        # 验证有内容
        assert len(text.plain) > 0
        # 验证牌码存在
        assert "1m" in text.plain or "2m" in text.plain

    def test_hand_with_dora_highlights(self) -> None:
        """包含宝牌的手牌高亮显示。"""
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        dora_tile = Tile(Suit.MAN, 3)
        hand = Counter({Tile(Suit.MAN, 3): 1, Tile(Suit.MAN, 4): 1})
        text = renderer.render_hand(hand, {dora_tile})
        # 验证有内容
        assert len(text.plain) > 0


class TestTileRendererRiver:
    """测试 TileRenderer.render_river。"""

    def test_empty_river_shows_placeholder(self) -> None:
        """空牌河返回空 Text。"""
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        # 空牌河
        text = renderer.render_river((), 0, set())
        assert len(text.plain) == 0 or "无" in text.plain

    def test_river_with_tiles(self) -> None:
        """有牌的牌河。"""
        from kernel.deal.model import RiverEntry
        from kernel.tiles.model import Suit, Tile
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        tile1 = Tile(Suit.MAN, 1)
        tile2 = Tile(Suit.MAN, 2)
        river = (RiverEntry(seat=0, tile=tile1, riichi=False),
                 RiverEntry(seat=0, tile=tile2, riichi=False))
        text = renderer.render_river(river, 0, set())
        # 验证牌码存在
        assert len(text.plain) > 0

    def test_river_with_riichi_tiles(self) -> None:
        """立直打牌用方括号标记。"""
        from kernel.deal.model import RiverEntry
        from kernel.tiles.model import Suit, Tile
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        tile = Tile(Suit.MAN, 1)
        river = (RiverEntry(seat=0, tile=tile, riichi=True),)
        text = renderer.render_river(river, 0, set())
        # 验证有方括号
        assert "[" in text.plain or "]" in text.plain


class TestFormatEvent:
    """测试 EventFormatter.format_event。"""

    def test_round_begin_event(self) -> None:
        """RoundBeginEvent 格式化。"""
        from kernel.event_log import RoundBeginEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        dora_indicator = Tile(Suit.MAN, 1)
        ev = RoundBeginEvent(
            seat=None, sequence=0, dealer_seat=0,
            dora_indicator=dora_indicator, seeds=(0, 1, 2, 3)
        )
        text = formatter.format_event(ev)
        assert text is not None
        assert "配牌" in text.plain or "宝牌" in text.plain

    def test_draw_tile_event(self) -> None:
        """DrawTileEvent 格式化。"""
        from kernel.event_log import DrawTileEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tile = Tile(Suit.MAN, 3)
        ev = DrawTileEvent(seat=1, sequence=1, tile=tile, is_rinshan=False, wall_remaining=60)
        text = formatter.format_event(ev)
        assert text is not None
        assert "摸" in text.plain

    def test_draw_tile_rinshan(self) -> None:
        """岭上摸牌。"""
        from kernel.event_log import DrawTileEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tile = Tile(Suit.MAN, 5)
        ev = DrawTileEvent(seat=0, sequence=5, tile=tile, is_rinshan=True, wall_remaining=55)
        text = formatter.format_event(ev)
        assert text is not None
        assert "岭上" in text.plain

    def test_discard_tile_event(self) -> None:
        """DiscardTileEvent 格式化。"""
        from kernel.event_log import DiscardTileEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tile = Tile(Suit.PIN, 5)
        ev = DiscardTileEvent(
            seat=2,
            sequence=2,
            tile=tile,
            is_tsumogiri=False,
            declare_riichi=False,
        )
        text = formatter.format_event(ev)
        assert text is not None
        assert "打" in text.plain

    def test_discard_tile_with_riichi(self) -> None:
        """立直打牌。"""
        from kernel.event_log import DiscardTileEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tile = Tile(Suit.SOU, 1)
        ev = DiscardTileEvent(
            seat=0,
            sequence=10,
            tile=tile,
            is_tsumogiri=False,
            declare_riichi=True,
        )
        text = formatter.format_event(ev)
        assert text is not None
        assert "立直" in text.plain

    def test_discard_tile_tsumogiri(self) -> None:
        """摸切打牌。"""
        from kernel.event_log import DiscardTileEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tile = Tile(Suit.MAN, 7)
        ev = DiscardTileEvent(
            seat=1,
            sequence=15,
            tile=tile,
            is_tsumogiri=True,
            declare_riichi=False,
        )
        text = formatter.format_event(ev)
        assert text is not None
        assert "摸切" in text.plain

    def test_ron_event(self) -> None:
        """RonEvent 格式化。"""
        from kernel.event_log import RonEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        win_tile = Tile(Suit.MAN, 9)
        ev = RonEvent(seat=1, sequence=20, win_tile=win_tile, discard_seat=0)
        text = formatter.format_event(ev)
        assert text is not None
        assert "荣和" in text.plain

    def test_tsumo_event(self) -> None:
        """TsumoEvent 格式化。"""
        from kernel.event_log import TsumoEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        win_tile = Tile(Suit.HONOR, 1)
        ev = TsumoEvent(seat=2, sequence=25, win_tile=win_tile, is_rinshan=False)
        text = formatter.format_event(ev)
        assert text is not None
        assert "自摸" in text.plain or "和了" in text.plain

    def test_tsumo_event_rinshan(self) -> None:
        """岭上自摸。"""
        from kernel.event_log import TsumoEvent
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        win_tile = Tile(Suit.PIN, 4)
        ev = TsumoEvent(seat=0, sequence=30, win_tile=win_tile, is_rinshan=True)
        text = formatter.format_event(ev)
        assert text is not None
        assert "岭上" in text.plain

    def test_hand_over_event_with_winners(self) -> None:
        """HandOverEvent 有和了者。"""
        from kernel.event_log import HandOverEvent
        formatter = _make_event_formatter()
        ev = HandOverEvent(seat=None, sequence=50, winners=(0,), payments=(1000, -1000, 0, 0))
        text = formatter.format_event(ev)
        assert text is not None
        assert "和了" in text.plain

    def test_hand_over_event_flow(self) -> None:
        """HandOverEvent 流局。"""
        from kernel.event_log import HandOverEvent
        formatter = _make_event_formatter()
        ev = HandOverEvent(seat=None, sequence=60, winners=(), payments=(0, 0, 0, 0))
        text = formatter.format_event(ev)
        assert text is not None
        assert "流局" in text.plain

    def test_flow_event_exhausted(self) -> None:
        """荒牌流局。"""
        from kernel.event_log import FlowEvent
        from kernel.flow.model import FlowKind
        formatter = _make_event_formatter()
        ev = FlowEvent(seat=0, sequence=70, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset())
        text = formatter.format_event(ev)
        assert text is not None
        assert "荒牌" in text.plain

    def test_flow_event_nine_nine(self) -> None:
        """九种九牌流局。"""
        from kernel.event_log import FlowEvent
        from kernel.flow.model import FlowKind
        formatter = _make_event_formatter()
        ev = FlowEvent(seat=0, sequence=5, flow_kind=FlowKind.NINE_NINE, tenpai_seats=None)
        text = formatter.format_event(ev)
        assert text is not None
        assert "九种九牌" in text.plain

    def test_call_event_chi(self) -> None:
        """吃事件。"""
        from kernel.event_log import CallEvent
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tiles = (Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3))
        meld = Meld(kind=MeldKind.CHI, tiles=tiles, called_tile=Tile(Suit.MAN, 2), from_seat=2)
        ev = CallEvent(seat=1, sequence=8, meld=meld, call_kind="chi")
        text = formatter.format_event(ev)
        assert text is not None
        assert "吃" in text.plain

    def test_call_event_pon(self) -> None:
        """碰事件。"""
        from kernel.event_log import CallEvent
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tiles = (Tile(Suit.PIN, 5), Tile(Suit.PIN, 5), Tile(Suit.PIN, 5))
        meld = Meld(kind=MeldKind.PON, tiles=tiles, called_tile=Tile(Suit.PIN, 5), from_seat=1)
        ev = CallEvent(seat=2, sequence=9, meld=meld, call_kind="pon")
        text = formatter.format_event(ev)
        assert text is not None
        assert "碰" in text.plain

    def test_call_event_kan(self) -> None:
        """杠事件。"""
        from kernel.event_log import CallEvent
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        formatter = _make_event_formatter()
        tiles = (Tile(Suit.SOU, 7), Tile(Suit.SOU, 7), Tile(Suit.SOU, 7), Tile(Suit.SOU, 7))
        meld = Meld(
            kind=MeldKind.DAIMINKAN,
            tiles=tiles,
            called_tile=Tile(Suit.SOU, 7),
            from_seat=1,
        )
        ev = CallEvent(seat=0, sequence=12, meld=meld, call_kind="daiminkan")
        text = formatter.format_event(ev)
        assert text is not None
        assert "杠" in text.plain


class TestTableSummary:
    """测试 LiveMatchViewer.describe_table。"""

    def test_header_contains_wind_and_round(self) -> None:
        """场况包含场风和局数。"""
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        summary = viewer.describe_table(state)
        text = f"{summary.summary_line}\n{summary.score_line}"
        assert "東" in text or "局" in text or "风" in text

    def test_header_contains_scores(self) -> None:
        """场况包含分数。"""
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        summary = viewer.describe_table(state)
        text = f"{summary.summary_line}\n{summary.score_line}"
        # 默认分数 25000（紧凑格式带逗号分隔）
        assert "25,000" in text or "25000" in text

    def test_header_contains_dora_indicators(self) -> None:
        """场况包含宝牌指示器。"""
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        outcome = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck))
        state = outcome.new_state

        summary = viewer.describe_table(state)
        text = f"{summary.summary_line}\n{summary.score_line}"
        assert "宝牌指示器" in text


class TestMeldDisplay:
    """测试 HandDisplay 副露格式化。"""

    def test_empty_melds_returns_none(self) -> None:
        """无副露返回 '无'。"""
        display = _make_hand_display()
        text = display.format_melds([], 0)
        assert text == "无"

    def test_melds_with_chi(self) -> None:
        """吃副露。"""
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        display = _make_hand_display()
        tiles = (Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3))
        meld = Meld(kind=MeldKind.CHI, tiles=tiles, called_tile=Tile(Suit.MAN, 2), from_seat=2)
        text = display.format_melds([meld], 0)
        assert text  # 验证有内容
        assert "吃" in text

    def test_melds_with_pon(self) -> None:
        """碰副露。"""
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        display = _make_hand_display()
        tiles = (Tile(Suit.PIN, 5), Tile(Suit.PIN, 5), Tile(Suit.PIN, 5))
        meld = Meld(kind=MeldKind.PON, tiles=tiles, called_tile=Tile(Suit.PIN, 5), from_seat=1)
        text = display.format_melds([meld], 0)
        assert text
        assert "碰" in text

    def test_melds_use_player_name_and_localize_honor_tiles(self) -> None:
        """副露来源显示角色名，字牌不泄漏 raw code。"""
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        display = _make_hand_display({2: "卡维"})
        east = Tile(Suit.HONOR, 1)
        meld = Meld(
            kind=MeldKind.PON,
            tiles=(east, east, east),
            called_tile=east,
            from_seat=2,
        )

        text = display.format_melds([meld], 0)

        assert text == "碰卡维[東東東]"
        assert "1z" not in text
        assert "东家" not in text

    def test_compact_melds_localize_honor_tiles(self) -> None:
        """紧凑副露也必须复用牌面本地化。"""
        from kernel.hand.melds import Meld, MeldKind
        from kernel.tiles.model import Suit, Tile
        from ui.terminal.components.hand_display import HandDisplay
        from ui.terminal.components.name_resolver import NameResolver
        from ui.terminal.components.render import TileRenderer

        east = Tile(Suit.HONOR, 1)
        meld = Meld(
            kind=MeldKind.PON,
            tiles=(east, east, east),
            called_tile=east,
            from_seat=1,
        )
        display = HandDisplay(TileRenderer(), NameResolver())

        assert display.format_melds_compact([meld]) == "碰[東東東]"


class TestDoraIndicators:
    """测试 TileRenderer.render_dora_indicators。"""

    def test_empty_indicators(self) -> None:
        """空指示器列表。"""
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        result = renderer.render_dora_indicators(())
        assert len(result) == 0

    def test_single_indicator(self) -> None:
        """单个指示器。"""
        from kernel.tiles.model import Suit, Tile
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        tile = Tile(Suit.MAN, 3)
        result = renderer.render_dora_indicators((tile,))
        assert len(result) == 1

    def test_multiple_indicators(self) -> None:
        """多个指示器。"""
        from kernel.tiles.model import Suit, Tile
        from ui.terminal.components import TileRenderer

        renderer = TileRenderer()
        tiles = (Tile(Suit.MAN, 1), Tile(Suit.PIN, 2), Tile(Suit.SOU, 3))
        result = renderer.render_dora_indicators(tiles)
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

    def test_step_returns_panel(self) -> None:
        """step 方法返回 Panel。"""
        from rich.panel import Panel

        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from ui.terminal.viewer import LiveMatchViewer

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        state = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck)).new_state
        viewer = LiveMatchViewer()

        assert isinstance(viewer.step(state, (), "家0 discard"), Panel)

    def test_step_marks_missing_llm_reason_explicitly(self) -> None:
        """真实 LLM 请求缺少 why 时，理由区显示明确占位。"""
        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from llm.agent.token_budget import PromptDiagnostics
        from ui.terminal.viewer import LiveMatchViewer

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        state = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck)).new_state
        diagnostics = PromptDiagnostics(
            estimated_tokens=900,
            prompt_budget_tokens=1000,
            max_context_tokens=1200,
            max_output_tokens=200,
            context_compression_threshold=1.0,
            selected_blocks=(),
            trimmed_blocks=(),
            max_compression_state="full",
            over_budget=False,
        )
        viewer = LiveMatchViewer(show_reason=True)

        viewer.step(state, (), "家0 打牌 1m", "", prompt_diagnostics=diagnostics)

        assert viewer._seat_reasons[0] == "未提供理由"

    def test_update_stats_counts_wins(self) -> None:
        """统计更新正确计算和了次数。"""
        from kernel.event_log import HandOverEvent
        from ui.terminal.components import StatsTracker

        tracker = StatsTracker()
        tracker.update_from_events(
            (
                HandOverEvent(
                    seat=None,
                    sequence=1,
                    winners=(2,),
                    payments=(0, 0, 0, 0),
                ),
            )
        )
        snapshot = tracker.snapshot()

        assert snapshot.wins == (0, 0, 1, 0)
        assert snapshot.rounds == 1

    def test_prompt_diagnostics_persist_per_seat(self) -> None:
        """上下文诊断按座位持久化，而不是只显示最新一次。"""
        from rich.console import Console

        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from llm.agent.token_budget import BlockTokenUsage, PromptDiagnostics
        from ui.terminal.viewer import LiveMatchViewer

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        state = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck)).new_state
        diagnostics = PromptDiagnostics(
            estimated_tokens=4800,
            prompt_budget_tokens=6656,
            max_context_tokens=8192,
            max_output_tokens=1024,
            context_compression_threshold=0.9375,
            selected_blocks=(
                BlockTokenUsage(
                    block_id="current_turn",
                    role="user",
                    priority=0,
                    required=True,
                    state="full",
                    estimated_tokens=1200,
                ),
            ),
            trimmed_blocks=(),
            max_compression_state="collapse",
            over_budget=False,
        )
        viewer = LiveMatchViewer()
        viewer.set_player_names({0: "一姬", 1: "二阶堂"})
        viewer.step(state, (), "家0 discard", "理由", prompt_diagnostics=diagnostics)
        panel = viewer.step(state, (), "家1 discard", "")
        console = Console(width=220, color_system=None)

        with console.capture() as capture:
            console.print(panel)

        rendered = capture.get()
        assert "一姬[东]" in rendered
        assert "有效上下文: █████████░░░ 72% (4.8k / 6.7k)" in rendered
        assert "本轮请求 4.8k" in rendered
        assert "collapse · 正常" in rendered

    def test_event_history_persists_multiple_steps(self) -> None:
        """事件面板显示历史事件，而不是只显示当前 step 事件。"""
        from rich.console import Console

        from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
        from kernel.event_log import DiscardTileEvent, DrawTileEvent
        from kernel.tiles.model import Suit, Tile
        from ui.terminal.viewer import LiveMatchViewer

        state = initial_game_state()
        deck = tuple(shuffle_deck(build_deck(), seed=42))
        state = apply(state, Action(ActionKind.BEGIN_ROUND, wall=deck)).new_state
        viewer = LiveMatchViewer()
        viewer.step(
            state,
            (
                DrawTileEvent(
                    seat=0,
                    sequence=1,
                    tile=Tile(Suit.MAN, 1),
                    is_rinshan=False,
                    wall_remaining=69,
                ),
            ),
            "家0 draw",
        )
        panel = viewer.step(
            state,
            (
                DiscardTileEvent(
                    seat=1,
                    sequence=2,
                    tile=Tile(Suit.HONOR, 1),
                    is_tsumogiri=False,
                    declare_riichi=False,
                ),
            ),
            "家1 discard",
        )
        console = Console(width=220, color_system=None)

        with console.capture() as capture:
            console.print(panel)

        rendered = capture.get()
        assert "从本墙摸" in rendered
        assert "打 東" in rendered


class TestLiveMatchViewerActionLabels:
    """测试动作标签本地化。"""

    def test_format_action_label_uses_player_name_and_localizes_kind(self) -> None:
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        viewer.set_player_names({0: "一姬"})

        assert viewer.format_action_label("家0 discard") == "一姬 打牌"

    def test_format_action_label_normalizes_discard_with_tile(self) -> None:
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        viewer.set_player_names({2: "卡维"})

        assert viewer.format_action_label("家2 打 3m") == "卡维 打牌 3m"

    def test_format_action_label_translates_honor_tiles(self) -> None:
        from ui.terminal.viewer import LiveMatchViewer

        viewer = LiveMatchViewer()
        viewer.set_player_names({0: "一姬"})

        assert viewer.format_action_label("家0 打 1z") == "一姬 打牌 東"


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
        assert callback.viewer.format_action_label("家0 discard") == "一姬 打牌"


# =============================================================================
# interactive 导航测试
# =============================================================================


class TestInteractiveNavigation:
    """统一返回导航测试。"""

    def test_page_interrupt_returns_back_by_default(self) -> None:
        """普通页面的 Ctrl+C 会返回上一层。"""
        from ui.interactive.framework import BACK, Page

        class SamplePage(Page):
            def _render_content(self) -> None:
                return None

        assert SamplePage()._on_interrupt() is BACK

    def test_main_menu_back_maps_to_quit(self, monkeypatch) -> None:
        """主菜单作为根节点，会把返回动作映射为退出。"""
        from ui.interactive.framework import BACK
        from ui.interactive.main_menu import MainMenuPage, show_main_menu

        monkeypatch.setattr(MainMenuPage, "run", lambda self: BACK)
        assert show_main_menu() == "quit"

    def test_replay_menu_without_records_returns_back(self, monkeypatch) -> None:
        """无牌谱时直接返回上一层，而不是留在死路页面。"""
        from ui.interactive.framework import BACK
        from ui.interactive.replay import Prompt, ReplayMenuPage

        monkeypatch.setattr(Prompt, "press_any_key", lambda message="按任意键继续...": None)
        monkeypatch.setattr(ReplayMenuPage, "_get_choices", lambda self: [])

        assert ReplayMenuPage()._render_content() is BACK

    def test_prompt_confirm_uses_select_navigation(self, monkeypatch) -> None:
        """确认输入走统一选择协议，而不是 questionary.confirm。"""
        from ui.interactive.framework import Prompt

        monkeypatch.setattr(Prompt, "select", lambda *args, **kwargs: False)
        assert Prompt.confirm("确认开始?") is False

    def test_prompt_number_propagates_back(self, monkeypatch) -> None:
        """数字输入通过菜单返回时，不会吞掉导航动作。"""
        from ui.interactive.framework import BACK, Prompt

        monkeypatch.setattr(Prompt, "select", lambda *args, **kwargs: BACK)
        assert Prompt.number("输入观战延迟") is BACK

    def test_prompt_text_can_use_default_without_entering_editor(self, monkeypatch) -> None:
        """文本输入可以直接通过菜单使用默认值。"""
        from ui.interactive.framework import Prompt

        monkeypatch.setattr(Prompt, "select", lambda *args, **kwargs: Prompt._ACTION_USE_DEFAULT)
        assert Prompt.text("显示名称", default="一姬") == "一姬"


class TestQuickStartMenu:
    """demo 菜单测试。"""

    def test_quick_start_build_command_with_watch(self) -> None:
        """观战模式会生成完整的 dry-run demo 命令。"""
        from ui.interactive.match_setup import QuickStartConfig

        config = QuickStartConfig(seed="42", watch=True, delay="0.5")
        assert config.build_command() == (
            "python -m llm --dry-run --seed 42 --log-session quick --watch --watch-delay 0.5"
        )

    def test_quick_start_menu_hides_delay_when_watch_disabled(self) -> None:
        """关闭观战后，配置菜单不再显示延迟设置。"""
        from ui.interactive.match_setup import QuickStartConfig, QuickStartMenuPage

        config = QuickStartConfig(seed="0", watch=False, delay="0.3")
        choices = QuickStartMenuPage(config)._get_choices()
        values = [choice.value for choice in choices if hasattr(choice, "value")]

        assert "start" in values
        assert "seed" in values
        assert "watch" in values
        assert "delay" not in values

    def test_quick_start_execute_demo_uses_config_summary(self, monkeypatch) -> None:
        """开始演示不再依赖不存在的页面方法。"""
        from ui.interactive.framework import Prompt
        from ui.interactive.match_setup import QuickStartConfig, QuickStartPage

        page = QuickStartPage()
        config = QuickStartConfig(seed="42", watch=True, delay="0.3")

        captured: dict[str, object] = {}

        monkeypatch.setattr(
            "ui.interactive.match_setup.run_match_session_flow",
            lambda session_config: captured.setdefault("session_config", session_config),
        )
        monkeypatch.setattr(Prompt, "press_any_key", lambda message="": None)
        monkeypatch.setattr(QuickStartPage, "_clear_screen", lambda self: None)

        assert page._execute_demo(config) is True
        assert captured["session_config"].label == "demo演示"
