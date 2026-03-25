"""内核观测 / 场况 → JSON 友好结构。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from kernel.api.observation import Observation
from kernel.deal.model import BoardState
from kernel.hand.multiset import concealed_total
from kernel.play.model import kamicha_seat
from kernel.table.model import TableSnapshot
from kernel.tiles.model import Tile
from web.api.codec import meld_to_payload


def _hand_json(hand: Counter[Tile] | None) -> dict[str, int] | None:
    if hand is None:
        return None
    items = sorted(hand.items(), key=lambda kv: kv[0].to_code())
    return {t.to_code(): c for t, c in items}


def table_to_json(table: TableSnapshot) -> dict[str, Any]:
    return {
        "prevailing_wind": table.prevailing_wind.value,
        "round_number": table.round_number.value,
        "dealer_seat": table.dealer_seat,
        "honba": table.honba,
        "kyoutaku": table.kyoutaku,
        "scores": list(table.scores),
    }


def observation_to_json(
    obs: Observation,
    *,
    table: TableSnapshot,
    board: BoardState | None,
) -> dict[str, Any]:
    river = [
        {
            "tile": e.tile.to_code(),
            "seat": e.seat,
            "is_tsumogiri": e.is_tsumogiri,
            "is_riichi": e.is_riichi,
        }
        for e in obs.river
    ]
    dora = [t.to_code() for t in obs.dora_indicators]
    ura = [t.to_code() for t in obs.ura_indicators] if obs.ura_indicators is not None else None
    melds = [meld_to_payload(m) for m in obs.melds]
    out: dict[str, Any] = {
        "seat": obs.seat,
        "hand": _hand_json(obs.hand),
        "melds": melds,
        "river": river,
        "dora_indicators": dora,
        "ura_indicators": ura,
        "riichi_state": list(obs.riichi_state),
        "scores": list(obs.scores),
        "honba": obs.honba,
        "kyoutaku": obs.kyoutaku,
        "turn_seat": obs.turn_seat,
        "last_discard": obs.last_discard.to_code() if obs.last_discard else None,
        "last_discard_seat": obs.last_discard_seat,
        "wall_remaining": obs.wall_remaining,
        "dead_wall": [t.to_code() for t in obs.dead_wall] if obs.dead_wall else None,
        "table": table_to_json(table),
    }
    if obs.hands_by_seat is not None:
        out["hands_by_seat"] = [_hand_json(h) for h in obs.hands_by_seat]
    else:
        out["hands_by_seat"] = None

    if board is not None:
        out["melds_by_seat"] = [
            [meld_to_payload(m) for m in board.melds[s]] for s in range(4)
        ]
        out["last_draw_tile"] = (
            board.last_draw_tile.to_code() if board.last_draw_tile is not None else None
        )
        out["last_draw_seat"] = (
            board.current_seat if board.last_draw_tile is not None else None
        )
        out["turn_phase"] = board.turn_phase.value
        out["current_seat"] = board.current_seat
        cs = board.call_state
        if cs is not None:
            out["call_response_stage"] = cs.stage
            if cs.stage == "ron":
                out["call_active_seats"] = sorted(cs.ron_remaining)
            elif cs.stage == "pon_kan":
                out["call_active_seats"] = [cs.pon_kan_order[cs.pon_kan_idx]]
            else:
                out["call_active_seats"] = [kamicha_seat(cs.discard_seat)]
        if obs.hands_by_seat is None:
            out["concealed_count_by_seat"] = [
                concealed_total(board.hands[s]) for s in range(4)
            ]
    else:
        out["melds_by_seat"] = [[], [], [], []]
        out["last_draw_tile"] = None
        out["last_draw_seat"] = None
    return out
