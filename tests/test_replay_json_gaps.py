"""replay_json 覆盖缺口测试：错误路径与可选字段。"""

from __future__ import annotations

from kernel.engine.actions import Action, ActionKind
from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    HandOverEvent,
    MatchEndEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
    WinSettlementLine,
)
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.replay_json import (
    actions_from_match_log,
    game_event_from_wire,
    game_event_to_wire,
    match_log_document,
    meld_from_wire,
    meld_to_wire,
    tile_from_code,
    win_line_from_wire,
    win_line_to_wire,
)
from kernel.tiles.model import Suit, Tile

MAN1 = Tile(Suit.MAN, 1)
MAN5 = Tile(Suit.MAN, 5)
MAN5R = Tile(Suit.MAN, 5, is_red=True)
PIN5 = Tile(Suit.PIN, 5)
TON = Tile(Suit.HONOR, 1)
HAKU = Tile(Suit.HONOR, 5)


# --- tile_from_code error paths ---

class TestTileFromCodeErrors:
    def test_red_on_non_5(self) -> None:
        try:
            tile_from_code("3mr")
            raise AssertionError("expected ValueError for red on non-5")
        except ValueError:
            pass

    def test_invalid_format(self) -> None:
        try:
            tile_from_code("abc")
            raise AssertionError("expected ValueError for invalid format")
        except ValueError:
            pass

    def test_honor_tiles(self) -> None:
        assert tile_from_code("1z") == TON
        assert tile_from_code("5z") == HAKU


# --- meld_from_wire with from_seat ---

class TestMeldFromWire:
    def test_from_seat(self) -> None:
        data = {"kind": "pon", "tiles": ["1m", "1m", "1m"], "called_tile": "1m", "from_seat": 2}
        meld = meld_from_wire(data)
        assert meld.from_seat == 2

    def test_no_from_seat(self) -> None:
        data = {"kind": "pon", "tiles": ["1m", "1m", "1m"], "called_tile": "1m"}
        meld = meld_from_wire(data)
        assert meld.from_seat is None


# --- win_line optional fields ---

class TestWinLineOptionalFields:
    def test_with_all_optional_fields(self) -> None:
        line = WinSettlementLine(
            seat=1, win_kind="ron", han=2, fu=30,
            hand_pattern="一般形", yakus=("立直",),
            discard_seat=0, payment_from_discarder=2000,
            tsumo_deltas=(-2000, 2000, 0, 0),
            kyoutaku_share=1000, points=3000,
        )
        d = win_line_to_wire(line)
        assert d["discard_seat"] == 0
        assert d["payment_from_discarder"] == 2000
        assert d["tsumo_deltas"] == [-2000, 2000, 0, 0]

        line2 = win_line_from_wire(d)
        assert line2.discard_seat == 0
        assert line2.payment_from_discarder == 2000
        assert line2.tsumo_deltas == (-2000, 2000, 0, 0)

    def test_without_optional_fields(self) -> None:
        line = WinSettlementLine(
            seat=0, win_kind="tsumo", han=1, fu=30,
            hand_pattern="一般形", yakus=(),
            kyoutaku_share=0, points=1000,
        )
        d = win_line_to_wire(line)
        assert "discard_seat" not in d
        assert "tsumo_deltas" not in d

        line2 = win_line_from_wire(d)
        assert line2.discard_seat is None
        assert line2.tsumo_deltas is None


# --- game_event_to_wire / game_event_from_wire roundtrip ---

class TestGameEventRoundtrip:
    def test_round_begin(self) -> None:
        ev = RoundBeginEvent(seat=None, sequence=0, dealer_seat=0, dora_indicator=MAN1, seeds=(0, 13))
        d = game_event_to_wire(ev)
        assert d["event_type"] == "round_begin"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, RoundBeginEvent)
        assert ev2.dealer_seat == 0

    def test_draw_tile(self) -> None:
        ev = DrawTileEvent(seat=0, sequence=1, tile=MAN5, is_rinshan=False, wall_remaining=68)
        d = game_event_to_wire(ev)
        assert d["event_type"] == "draw_tile"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, DrawTileEvent)
        assert ev2.tile == MAN5

    def test_discard_tile(self) -> None:
        ev = DiscardTileEvent(seat=0, sequence=2, tile=MAN1, is_tsumogiri=True, declare_riichi=False)
        d = game_event_to_wire(ev)
        assert d["event_type"] == "discard_tile"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, DiscardTileEvent)

    def test_call(self) -> None:
        meld = Meld(MeldKind.PON, (MAN1, MAN1, MAN1), MAN1)
        ev = CallEvent(seat=1, sequence=3, meld=meld, call_kind="pon")
        d = game_event_to_wire(ev)
        assert d["event_type"] == "call"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, CallEvent)
        assert ev2.call_kind == "pon"

    def test_ron(self) -> None:
        ev = RonEvent(seat=1, sequence=4, win_tile=MAN1, discard_seat=0)
        d = game_event_to_wire(ev)
        assert d["event_type"] == "ron"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, RonEvent)
        assert ev2.win_tile == MAN1

    def test_tsumo(self) -> None:
        ev = TsumoEvent(seat=0, sequence=5, win_tile=MAN5, is_rinshan=False)
        d = game_event_to_wire(ev)
        assert d["event_type"] == "tsumo"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, TsumoEvent)

    def test_flow(self) -> None:
        ev = FlowEvent(seat=None, sequence=6, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset({0, 2}))
        d = game_event_to_wire(ev)
        assert d["event_type"] == "flow"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, FlowEvent)
        assert 0 in ev2.tenpai_seats

    def test_hand_over(self) -> None:
        wl = WinSettlementLine(
            seat=1, win_kind="ron", han=2, fu=30,
            hand_pattern="一般形", yakus=("立直",),
            discard_seat=0, payment_from_discarder=2000,
            kyoutaku_share=0, points=2000,
        )
        ev = HandOverEvent(seat=None, sequence=7, winners=(1,), payments=(-2000, 2000, 0, 0), win_lines=(wl,))
        d = game_event_to_wire(ev)
        assert d["event_type"] == "hand_over"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, HandOverEvent)
        assert ev2.winners == (1,)

    def test_match_end(self) -> None:
        ev = MatchEndEvent(seat=None, sequence=8, ranking=(0, 1, 2, 3), final_scores=(30000, 25000, 25000, 20000))
        d = game_event_to_wire(ev)
        assert d["event_type"] == "match_end"
        ev2 = game_event_from_wire(d)
        assert isinstance(ev2, MatchEndEvent)
        assert ev2.ranking == (0, 1, 2, 3)


# --- actions_from_match_log ---

class TestActionsFromMatchLog:
    def test_invalid_version(self) -> None:
        try:
            actions_from_match_log({"format_version": 99, "actions": []})
            raise AssertionError("expected ValueError for invalid version")
        except ValueError:
            pass

    def test_missing_actions(self) -> None:
        try:
            actions_from_match_log({"format_version": 1})
            raise AssertionError("expected ValueError for missing actions")
        except ValueError:
            pass


# --- match_log_document optional fields ---

class TestMatchLogDocument:
    def test_with_optional_fields(self) -> None:
        doc = match_log_document(
            seed=42, stopped_reason="normal", steps=10, final_phase="MATCH_END",
            actions_wire=(), events_wire=(),
            reasons=("reason1", None),
            token_diagnostics=({"tokens": 100}, None),
            players=({"name": "p1"},),
        )
        assert doc["reasons"] == ["reason1", None]
        assert doc["token_diagnostics"] == [{"tokens": 100}, None]
        assert doc["players"] == [{"name": "p1"}]

    def test_without_optional_fields(self) -> None:
        doc = match_log_document(
            seed=42, stopped_reason="normal", steps=10, final_phase="MATCH_END",
            actions_wire=(), events_wire=(),
        )
        assert "reasons" not in doc
        assert "token_diagnostics" not in doc
        assert "players" not in doc
