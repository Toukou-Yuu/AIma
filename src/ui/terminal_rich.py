"""Rich 终端实时观战：纯文本动态渲染，无需图片资源。

用法::

    from ui.terminal_rich import LiveMatchViewer
    from llm.runner import run_llm_match

    viewer = LiveMatchViewer(delay=0.5)
    viewer.run(run_llm_match(...))

或命令行::

    python -m llm --dry-run --seed 0 --watch

依赖: ``pip install rich``
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Iterator

from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    GameEvent,
    HandOverEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
)
from kernel.deal.model import TurnPhase
from kernel.flow.model import FlowKind
from kernel.hand.melds import MeldKind
from kernel.table.model import PrevailingWind
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from llm.runner import RunResult


# 炫彩虹宝牌颜色循环
_DORA_RAINBOW = [
    "red",      # 红
    "yellow",   # 黄
    "green",    # 绿
    "cyan",     # 青
    "blue",     # 蓝
    "magenta",  # 紫
]
_SUIT_COLORS = {
    "m": "bright_white",  # 万子
    "p": "bright_green",  # 筒子
    "s": "bright_blue",   # 索子
    "z": "bright_yellow", # 字牌
}

_WIND_NAMES = ["东", "南", "西", "北"]


def _tile_to_rich(tile_code: str, is_dora: bool = False) -> Text:
    """将牌码（如'1m'、'5sr'、'7z'）渲染为带颜色的 Text。

    Args:
        tile_code: 牌码
        is_dora: 是否为宝牌（使用炫彩高亮）
    """
    if not tile_code:
        return Text("")

    suit = tile_code[0] if tile_code[0] in "mpsz" else tile_code[-1]
    color = _SUIT_COLORS.get(suit, "white")

    # 赤宝牌标红
    if "r" in tile_code:
        color = "bright_red"

    # 宝牌使用金色高亮
    if is_dora:
        style = "bold bright_yellow"
    else:
        style = color

    # 字牌用汉字
    if suit == "z":
        honor_map = {"1": "東", "2": "南", "3": "西", "4": "北", "5": "白", "6": "發", "7": "中"}
        display = honor_map.get(tile_code[0], tile_code[0])
        return Text(display, style=style)

    return Text(tile_code.replace("r", ""), style=style)


def _parse_hand_tiles(hand_str: str) -> list[Text]:
    """解析手牌字符串（如'1m2m3m4p5p'）为 Text 列表。"""
    tiles = []
    i = 0
    while i < len(hand_str):
        # 跳过空格
        if hand_str[i] == " ":
            i += 1
            continue
        # 尝试读取牌（可能是 '5sr' 或 '1m' 或 '7z'）
        if i + 1 < len(hand_str) and hand_str[i + 1] in "mpsz":
            # 检查是否是赤宝牌 (e.g., '5sr')
            if i + 2 < len(hand_str) and hand_str[i + 2] == "r":
                tiles.append(_tile_to_rich(hand_str[i : i + 3]))
                i += 3
            else:
                tiles.append(_tile_to_rich(hand_str[i : i + 2]))
                i += 2
        else:
            i += 1
    return tiles


def _wind_with_seat(wind_idx: int, seat: int, is_active: bool = False) -> Text:
    """生成带样式的风位+座位标签，如'东(S0)'。

    Args:
        wind_idx: 相对风位索引 (0=东, 1=南, 2=西, 3=北)
        seat: 绝对座位号 (0-3)
        is_active: 是否为当前操作席（高亮显示）
    """
    wind = _WIND_NAMES[wind_idx]
    style = "bold bright_cyan" if is_active else "bright_white"
    return Text.assemble(
        (wind, style),
        (f"(S{seat})", "dim")
    )


class LiveMatchViewer:
    """Rich 实时观战器。"""

    def __init__(self, delay: float = 0.5, show_reason: bool = True, max_player_steps: int = 500):
        """
        初始化观战器。

        Args:
            delay: 每步之间的延迟（秒）
            show_reason: 是否显示模型的决策理由
            max_player_steps: 最大玩家决策步数（用于显示步数进度）
        """
        self.delay = delay
        self.show_reason = show_reason
        self.max_player_steps = max_player_steps
        self.console = Console()
        self._wins = [0, 0, 0, 0]
        self._rounds = 0
        self._last_action_str: str = ""
        self._last_reason: str = ""
        self._step = 0
        self._last_actor_seat: int | None = None

    def _hand_to_rich(self, hand_str: str) -> Text:
        """将手牌字符串转为带空格分隔的 Rich Text，宝牌用 [] 包裹并高亮。"""
        if not hand_str:
            return Text("（空）", style="dim")

        result = Text()
        i = 0
        first = True

        while i < len(hand_str):
            # 跳过空格
            if hand_str[i] == " ":
                i += 1
                continue

            # 检查是否是宝牌标记 [牌码]
            if hand_str[i] == "[":
                # 找到匹配的 ]
                end = hand_str.find("]", i + 1)
                if end != -1:
                    # 提取方括号内的内容
                    tile_code = hand_str[i + 1:end]
                    # 添加分隔符
                    if not first:
                        result.append(" ")
                    first = False
                    # 宝牌使用金色高亮
                    tile_text = _tile_to_rich(tile_code, is_dora=True)
                    result.append(tile_text)
                    i = end + 1
                    continue

            # 读取普通牌
            if i + 1 < len(hand_str) and hand_str[i + 1] in "mpsz":
                if i + 2 < len(hand_str) and hand_str[i + 2] == "r":
                    tile_code = hand_str[i:i + 3]
                    i += 3
                else:
                    tile_code = hand_str[i:i + 2]
                    i += 2

                if not first:
                    result.append(" ")
                first = False
                result.append(_tile_to_rich(tile_code))
            else:
                i += 1

        return result if result.plain else Text("（空）", style="dim")

    def _render_header(self, state: GameState) -> Table:
        """渲染顶部场况信息表。"""
        table = state.table
        board = state.board

        # 风向和局数
        wind = "東" if table.prevailing_wind == PrevailingWind.EAST else "南"
        round_num = table.round_number.value

        header = Table(show_header=False, box=None, padding=(0, 2))
        header.add_column("key", style="dim")
        header.add_column("value")

        header.add_row("步数", f"{self._step}/{self.max_player_steps}")
        header.add_row("局", f"{wind}風{round_num}局")
        header.add_row("本场", str(table.honba))
        header.add_row("供托", str(table.kyoutaku))

        if board:
            remaining = len(board.live_wall) - board.live_draw_index
            header.add_row("余牌", str(remaining))

            # 宝牌指示器
            if board.revealed_indicators:
                dora_text = Text.assemble(
                    *(self._dora_indicators_to_rich(board.revealed_indicators))
                )
                header.add_row("宝牌", dora_text)

        # 点数
        scores = Table(show_header=False, box=None, padding=(0, 1))
        scores.add_column(style="dim")
        scores.add_column(justify="right")
        for i, s in enumerate(table.scores):
            wind_name = _WIND_NAMES[i]
            # 高亮上一步执行动作的玩家点数
            is_active = (i == self._last_actor_seat)
            style = "bold bright_cyan" if is_active else ""
            scores.add_row(f"{wind_name}:", Text(str(s), style=style))

        # 合并
        main = Table(show_header=False, box=None)
        main.add_column()
        main.add_column()
        main.add_row(header, scores)

        return main

    def _render_player_tree(self, state: GameState) -> Group:
        """渲染四家手牌（使用 Group 实现更灵活的间距控制）。"""
        from rich.columns import Columns

        board = state.board
        table = state.table

        if not board:
            return Group(Text("未开始"))

        dealer = table.dealer_seat
        lines = []

        # 当前动作标题（无缩进）
        lines.append(Text(f"当前动作: {self._last_action_str}", style="bold bright_yellow"))

        for seat in range(4):
            # 计算相对风位
            rel_wind = (seat - dealer) % 4
            # 高亮上一步执行动作的玩家
            is_active = (seat == self._last_actor_seat)

            # 手牌
            hand = board.hands[seat]
            # 在 MUST_DISCARD 阶段，当前玩家把摸牌单独显示
            is_must_discard = (
                board.turn_phase == TurnPhase.MUST_DISCARD
                and seat == board.current_seat
                and board.last_draw_tile is not None
            )
            if is_must_discard:
                # 从手牌中分离出摸牌
                from collections import Counter
                draw_tile = board.last_draw_tile
                hand_without_draw = Counter(hand)
                if hand_without_draw[draw_tile] > 0:
                    hand_without_draw[draw_tile] -= 1
                    if hand_without_draw[draw_tile] == 0:
                        del hand_without_draw[draw_tile]
                hand_str = self._hand_to_str_with_dora(hand_without_draw, board.revealed_indicators)
                draw_str = draw_tile.to_code()
                # 检查摸牌是否是宝牌
                from kernel.scoring.dora import dora_from_indicators
                dora_tiles = set(dora_from_indicators(board.revealed_indicators)) if board.revealed_indicators else set()
                is_draw_dora = draw_tile in dora_tiles
                if is_draw_dora:
                    draw_str = f"[{draw_str}]"
                hand_str = f"{hand_str} [{draw_str}]"
            else:
                hand_str = self._hand_to_str_with_dora(hand, board.revealed_indicators)

            # 副露
            melds = board.melds[seat]
            melds_str = self._melds_to_str(melds, seat, dealer)

            # 牌河
            river_str = self._river_to_str(board.river, seat)

            # 立直状态
            is_riichi = board.riichi[seat] if board.riichi else False
            riichi_mark = " [立直]" if is_riichi else ""
            if board.double_riichi and seat in board.double_riichi:
                riichi_mark = " [双立直]"

            # 判断是否是最后一家（用于树形符号）
            is_last = (seat == 3)
            branch_char = "└──" if is_last else "├──"

            # 玩家行
            player_text = Text.assemble(
                (f"{branch_char} ", "bright_black"),
                _wind_with_seat(rel_wind, seat, is_active),
                (riichi_mark, "bold bright_red" if riichi_mark else ""),
                "  ",
                self._hand_to_rich(hand_str),
            )
            lines.append(player_text)

            # 副露行
            if melds:
                meld_text = Text.assemble(
                    ("│   ├── " if not is_last else "    ├── ", "bright_black"),
                    (f"副露: {melds_str}", "bright_magenta"),
                )
                lines.append(meld_text)

            # 牌河行
            river_text_obj = self._river_to_str(board.river, seat)
            if river_text_obj.plain.strip():  # 检查内容是否非空
                river_line = Text.assemble(
                    ("│   └── " if not is_last else "    └── ", "bright_black"),
                    ("牌河: ", "dim"),
                )
                river_line.append(river_text_obj)
                lines.append(river_line)
            else:
                # 如果没有牌河，也显示一个空行保持结构
                lines.append(Text("│" + " " * 79 if not is_last else " " * 80, style="bright_black"))

            # 空行分隔（除了最后一家）- 两行间距
            if not is_last:
                lines.append(Text("│", style="bright_black"))
                lines.append(Text("│", style="bright_black"))

        return Group(*lines)

    def _melds_to_str_compact(self, melds, owner_seat: int, dealer_seat: int) -> str:
        """副露列表 -> 紧凑字符串（每副露只显示牌型，省略鸣牌来源）。"""
        parts = []
        for m in melds:
            tiles_s = "".join(t.to_code() for t in m.tiles)
            if m.kind.value == "chi":
                parts.append(f"吃[{tiles_s}]")
            elif m.kind.value == "pon":
                parts.append(f"碰[{tiles_s}]")
            elif m.kind.value == "daiminkan":
                parts.append(f"杠[{tiles_s}]")
            elif m.kind.value == "ankan":
                parts.append(f"暗[{tiles_s}]")
            elif m.kind.value == "shankuminkan":
                parts.append(f"加[{tiles_s}]")
        return " ".join(parts) if parts else "无"

    def _hand_to_str_with_dora(self, hand, revealed_indicators: tuple) -> str:
        """手牌 -> 字符串，宝牌用 [] 包裹高亮。"""
        from kernel.scoring.dora import dora_from_indicators

        dora_tiles = set()
        if revealed_indicators:
            dora_tiles = set(dora_from_indicators(revealed_indicators))

        # 获取排序后的手牌列表
        from llm.table_snapshot_text import _counter_sorted_str
        hand_str = _counter_sorted_str(hand)

        # 如果手牌为空
        if not hand_str:
            return ""

        # 解析手牌并标记宝牌
        parts = []
        i = 0
        while i < len(hand_str):
            # 跳过空格
            if hand_str[i] == " ":
                i += 1
                continue
            # 读取牌（可能是 '5sr' 或 '1m' 或 '7z'）
            if i + 1 < len(hand_str) and hand_str[i + 1] in "mpsz":
                if i + 2 < len(hand_str) and hand_str[i + 2] == "r":
                    tile_code = hand_str[i:i + 3]
                    i += 3
                else:
                    tile_code = hand_str[i:i + 2]
                    i += 2

                # 检查是否是宝牌
                from kernel.replay_json import tile_from_code
                try:
                    tile = tile_from_code(tile_code)
                    is_dora = tile in dora_tiles
                    # 赤五也算宝牌（当宝牌是5时）
                    if not is_dora and tile.is_red:
                        for d in dora_tiles:
                            if d.suit == tile.suit and d.rank == 5:
                                is_dora = True
                                break

                    if is_dora:
                        parts.append(f"[{tile_code}]")
                    else:
                        parts.append(tile_code)
                except:
                    parts.append(tile_code)
            else:
                i += 1

        return " ".join(parts)

    def _dora_indicators_to_rich(self, indicators: tuple) -> list:
        """宝牌指示器列表 -> Rich Text 列表（炫彩效果）。"""
        result = []
        for i, tile in enumerate(indicators):
            if i > 0:
                result.append((" ", ""))
            # 宝牌指示器使用炫彩虹色（每个指示器不同颜色）
            color = _DORA_RAINBOW[i % len(_DORA_RAINBOW)]
            # 直接创建带炫彩样式的 Text，不经过 _tile_to_rich
            tile_code = tile.to_code()
            suit = tile_code[0] if tile_code[0] in "mpsz" else tile_code[-1]

            # 字牌用汉字
            if suit == "z":
                honor_map = {"1": "東", "2": "南", "3": "西", "4": "北", "5": "白", "6": "發", "7": "中"}
                display = honor_map.get(tile_code[0], tile_code[0])
                # 使用反转色确保可见
                tile_text = Text(display, style=f"bold {color} reverse")
            else:
                tile_text = Text(tile_code.replace("r", ""), style=f"bold {color} reverse")

            result.append(tile_text)
        return result

    def _melds_to_str(self, melds, owner_seat: int, dealer_seat: int) -> str:
        """副露列表 -> 可读字符串。"""
        from llm.table_snapshot_text import _meld_segment
        if not melds:
            return "无"
        return " ".join(_meld_segment(m, owner_seat, dealer_seat) for m in melds)

    def _river_to_str(self, river, seat: int) -> Text:
        """牌河 -> 可读字符串（带颜色）。"""
        from rich.text import Text

        result = Text()
        first = True
        for e in river:
            if e.seat != seat:
                continue
            if not first:
                result.append(" ")
            first = False

            tile_code = e.tile.to_code()
            tile_text = _tile_to_rich(tile_code)

            if e.riichi:
                result.append("[", style="dim")
                result.append(tile_text)
                result.append("]", style="dim")
            elif e.tsumogiri:
                result.append("<", style="dim")
                result.append(tile_text)
                result.append(">", style="dim")
            else:
                result.append(tile_text)
        return result

    def _render_stats(self) -> Text:
        """渲染统计信息面板（返回 Text）。"""
        lines = []
        for i in range(4):
            seat_label = f"S{i}"
            wins = self._wins[i]
            rate = f"{wins}/{self._rounds}" if self._rounds > 0 else "—"
            pct = f"({wins/max(self._rounds,1)*100:.0f}%)" if self._rounds > 0 else "(—)"
            lines.append(f"{seat_label}    {wins}    {rate} {pct}")
        return Text("\n".join(lines))

    def _render_recent_events(self, events: tuple[GameEvent, ...]) -> Group:
        """渲染最近事件面板（返回 Group，不包 Panel）。"""
        lines = []
        for ev in events[-2:]:  # 只显示最近2条
            line = self._format_event(ev)
            if line:
                lines.append(line)

        if not lines:
            return Group(Text("无", style="dim"))

        return Group(*lines)

    def _format_event(self, ev: GameEvent) -> Text | None:
        """单个事件 -> Rich Text。"""
        if isinstance(ev, RoundBeginEvent):
            return Text.assemble(
                ("配牌 ", "dim"),
                ("宝牌: ", "dim"),
                _tile_to_rich(ev.dora_indicator.to_code(), is_dora=True),
            )

        if isinstance(ev, DrawTileEvent):
            src = "岭上" if ev.is_rinshan else "本墙"
            return Text.assemble(
                (_WIND_NAMES[ev.seat], "cyan"),
                (f" 从{src}摸 ", "dim"),
                _tile_to_rich(ev.tile.to_code()),
            )

        if isinstance(ev, DiscardTileEvent):
            riichi = " 立直" if ev.declare_riichi else ""
            tg = "摸切" if ev.is_tsumogiri else "手切"
            return Text.assemble(
                (_WIND_NAMES[ev.seat], "cyan"),
                (f" 打 ", "dim"),
                _tile_to_rich(ev.tile.to_code()),
                (f" ({tg}{riichi})", "dim"),
            )

        if isinstance(ev, CallEvent):
            cn = {"chi": "吃", "pon": "碰", "daiminkan": "大明杠",
                  "ankan": "暗杠", "shankuminkan": "加杠"}.get(ev.call_kind, ev.call_kind)
            return Text.assemble(
                (_WIND_NAMES[ev.seat], "bright_magenta"),
                (f" {cn}", "bright_magenta"),
            )

        if isinstance(ev, RonEvent):
            return Text.assemble(
                (_WIND_NAMES[ev.seat], "bold bright_red"),
                (" 荣和 ", "bold bright_red"),
                _tile_to_rich(ev.win_tile.to_code()),
                (f" ← {_WIND_NAMES[ev.discard_seat]}", "dim"),
            )

        if isinstance(ev, TsumoEvent):
            rs = "岭上" if ev.is_rinshan else ""
            return Text.assemble(
                (_WIND_NAMES[ev.seat], "bold bright_red"),
                (f" 自摸和了 {rs}", "bold bright_red"),
                _tile_to_rich(ev.win_tile.to_code()),
            )

        if isinstance(ev, HandOverEvent):
            if ev.winners:
                winners = "、".join(_WIND_NAMES[w] for w in ev.winners)
                return Text.assemble(
                    ("局终: ", "bold yellow"),
                    (f"{winners} 和了", "bright_yellow"),
                )
            return Text("局终: 流局", style="dim")

        if isinstance(ev, FlowEvent):
            names = {
                FlowKind.EXHAUSTED: "荒牌",
                FlowKind.NINE_NINE: "九种九牌",
                FlowKind.FOUR_WINDS: "四风连打",
                FlowKind.FOUR_KANS: "四杠散",
                FlowKind.FOUR_RIICHI: "四家立直",
                FlowKind.THREE_RON: "三家和",
            }
            return Text.assemble(
                ("流局: ", "dim"),
                (names.get(ev.flow_kind, ev.flow_kind.value), "yellow"),
            )

        return None

    def _update_stats(self, events: tuple[GameEvent, ...]) -> None:
        """更新和了统计。"""
        for ev in events:
            if isinstance(ev, HandOverEvent):
                self._rounds += 1
                if ev.winners:
                    for w in ev.winners:
                        self._wins[w] += 1

    def _build_layout(self, state: GameState, events: tuple[GameEvent, ...]) -> Panel:
        """构建完整布局（固定尺寸）。"""
        from rich.columns import Columns

        # 场况（左侧）
        header = self._render_header(state)
        header_panel = Panel(header, title="场况", border_style="bright_cyan", padding=(0, 1), width=45)

        # 和了统计（右侧）
        stats = self._render_stats()
        stats_panel = Panel(stats, title="和了统计", border_style="bright_blue", padding=(0, 1), width=25)

        # 顶部并排：场况 + 统计
        top_row = Columns([header_panel, stats_panel], equal=False, expand=False)

        # 手牌树（中间，足够高度）
        player_tree = self._render_player_tree(state)
        hand_panel = Panel(
            player_tree,
            title="手牌",
            border_style="green",
            height=26,  # 增加高度
            padding=(0, 2),  # 增加水平边距
        )

        # 事件（底部）
        recent = self._render_recent_events(events)
        event_panel = Panel(recent, title="事件", border_style="yellow", height=4, padding=(0, 1))

        # 主布局：顶部并排 + 手牌 + 事件
        main_content = Group(top_row, hand_panel, event_panel)

        return Panel(main_content, border_style="bright_blue")

    def step(self, state: GameState, events: tuple[GameEvent, ...], action_str: str = "", reason: str = ""):
        """
        单步渲染（供外部调用）。

        Returns:
            Panel 对象（可用于 Live 更新）
        """
        self._step += 1
        self._last_action_str = action_str
        self._last_reason = reason
        # 解析 action_str 获取上一步的行动者（格式: "家{seat} {action}"）
        self._last_actor_seat = None
        if action_str.startswith("家"):
            try:
                self._last_actor_seat = int(action_str[1])
            except (ValueError, IndexError):
                pass
        self._update_stats(events)
        return self._build_layout(state, events)

    def run_from_replay(self, actions: list, states: list, events_list: list, action_strs: list, reasons: list | None = None):
        """从回放数据运行动态观战。"""
        reasons = reasons or []
        with Live(console=self.console, refresh_per_second=4) as live:
            for i, (state, events, action_str) in enumerate(zip(states, events_list, action_strs)):
                reason = reasons[i] if i < len(reasons) else ""
                panel = self.step(state, events, action_str, reason)
                live.update(panel)
                time.sleep(self.delay)

    def run(self, result: RunResult):
        """
        从 RunResult 运行回放观战。

        注意：RunResult 只包含最终状态和 action wire，不包含中间状态。
        要完整观战，需要在 runner 中集成实时回调。
        """
        self.console.print("[dim]提示: RunResult 不包含中间状态，请使用 run_with_callback 或从 replay 运行[/]")
        self.console.print(f"终局: {result.final_state.phase.value}")

    def run_from_replay_file(self, replay_path: str | Path, delay: float | None = None):
        """
        从牌谱 JSON 文件运行动态回放。

        Args:
            replay_path: 牌谱文件路径
            delay: 覆盖默认的 delay
        """
        import json
        from pathlib import Path

        from kernel.replay import replay_from_actions
        from kernel.replay_json import actions_from_match_log

        path = Path(replay_path)
        if not path.exists():
            self.console.print(f"[red]牌谱文件不存在: {replay_path}[/]")
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            actions = actions_from_match_log(data)
        except (ValueError, KeyError, TypeError) as e:
            self.console.print(f"[red]牌谱解析失败: {e}[/]")
            return

        # 回放并实时渲染
        from kernel.replay import ReplayError

        try:
            with Live(console=self.console, refresh_per_second=4) as live:
                # 显示初始状态
                from kernel.engine.state import initial_game_state
                state = initial_game_state()
                live.update(self.step(state, (), "开始回放"))
                time.sleep(self.delay if delay is None else delay)

                # 逐步回放
                for i, action in enumerate(actions):
                    from kernel import apply

                    try:
                        outcome = apply(state, action)
                        state = outcome.new_state
                        self._update_stats(outcome.events)

                        action_str = f"Step {i+1}: {action.kind.value}"
                        live.update(self.step(state, outcome.events, action_str))
                        time.sleep(self.delay if delay is None else delay)
                    except Exception as e:
                        self.console.print(f"[red]回放错误 at step {i}: {e}[/]")
                        break

                # 显示终局
                live.update(self.step(state, (), f"回放完成: {state.phase.value}"))

        except ReplayError as e:
            self.console.print(f"[red]回放失败: {e}[/]")


class LiveMatchCallback:
    """用于集成到 runner 的实时回调类。"""

    def __init__(self, delay: float = 0.5, show_reason: bool = True, max_player_steps: int = 500):
        self.viewer = LiveMatchViewer(delay=delay, show_reason=show_reason, max_player_steps=max_player_steps)
        self.live: Live | None = None
        self._start_sequence: int = 0

    def __enter__(self):
        self.live = Live(console=self.viewer.console, refresh_per_second=4)
        self.live.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.live:
            self.live.__exit__(exc_type, exc_val, exc_tb)

    def on_step(self, state: GameState, events: tuple[GameEvent, ...], action_str: str = "", reason: str = ""):
        """每步调用。"""
        panel = self.viewer.step(state, events, action_str, reason)
        if self.live:
            self.live.update(panel)
        time.sleep(self.viewer.delay)


def demo_dry_run(seed: int = 0, steps: int = 100, delay: float = 0.3):
    """演示：dry-run 模式实时观战。"""
    import random

    from kernel import apply, shuffle_deck
    from kernel.engine.actions import Action, ActionKind
    from kernel.engine.state import initial_game_state
    from kernel.play.model import TurnPhase
    from kernel.tiles.deck import build_deck
    from llm.turns import pending_actor_seats

    viewer = LiveMatchViewer(delay=delay, show_reason=False)

    with Live(console=viewer.console, refresh_per_second=4) as live:
        # 初始状态
        state = initial_game_state()

        # BEGIN_ROUND
        deck = tuple(shuffle_deck(build_deck(), seed=seed))
        action = Action(ActionKind.BEGIN_ROUND, wall=deck)
        outcome = apply(state, action)
        state = outcome.new_state

        viewer._update_stats(outcome.events)
        live.update(viewer.step(state, outcome.events, "开局配牌"))
        time.sleep(delay)

        # 模拟摸打循环
        while viewer._step < steps:
            if state.phase.value != "in_round":
                break

            board = state.board
            if not board:
                break

            # 获取当前需要行动的座位列表
            pending = pending_actor_seats(state)
            if not pending:
                break

            seat = pending[0]  # 取第一个需要行动的座位
            turn_phase = board.turn_phase

            if turn_phase == TurnPhase.NEED_DRAW:
                if not board.live_wall:
                    break  # 荒牌
                action = Action(ActionKind.DRAW, seat=seat)
                action_str = f"家{seat} 摸牌"

            elif turn_phase == TurnPhase.MUST_DISCARD:
                # 随机弃牌
                hand = board.hands[seat]
                if not hand:
                    break
                tile = random.choice(list(hand.elements()))
                action = Action(ActionKind.DISCARD, seat=seat, tile=tile)
                action_str = f"家{seat} 打 {tile.to_code()}"

            elif turn_phase == TurnPhase.CALL_RESPONSE:
                # 检查是否有鸣牌/荣和机会
                from kernel.api.legal_actions import legal_actions
                legals = legal_actions(state, seat)
                # 如果只有 PASS_CALL 一个选项，不渲染（直接执行）
                has_real_choice = any(la.kind.name != "PASS_CALL" for la in legals)
                action = Action(ActionKind.PASS_CALL, seat=seat)
                if has_real_choice:
                    action_str = f"家{seat} 过牌"
                else:
                    # 无意义过牌，执行但不渲染
                    outcome = apply(state, action)
                    state = outcome.new_state
                    continue
            else:
                break

            try:
                outcome = apply(state, action)
                state = outcome.new_state
                viewer._update_stats(outcome.events)
                live.update(viewer.step(state, outcome.events, action_str))
                time.sleep(delay)
            except Exception as e:
                viewer.console.print(f"[red]错误: {e}[/]")
                break

    viewer.console.print(f"\n[bold green]演示结束[/] 步数: {viewer._step}, 终局状态: {state.phase.value}")


if __name__ == "__main__":
    demo_dry_run(seed=42, steps=30, delay=0.2)
