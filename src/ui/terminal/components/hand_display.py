"""手牌显示组件：负责响应式渲染四家手牌主视图。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Literal

from rich.cells import cell_len, set_cell_size
from rich.console import Group
from rich.text import Text

from kernel.deal.model import TurnPhase
from ui.terminal.components.meld_display import MeldDisplay
from ui.terminal.components.render import TileRenderer
from ui.terminal.components.tiles import tile_to_rich

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from ui.terminal.components.name_resolver import NameResolver
    from ui.terminal.components.stats_tracker import StatsSnapshot


RenderMode = Literal["full", "normal", "compact"]


class HandDisplay:
    """响应式渲染 live 观战中的四家手牌。"""

    def __init__(
        self,
        renderer: TileRenderer,
        name_resolver: NameResolver,
    ) -> None:
        self._renderer = renderer
        self._name_resolver = name_resolver
        self._meld_display = MeldDisplay(name_resolver)

    def format_melds(
        self,
        melds: list,
        owner_seat: int,
    ) -> str:
        """格式化完整副露描述。"""
        return self._meld_display.format_melds(
            melds,
            owner_seat,
            include_source=True,
        )

    def format_melds_compact(self, melds: list) -> str:
        """格式化紧凑副露描述。"""
        return self._meld_display.format_melds(
            melds,
            owner_seat=0,
            include_source=False,
        )

    def render_player_tree(
        self,
        state: GameState,
        last_actor_seat: int | None = None,
        last_action_str: str = "",
        seat_reasons: dict[int, str] | None = None,
        show_reason: bool = True,
        mode: RenderMode = "full",
        seat_contexts: dict[int, Text] | None = None,
        stats_snapshot: "StatsSnapshot | None" = None,
    ) -> Group:
        """按档位渲染四家手牌。"""
        board = state.board
        table = state.table
        if not board:
            return Group(Text("未开始", style="dim"))

        dealer = table.dealer_seat
        dora_tiles = self._renderer.compute_dora_tiles(board.revealed_indicators)
        hand_labels = {
            seat: self._format_hand_label(
                seat,
                dealer,
                table.scores[seat],
                stats_snapshot,
            )
            for seat in range(4)
        }
        label_width = self._compute_label_width(hand_labels.values())

        lines: list[Text] = []
        if last_action_str:
            lines.append(Text(f"当前动作: {last_action_str}", style="bold bright_yellow"))
            lines.append(Text(""))

        for seat in range(4):
            is_active = seat == last_actor_seat
            hand_text = self._render_hand_text(board, seat, dora_tiles)
            label_text = self._render_hand_label(hand_labels[seat], label_width, is_active)
            riichi_mark = self._build_riichi_mark(board, seat)

            lines.extend(
                self._render_multiline_block(
                    board,
                    seat,
                    label_text,
                    hand_text,
                    riichi_mark,
                    dora_tiles,
                    mode,
                    is_active=is_active,
                    reason=seat_reasons.get(seat) if seat_reasons else None,
                    show_reason=show_reason,
                    context_text=seat_contexts.get(seat) if seat_contexts else None,
                )
            )

            if seat != 3:
                lines.append(Text("│", style="bright_black"))

        while lines and not lines[-1].plain:
            lines.pop()
        return Group(*lines)

    def _render_multiline_block(
        self,
        board,
        seat: int,
        label_text: Text,
        hand_text: Text,
        riichi_mark: str,
        dora_tiles: set,
        mode: RenderMode,
        is_active: bool,
        reason: str | None,
        show_reason: bool,
        context_text: Text | None,
    ) -> list[Text]:
        is_last = seat == 3
        branch_prefix = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "

        melds = board.melds[seat]
        melds_text = (
            self.format_melds(melds, seat)
            if mode == "full"
            else self.format_melds_compact(melds)
        )
        river_limit = 10 if mode == "full" else 6 if mode == "normal" else 4
        river_text = self._render_river_tail(board.river, seat, dora_tiles, limit=river_limit)

        lines: list[Text] = [
            Text.assemble(
                (branch_prefix, "bright_black"),
                label_text,
                (" ", ""),
                hand_text,
                (riichi_mark, "bold bright_red" if riichi_mark else ""),
            )
        ]

        children: list[tuple[str, Text]] = [
            (
                "副露: ",
                Text(
                    melds_text if melds_text else "无",
                    style="bright_magenta" if melds else "dim",
                ),
            ),
            ("牌河: ", river_text if river_text.plain else Text("无", style="dim")),
        ]
        if show_reason and mode == "full" and reason:
            reason_style = "italic bright_cyan" if is_active else "italic cyan"
            children.append(("理由: ", Text(self._clip_reason(reason), style=reason_style)))
        if context_text is not None:
            children.append(("上下文: ", context_text))

        for idx, (label, content) in enumerate(children):
            lines.append(
                self._render_child_line(
                    child_prefix,
                    is_last_child=idx == len(children) - 1,
                    label=label,
                    content=content,
                )
            )
        return lines

    def _render_child_line(
        self,
        child_prefix: str,
        *,
        is_last_child: bool,
        label: str,
        content: Text,
    ) -> Text:
        branch = "└── " if is_last_child else "├── "
        return Text.assemble(
            (f"{child_prefix}{branch}", "bright_black"),
            (label, "dim cyan" if label == "理由: " else "dim"),
            content,
        )

    def _render_hand_text(self, board, seat: int, dora_tiles: set) -> Text:
        hand = board.hands[seat]
        is_must_discard = (
            board.turn_phase == TurnPhase.MUST_DISCARD
            and seat == board.current_seat
            and board.last_draw_tile is not None
        )

        if not is_must_discard:
            return self._renderer.render_hand(hand, dora_tiles)

        draw_tile = board.last_draw_tile
        hand_without_draw = Counter(hand)
        if hand_without_draw[draw_tile] > 0:
            hand_without_draw[draw_tile] -= 1
            if hand_without_draw[draw_tile] == 0:
                del hand_without_draw[draw_tile]

        hand_rich = self._renderer.render_hand(hand_without_draw, dora_tiles)
        draw_is_dora = draw_tile in dora_tiles
        draw_rich = tile_to_rich(draw_tile.to_code(), is_dora=draw_is_dora)
        return Text.assemble(hand_rich, " ", draw_rich)

    def _render_river_tail(self, river: tuple, seat: int, dora_tiles: set, limit: int) -> Text:
        recent = tuple(entry for entry in river if entry.seat == seat)[-limit:]
        return self._renderer.render_river(recent, seat, dora_tiles)

    def _build_riichi_mark(self, board, seat: int) -> str:
        if board.double_riichi and seat in board.double_riichi:
            return " [双立直]"
        if board.riichi and board.riichi[seat]:
            return " [立直]"
        return ""

    def _compute_label_width(self, labels: Iterable[str]) -> int:
        return max((cell_len(label) for label in labels), default=0)

    def _render_hand_label(self, label: str, width: int, is_active: bool) -> Text:
        padded = set_cell_size(label, width)
        style = "bold bright_cyan" if is_active else "bright_white"
        return Text(padded, style=style)

    def _format_hand_label(
        self,
        seat: int,
        dealer: int,
        score: int,
        stats_snapshot: "StatsSnapshot | None",
    ) -> str:
        base_label = self._name_resolver.format_hand_label(seat, dealer).rstrip("：")
        wins = stats_snapshot.win_count(seat) if stats_snapshot is not None else 0
        win_rate = stats_snapshot.win_rate(seat) if stats_snapshot is not None else 0.0
        return f"{base_label} {score:,} · 和{wins}({round(win_rate * 100):d}%)："

    def _clip_reason(self, reason: str) -> str:
        return reason if len(reason) <= 72 else f"{reason[:69]}..."
