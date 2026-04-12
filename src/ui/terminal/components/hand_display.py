"""手牌显示组件：渲染手牌、副露、牌河的树形布局。

职责：
- 格式化副露列表
- 渲染完整的玩家手牌树
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from rich.console import Group
from rich.text import Text

from kernel.deal.model import TurnPhase
from ui.terminal.components.render import TileRenderer
from ui.terminal.components.tiles import tile_to_rich

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from kernel.hand.melds import Meld
    from ui.terminal.components.name_resolver import NameResolver


class HandDisplay:
    """手牌显示组件。

    主要职责：
    - 格式化副露列表
    - 渲染完整的玩家手牌树
    """

    def __init__(
        self,
        renderer: TileRenderer,
        name_resolver: NameResolver,
    ) -> None:
        """初始化手牌显示组件。

        Args:
            renderer: 牌面渲染器
            name_resolver: 名字解析器
        """
        self._renderer = renderer
        self._name_resolver = name_resolver

    def format_melds(
        self,
        melds: list,
        owner_seat: int,
        dealer_seat: int,
    ) -> str:
        """格式化副露列表（可读格式）。

        Args:
            melds: 副露列表
            owner_seat: 副露持有者座位
            dealer_seat: 亲家座位

        Returns:
            副露描述字符串
        """
        from llm.table_snapshot_text import _meld_segment

        if not melds:
            return "无"
        return " ".join(_meld_segment(m, owner_seat, dealer_seat) for m in melds)

    def format_melds_compact(self, melds: list) -> str:
        """格式化副露列表（紧凑格式）。

        Args:
            melds: 副露列表

        Returns:
            紧凑副露描述字符串
        """
        parts = []
        for m in melds:
            tiles_s = "".join(t.to_code() for t in m.tiles)
            kind_name = {
                "chi": "吃",
                "pon": "碰",
                "daiminkan": "杠",
                "ankan": "暗",
                "shankuminkan": "加",
            }.get(m.kind.value, m.kind.value)
            parts.append(f"{kind_name}[{tiles_s}]")
        return " ".join(parts) if parts else "无"

    def render_player_tree(
        self,
        state: GameState,
        last_actor_seat: int | None = None,
        last_action_str: str = "",
        seat_reasons: dict[int, str] | None = None,
        seat_decision_times: dict[int, float] | None = None,
        show_reason: bool = True,
    ) -> Group:
        """渲染四家手牌树。

        Args:
            state: 游戏状态
            last_actor_seat: 上一步操作者座位
            last_action_str: 上一步动作描述
            seat_reasons: 各席决策理由
            seat_decision_times: 各席决策时间
            show_reason: 是否显示决策理由

        Returns:
            Rich Group 对象
        """
        board = state.board
        table = state.table

        if not board:
            return Group(Text("未开始"))

        dealer = table.dealer_seat
        lines = []

        # 当前动作标题
        lines.append(Text(f"当前动作: {last_action_str}", style="bold bright_yellow"))

        # 计算宝牌集合
        dora_tiles = self._renderer.compute_dora_tiles(board.revealed_indicators)

        for seat in range(4):
            is_active = seat == last_actor_seat
            is_last = seat == 3

            # 手牌（处理 MUST_DISCARD 阶段的摸牌分离）
            hand = board.hands[seat]
            is_must_discard = (
                board.turn_phase == TurnPhase.MUST_DISCARD
                and seat == board.current_seat
                and board.last_draw_tile is not None
            )

            if is_must_discard:
                draw_tile = board.last_draw_tile
                hand_without_draw = Counter(hand)
                if hand_without_draw[draw_tile] > 0:
                    hand_without_draw[draw_tile] -= 1
                    if hand_without_draw[draw_tile] == 0:
                        del hand_without_draw[draw_tile]

                hand_rich = self._renderer.render_hand(hand_without_draw, dora_tiles)
                draw_is_dora = draw_tile in dora_tiles
                draw_rich = tile_to_rich(draw_tile.to_code(), is_dora=draw_is_dora)
                hand_text = Text.assemble(hand_rich, " ", draw_rich)
            else:
                hand_text = self._renderer.render_hand(hand, dora_tiles)

            # 副露
            melds = board.melds[seat]
            melds_str = self.format_melds(melds, seat, dealer)

            # 牌河
            river_str = self._renderer.render_river(board.river, seat, dora_tiles)

            # 立直状态
            is_riichi = board.riichi[seat] if board.riichi else False
            riichi_mark = " [立直]" if is_riichi else ""
            if board.double_riichi and seat in board.double_riichi:
                riichi_mark = " [双立直]"

            # 树形符号
            branch_char = "└──" if is_last else "├──"

            # 玩家行
            player_text = Text.assemble(
                (f"{branch_char} ", "bright_black"),
                self._name_resolver.with_wind(seat, dealer, is_active),
                (riichi_mark, "bold bright_red" if riichi_mark else ""),
                "  ",
                hand_text,
            )
            lines.append(player_text)

            # 副露行
            meld_prefix = "│   ├── " if not is_last else "    ├── "
            meld_content = melds_str if melds_str and melds_str != "无" else "（无）"
            meld_text = Text.assemble(
                (meld_prefix, "bright_black"),
                ("副露: ", "dim"),
                (meld_content, "bright_magenta" if melds else "dim"),
            )
            lines.append(meld_text)

            # 牌河行
            river_prefix = "│   ├── " if not is_last else "    ├── "
            river_line = Text.assemble(
                (river_prefix, "bright_black"),
                ("牌河: ", "dim"),
            )
            if river_str.plain:
                river_line.append(river_str)
            else:
                river_line.append(Text("（无）", style="dim"))
            lines.append(river_line)

            # 决策理由行
            seat_reason = seat_reasons.get(seat) if seat_reasons else None
            seat_time = seat_decision_times.get(seat, 0) if seat_decision_times else 0

            if seat_reason and show_reason:
                self._render_reason_lines(lines, seat_reason, seat_time, seat, last_actor_seat, is_last)

            # 空行分隔（仅一个）
            if not is_last:
                lines.append(Text("│", style="bright_black"))

        return Group(*lines)

    def _render_reason_lines(
        self,
        lines: list,
        reason: str,
        decision_time: float,
        seat: int,
        last_actor_seat: int | None,
        is_last: bool,
    ) -> None:
        """渲染决策理由行。"""
        reason_prefix = "│   └── " if not is_last else "    └── "
        time_str = f"({decision_time:.1f}s) " if decision_time > 0 else ""
        reason_label = "决策理由"

        prefix_len = len(reason_prefix) + len(reason_label) + len(time_str) + 2
        max_reason_width = 70 - prefix_len

        # 截断并分行
        if len(reason) > max_reason_width:
            reason_lines = [reason[i:i+max_reason_width] for i in range(0, len(reason), max_reason_width)]
        else:
            reason_lines = [reason]

        for idx, reason_line in enumerate(reason_lines):
            if idx == 0:
                reason_text = Text.assemble(
                    (reason_prefix, "bright_black"),
                    (reason_label, "dim cyan"),
                    (time_str, "dim"),
                    (": ", "dim cyan"),
                    (reason_line, "italic bright_cyan" if seat == last_actor_seat else "italic cyan"),
                )
            else:
                cont_prefix = "│       " if not is_last else "        "
                reason_text = Text.assemble(
                    (cont_prefix, "bright_black"),
                    (reason_line, "italic bright_cyan" if seat == last_actor_seat else "italic cyan"),
                )
            lines.append(reason_text)