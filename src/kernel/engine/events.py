"""事件构建器：维护序列号并生成结构化事件日志。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    GameEvent,
    HandOverEvent,
    MatchEndEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
    WinSettlementLine,
)

if TYPE_CHECKING:
    from kernel.flow.model import FlowKind
    from kernel.hand.melds import Meld
    from kernel.tiles.model import Tile


class EventBuilder:
    """事件构建器：维护序列号并生成事件。"""

    def __init__(self, start_sequence: int = 0) -> None:
        self._sequence = start_sequence

    def next_sequence(self) -> int:
        seq = self._sequence
        self._sequence += 1
        return seq

    def round_begin(
        self,
        dealer_seat: int,
        dora_indicator: "Tile",
        seeds: tuple[int, ...],
    ) -> RoundBeginEvent:
        return RoundBeginEvent(
            seat=None,
            sequence=self.next_sequence(),
            dealer_seat=dealer_seat,
            dora_indicator=dora_indicator,
            seeds=seeds,
        )

    def draw_tile(
        self,
        seat: int,
        tile: "Tile",
        is_rinshan: bool,
        wall_remaining: int,
    ) -> DrawTileEvent:
        return DrawTileEvent(
            seat=seat,
            sequence=self.next_sequence(),
            tile=tile,
            is_rinshan=is_rinshan,
            wall_remaining=wall_remaining,
        )

    def discard_tile(
        self,
        seat: int,
        tile: "Tile",
        is_tsumogiri: bool,
        declare_riichi: bool,
    ) -> DiscardTileEvent:
        return DiscardTileEvent(
            seat=seat,
            sequence=self.next_sequence(),
            tile=tile,
            is_tsumogiri=is_tsumogiri,
            declare_riichi=declare_riichi,
        )

    def call(
        self,
        seat: int,
        meld: "Meld",
        call_kind: str,
    ) -> CallEvent:
        return CallEvent(
            seat=seat,
            sequence=self.next_sequence(),
            meld=meld,
            call_kind=call_kind,
        )

    def ron(
        self,
        seat: int,
        win_tile: "Tile",
        discard_seat: int,
    ) -> RonEvent:
        return RonEvent(
            seat=seat,
            sequence=self.next_sequence(),
            win_tile=win_tile,
            discard_seat=discard_seat,
        )

    def tsumo(
        self,
        seat: int,
        win_tile: "Tile",
        is_rinshan: bool,
    ) -> TsumoEvent:
        return TsumoEvent(
            seat=seat,
            sequence=self.next_sequence(),
            win_tile=win_tile,
            is_rinshan=is_rinshan,
        )

    def flow(
        self,
        flow_kind: "FlowKind",
        tenpai_seats: frozenset[int],
    ) -> FlowEvent:
        return FlowEvent(
            seat=None,
            sequence=self.next_sequence(),
            flow_kind=flow_kind,
            tenpai_seats=tenpai_seats,
        )

    def hand_over(
        self,
        winners: tuple[int, ...],
        payments: tuple[int, int, int, int],
        win_lines: tuple[WinSettlementLine, ...] = (),
    ) -> HandOverEvent:
        return HandOverEvent(
            seat=None,
            sequence=self.next_sequence(),
            winners=winners,
            payments=payments,
            win_lines=win_lines,
        )

    def match_end(
        self,
        ranking: tuple[int, int, int, int],
        final_scores: tuple[int, int, int, int],
    ) -> MatchEndEvent:
        return MatchEndEvent(
            seat=None,
            sequence=self.next_sequence(),
            ranking=ranking,
            final_scores=final_scores,
        )