"""Event extractors: Ron, Tsumo, Riichi, Call, Flow."""

from __future__ import annotations

from typing import Iterator

from metrics.extractors.base import BaseExtractor
from metrics.loader import RunData
from metrics.schema import MetricRecord


class RonExtractor(BaseExtractor):
    """Extract ron (win by discard) metrics.

    Yields MetricRecord for each RonEvent with:
        - kind: "ron"
        - seat: winner seat
        - hand_index: hand index
        - values: win_tile, discard_seat
    """

    name = "ron"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract ron metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for each ron event.
        """
        hand_index = 0
        for event_record in data.events:
            event = event_record.event
            event_type = event.get("event_type")

            if event_type == "ron":
                seat = event.get("seat")
                win_tile = event.get("win_tile", "")
                discard_seat = event.get("discard_seat")

                yield MetricRecord(
                    kind="ron",
                    match_id=data.match_id,
                    job_id=data.job_id,
                    seat=seat,
                    hand_index=hand_index,
                    values={
                        "win_tile": win_tile,
                        "discard_seat": discard_seat,
                    },
                )
            elif event_type == "hand_over":
                hand_index += 1


class TsumoExtractor(BaseExtractor):
    """Extract tsumo (self-draw win) metrics.

    Yields MetricRecord for each TsumoEvent with:
        - kind: "tsumo"
        - seat: winner seat
        - hand_index: hand index
        - values: win_tile, is_rinshan
    """

    name = "tsumo"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract tsumo metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for each tsumo event.
        """
        hand_index = 0
        for event_record in data.events:
            event = event_record.event
            event_type = event.get("event_type")

            if event_type == "tsumo":
                seat = event.get("seat")
                win_tile = event.get("win_tile", "")
                is_rinshan = event.get("is_rinshan", False)

                yield MetricRecord(
                    kind="tsumo",
                    match_id=data.match_id,
                    job_id=data.job_id,
                    seat=seat,
                    hand_index=hand_index,
                    values={
                        "win_tile": win_tile,
                        "is_rinshan": is_rinshan,
                    },
                )
            elif event_type == "hand_over":
                hand_index += 1


class RiichiExtractor(BaseExtractor):
    """Extract riichi declaration metrics.

    Yields MetricRecord for each riichi declaration (DiscardTileEvent with declare_riichi=True).

        - kind: "riichi"
        - seat: player who declared riichi
        - hand_index: hand index
        - values: tile, is_tsumogiri
    """

    name = "riichi"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract riichi metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for each riichi declaration.
        """
        hand_index = 0
        for event_record in data.events:
            event = event_record.event
            event_type = event.get("event_type")

            if event_type == "discard_tile":
                declare_riichi = event.get("declare_riichi", False)
                if declare_riichi:
                    seat = event.get("seat")
                    tile = event.get("tile", "")
                    is_tsumogiri = event.get("is_tsumogiri", False)

                    yield MetricRecord(
                        kind="riichi",
                        match_id=data.match_id,
                        job_id=data.job_id,
                        seat=seat,
                        hand_index=hand_index,
                        values={
                            "tile": tile,
                            "is_tsumogiri": is_tsumogiri,
                        },
                    )
            elif event_type == "hand_over":
                hand_index += 1


class CallExtractor(BaseExtractor):
    """Extract call (meld) metrics.

    Yields MetricRecord for each CallEvent with:
        - kind: "call"
        - seat: player who called
        - hand_index: hand index
        - values: call_kind, meld_type
    """

    name = "call"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract call metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for each call event.
        """
        hand_index = 0
        for event_record in data.events:
            event = event_record.event
            event_type = event.get("event_type")

            if event_type == "call":
                seat = event.get("seat")
                call_kind = event.get("call_kind", "")
                meld = event.get("meld", {})
                meld_type = meld.get("kind", "") if isinstance(meld, dict) else ""

                yield MetricRecord(
                    kind="call",
                    match_id=data.match_id,
                    job_id=data.job_id,
                    seat=seat,
                    hand_index=hand_index,
                    values={
                        "call_kind": call_kind,
                        "meld_type": meld_type,
                        "is_kan": call_kind in ("ankan", "daiminkan", "kakan"),
                    },
                )
            elif event_type == "hand_over":
                hand_index += 1


class FlowExtractor(BaseExtractor):
    """Extract flow (draw/exhaustive draw) metrics.

    Yields MetricRecord for each FlowEvent with:
        - kind: "flow"
        - seat: None (flow affects all players)
        - hand_index: hand index
        - values: flow_kind, tenpai_seats
    """

    name = "flow"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract flow metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for each flow event.
        """
        hand_index = 0
        for event_record in data.events:
            event = event_record.event
            event_type = event.get("event_type")

            if event_type == "flow":
                flow_kind = event.get("flow_kind", "")
                tenpai_seats = event.get("tenpai_seats", [])

                if isinstance(tenpai_seats, list):
                    tenpai_seats = tuple(tenpai_seats)

                yield MetricRecord(
                    kind="flow",
                    match_id=data.match_id,
                    job_id=data.job_id,
                    seat=None,
                    hand_index=hand_index,
                    values={
                        "flow_kind": flow_kind,
                        "tenpai_seats": tenpai_seats,
                        "tenpai_count": len(tenpai_seats) if tenpai_seats else 0,
                    },
                )
            elif event_type == "hand_over":
                hand_index += 1