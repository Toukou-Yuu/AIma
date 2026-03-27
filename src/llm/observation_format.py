"""将内核观测与合法动作格式化为模型输入（JSON 文本）。"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation, RiverEntry
from kernel.tiles.model import Tile
from llm.wire import legal_action_to_wire


def _hand_dict(hand: Counter[Tile] | None) -> dict[str, int] | None:
    if hand is None:
        return None
    items = sorted(hand.items(), key=lambda kv: kv[0].to_code())
    return {t.to_code(): c for t, c in items}


def _river_entries(river: tuple[RiverEntry, ...]) -> list[dict[str, Any]]:
    return [
        {
            "tile": e.tile.to_code(),
            "seat": e.seat,
            "is_tsumogiri": e.is_tsumogiri,
            "is_riichi": e.is_riichi,
        }
        for e in river
    ]


def observation_to_prompt_dict(obs: Observation) -> dict[str, Any]:
    """人类观测 → 可 JSON 序列化的 dict（不含 debug 王牌等敏感扩展给模型时可裁剪）。"""
    out: dict[str, Any] = {
        "seat": obs.seat,
        "phase": obs.phase.value,
        "hand": _hand_dict(obs.hand),
        "melds": [
            {
                "kind": m.kind.value,
                "tiles": [t.to_code() for t in m.tiles],
                **({"called_tile": m.called_tile.to_code()} if m.called_tile is not None else {}),
                **({"from_seat": m.from_seat} if m.from_seat is not None else {}),
            }
            for m in obs.melds
        ],
        "river": _river_entries(obs.river),
        "dora_indicators": [t.to_code() for t in obs.dora_indicators],
        "riichi_state": list(obs.riichi_state),
        "scores": list(obs.scores),
        "honba": obs.honba,
        "kyoutaku": obs.kyoutaku,
        "turn_seat": obs.turn_seat,
        "last_discard": obs.last_discard.to_code() if obs.last_discard else None,
        "last_discard_seat": obs.last_discard_seat,
    }
    return out


def build_user_prompt(obs: Observation, legal: tuple[LegalAction, ...]) -> str:
    """拼装 user 消息：局面 JSON + 合法动作列表。"""
    body = {
        "observation": observation_to_prompt_dict(obs),
        "legal_actions": [legal_action_to_wire(la) for la in legal],
    }
    return json.dumps(body, ensure_ascii=False, indent=2)


SYSTEM_PROMPT = (
    "你是日式麻将（立直麻将）的牌手代理。你只能从给出的 legal_actions 中"
    "**精确选择一条**执行。\n"
    "输出要求：仅输出一行 JSON 对象，不要 markdown 代码块，不要其它解释。\n"
    "JSON 字段必须与所选 legal_actions 中某一项完全一致"
    "（含 kind、seat；discard 须含 tile；需要时含 declare_riichi、meld）。\n"
    '示例：{"kind":"discard","seat":0,"tile":"3m"}\n'
    '示例：{"kind":"pass_call","seat":1}\n'
)
