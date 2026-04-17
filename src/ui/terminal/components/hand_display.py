"""手牌显示组件：负责响应式渲染四家手牌主视图。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Literal

from rich.cells import cell_len, set_cell_size
from rich.console import Group
from rich.text import Text

from kernel.deal.model import TurnPhase
from ui.terminal.components.render import TileRenderer
from ui.terminal.components.tiles import tile_to_rich

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from ui.terminal.components.name_resolver import NameResolver


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

    def format_melds(
        self,
        melds: list,
        owner_seat: int,
        dealer_seat: int,
    ) -> str:
        """格式化完整副露描述。"""
        from llm.table_snapshot_text import _meld_segment

        if not melds:
            return "无"
        return " ".join(_meld_segment(m, owner_seat, dealer_seat) for m in melds)

    def format_melds_compact(self, melds: list) -> str:
        """格式化紧凑副露描述。"""
        if not melds:
            return "无"
        parts = []
        for meld in melds:
            tiles_s = "".join(tile.to_code() for tile in meld.tiles)
            kind_name = {
                "chi": "吃",
                "pon": "碰",
                "daiminkan": "杠",
                "ankan": "暗",
                "shankuminkan": "加",
            }.get(meld.kind.value, meld.kind.value)
            parts.append(f"{kind_name}[{tiles_s}]")
        return " ".join(parts)

    def render_player_tree(
        self,
        state: GameState,
        last_actor_seat: int | None = None,
        last_action_str: str = "",
        seat_reasons: dict[int, str] | None = None,
        seat_decision_times: dict[int, float] | None = None,
        show_reason: bool = True,
        mode: RenderMode = "full",
    ) -> Group:
        """按档位渲染四家手牌。"""
        del last_action_str
        del seat_decision_times

        board = state.board
        table = state.table
        if not board:
            return Group(Text("未开始", style="dim"))

        dealer = table.dealer_seat
        dora_tiles = self._renderer.compute_dora_tiles(board.revealed_indicators)
        hand_labels = {
            seat: self._name_resolver.format_hand_label(seat, dealer) for seat in range(4)
        }
        label_width = self._compute_label_width(hand_labels.values())

        lines: list[Text] = []
        for seat in range(4):
            is_active = seat == last_actor_seat
            hand_text = self._render_hand_text(board, seat, dora_tiles)
            label_text = self._render_hand_label(hand_labels[seat], label_width, is_active)
            riichi_mark = self._build_riichi_mark(board, seat)

            if mode == "compact":
                lines.append(
                    self._render_compact_line(
                        board,
                        seat,
                        dealer,
                        label_text,
                        hand_text,
                        riichi_mark,
                        dora_tiles,
                    )
                )
            else:
                lines.extend(
                    self._render_multiline_block(
                        board,
                        seat,
                        dealer,
                        label_text,
                        hand_text,
                        riichi_mark,
                        dora_tiles,
                        mode,
                    )
                )
                if show_reason and mode == "full":
                    seat_reason = seat_reasons.get(seat) if seat_reasons else None
                    if seat_reason and seat == last_actor_seat:
                        lines.append(self._render_reason_line(seat_reason))

            if seat != 3:
                lines.append(Text(""))

        while lines and not lines[-1].plain:
            lines.pop()
        return Group(*lines)

    def _render_multiline_block(
        self,
        board,
        seat: int,
        dealer: int,
        label_text: Text,
        hand_text: Text,
        riichi_mark: str,
        dora_tiles: set,
        mode: RenderMode,
    ) -> list[Text]:
        lines = [
            Text.assemble(
                label_text,
                (" ", ""),
                hand_text,
                (riichi_mark, "bold bright_red" if riichi_mark else ""),
            )
        ]

        melds = board.melds[seat]
        if mode == "full":
            melds_text = self.format_melds(melds, seat, dealer)
            river_text = self._renderer.render_river(board.river, seat, dora_tiles)
        else:
            melds_text = self.format_melds_compact(melds)
            river_text = self._render_river_tail(board.river, seat, dora_tiles, limit=6)

        detail_line = Text.assemble(
            ("  ", "dim"),
            ("副露: ", "dim"),
            (melds_text if melds_text else "无", "bright_magenta" if melds else "dim"),
            (" | ", "dim"),
            ("牌河: ", "dim"),
        )
        if river_text.plain:
            detail_line.append(river_text)
        else:
            detail_line.append(Text("（无）", style="dim"))
        lines.append(detail_line)
        return lines

    def _render_compact_line(
        self,
        board,
        seat: int,
        dealer: int,
        label_text: Text,
        hand_text: Text,
        riichi_mark: str,
        dora_tiles: set,
    ) -> Text:
        melds = board.melds[seat]
        melds_text = self.format_melds_compact(melds)
        river_text = self._render_river_tail(board.river, seat, dora_tiles, limit=4)

        line = Text.assemble(
            label_text,
            (" ", ""),
            hand_text,
            (riichi_mark, "bold bright_red" if riichi_mark else ""),
            ("  |  ", "dim"),
            ("副露 ", "dim"),
            (melds_text if melds_text else "无", "bright_magenta" if melds else "dim"),
            ("  |  ", "dim"),
            ("河尾 ", "dim"),
        )
        if river_text.plain:
            line.append(river_text)
        else:
            line.append(Text("（无）", style="dim"))
        return line

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

    def _render_reason_line(self, reason: str) -> Text:
        clipped = reason if len(reason) <= 72 else f"{reason[:69]}..."
        return Text.assemble(
            ("  理由: ", "dim cyan"),
            (clipped, "italic bright_cyan"),
        )
