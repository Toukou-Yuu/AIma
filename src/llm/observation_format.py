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


def _calculate_wind(seat: int, dealer_seat: int) -> str:
    """根据座位和庄家计算风位。"""
    winds = ["東", "南", "西", "北"]
    # (seat - dealer_seat) % 4 得到相对风位
    return winds[(seat - dealer_seat) % 4]


def build_compressed_observation(
    obs: Observation,
    prev_obs: Observation | None = None,
    max_river_entries: int = 10,
) -> dict[str, Any]:
    """构建压缩观测，减少冗余信息.

    Args:
        obs: 当前观测
        prev_obs: 上回合观测（用于生成变化说明，可选）
        max_river_entries: 保留的牌河条目数（默认最近10张）

    Returns:
        压缩后的观测字典
    """
    # 基础信息（完整保留）
    out: dict[str, Any] = {
        "seat": obs.seat,
        "wind": _calculate_wind(obs.seat, obs.dealer_seat),
        "dealer_seat": obs.dealer_seat,
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
        "dora_indicators": [t.to_code() for t in obs.dora_indicators],
        "riichi_state": list(obs.riichi_state),
        "scores": list(obs.scores),
        "honba": obs.honba,
        "kyoutaku": obs.kyoutaku,
        "turn_seat": obs.turn_seat,
        "last_discard": obs.last_discard.to_code() if obs.last_discard else None,
        "last_discard_seat": obs.last_discard_seat,
    }

    # 压缩牌河：只保留最近 N 张
    if obs.river:
        recent_river = obs.river[-max_river_entries:]
        out["recent_river"] = _river_entries(recent_river)
        out["river_total"] = len(obs.river)  # 保留总数用于参考
    else:
        out["recent_river"] = []
        out["river_total"] = 0

    # 压缩他家副露：只保留关键信息
    if obs.all_melds:
        out["other_melds"] = []
        for seat_idx, seat_melds in enumerate(obs.all_melds):
            if seat_idx != obs.seat and seat_melds:  # 跳过自家
                melds_summary = []
                for m in seat_melds:
                    melds_summary.append({
                        "kind": m.kind.value,
                        "tiles": [t.to_code() for t in m.tiles],
                    })
                out["other_melds"].append({
                    "seat": seat_idx,
                    "melds": melds_summary,
                })

    # 可选：生成变化说明
    if prev_obs is not None:
        changes = _calculate_changes(prev_obs, obs)
        if changes:
            out["changes"] = changes

    return out


def _calculate_changes(prev_obs: Observation, curr_obs: Observation) -> dict[str, Any] | None:
    """计算两回合之间的变化."""
    changes: dict[str, Any] = {}

    # 计算手牌变化
    if prev_obs.hand and curr_obs.hand:
        # 找出新增的牌（摸到）
        added = []
        removed = []

        all_tiles = set(prev_obs.hand.keys()) | set(curr_obs.hand.keys())
        for tile in all_tiles:
            prev_count = prev_obs.hand.get(tile, 0)
            curr_count = curr_obs.hand.get(tile, 0)
            if curr_count > prev_count:
                added.extend([tile.to_code()] * (curr_count - prev_count))
            elif prev_count > curr_count:
                removed.extend([tile.to_code()] * (prev_count - curr_count))

        if added:
            changes["drew"] = added
        if removed:
            changes["discarded"] = removed

    # 计算牌河新增
    if curr_obs.river and prev_obs.river:
        new_river_entries = curr_obs.river[len(prev_obs.river):]
        if new_river_entries:
            changes["new_river"] = _river_entries(new_river_entries)

    return changes if changes else None


def observation_to_prompt_dict(obs: Observation) -> dict[str, Any]:
    """人类观测 → 可 JSON 序列化的 dict（不含 debug 王牌等敏感扩展给模型时可裁剪）."""
    out: dict[str, Any] = {
        "seat": obs.seat,
        "wind": _calculate_wind(obs.seat, obs.dealer_seat),
        "dealer_seat": obs.dealer_seat,
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
        "melds_by_seat": [
            [
                {
                    "kind": m.kind.value,
                    "tiles": [t.to_code() for t in m.tiles],
                    **({"called_tile": m.called_tile.to_code()} if m.called_tile is not None else {}),
                    **({"from_seat": m.from_seat} if m.from_seat is not None else {}),
                }
                for m in seat_melds
            ]
            for seat_melds in obs.all_melds
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
