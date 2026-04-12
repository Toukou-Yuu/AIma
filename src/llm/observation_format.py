"""将内核观测与合法动作格式化为模型输入（自然语言格式）。"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation, RiverEntry
from kernel.tiles.model import Tile, Suit

if TYPE_CHECKING:
    from typing import Any


# 牌面中文映射
TILE_CN_MAP = {
    # 万子
    "1m": "一万", "2m": "二万", "3m": "三万", "4m": "四万", "5m": "五万",
    "6m": "六万", "7m": "七万", "8m": "八万", "9m": "九万",
    # 筒子
    "1p": "一筒", "2p": "二筒", "3p": "三筒", "4p": "四筒", "5p": "五筒",
    "6p": "六筒", "7p": "七筒", "8p": "八筒", "9p": "九筒",
    # 索子
    "1s": "一索", "2s": "二索", "3s": "三索", "4s": "四索", "5s": "五索",
    "6s": "六索", "7s": "七索", "8s": "八索", "9s": "九索",
    # 字牌
    "1z": "东", "2z": "南", "3z": "西", "4z": "北",
    "5z": "白", "6z": "发", "7z": "中",
    # 赤宝牌
    "5mr": "五万(赤)", "5pr": "五筒(赤)", "5sr": "五索(赤)",
}


def tile_to_cn(tile: Tile) -> str:
    """将牌编码转换为中文."""
    code = tile.to_code()
    return TILE_CN_MAP.get(code, code)


def _hand_to_cn(hand: Counter[Tile] | None) -> str:
    """将手牌转换为中文格式（按花色分组）."""
    if hand is None:
        return "无"

    # 按花色分组
    suits: dict[Suit, list[tuple[Tile, int]]] = {}
    for tile, count in hand.items():
        suit = tile.suit
        if suit not in suits:
            suits[suit] = []
        suits[suit].append((tile, count))

    # 花色名称映射
    suit_names = {
        Suit.MAN: "万子",
        Suit.PIN: "筒子",
        Suit.SOU: "索子",
        Suit.HONOR: "字牌",
    }

    # 构建输出
    lines = []
    for suit in [Suit.MAN, Suit.PIN, Suit.SOU, Suit.HONOR]:
        if suit in suits:
            tiles = sorted(suits[suit], key=lambda x: x[0].rank)
            parts = []
            for tile, count in tiles:
                cn = tile_to_cn(tile)
                if count > 1:
                    parts.append(cn * count)  # "西西" 表示两张西
                else:
                    parts.append(cn)
            lines.append(f"{suit_names[suit]}: {' '.join(parts)}")

    return "\n".join(lines) if lines else "无"


def _meld_to_cn(meld: Any) -> str:
    """将副露转换为中文."""
    tiles_str = " ".join(tile_to_cn(t) for t in meld.tiles)
    kind_cn = {
        "chii": "吃",
        "pon": "碰",
        "daiminkan": "明杠",
        "ankan": "暗杠",
        "shouminkan": "加杠",
    }
    kind_str = kind_cn.get(meld.kind.value, meld.kind.value)

    # 吃碰杠需要显示从哪里拿的
    extra = ""
    if meld.called_tile:
        extra = f"(叫{tile_to_cn(meld.called_tile)}"
        if meld.from_seat is not None:
            extra += f" 来自家{meld.from_seat}"
        extra += ")"

    return f"{kind_str} {tiles_str}{extra}"


def _river_to_cn(river: tuple[RiverEntry, ...], my_seat: int) -> str:
    """将牌河转换为中文."""
    if not river:
        return "空"

    entries = []
    for e in river:
        seat_name = "我" if e.seat == my_seat else f"家{e.seat}"
        tile_cn = tile_to_cn(e.tile)
        suffix = ""
        if e.is_riichi:
            suffix = "立直"
        elif e.is_tsumogiri:
            suffix = "摸切"
        entries.append(f"{seat_name}: {tile_cn}{suffix}")

    return ", ".join(entries)


def _calculate_wind(seat: int, dealer_seat: int) -> str:
    """根据座位和庄家计算风位。"""
    winds = ["东", "南", "西", "北"]
    return winds[(seat - dealer_seat) % 4]


def _action_to_cn(action: LegalAction, my_seat: int) -> str:
    """将合法动作转换为中文描述."""
    from kernel.engine.actions import ActionKind

    kind = action.kind

    if kind == ActionKind.DISCARD:
        tile_cn = tile_to_cn(action.tile)
        riichi = "并立直" if action.declare_riichi else ""
        return f"打{tile_cn}{riichi}"

    if kind == ActionKind.PASS_CALL:
        return "过"

    if kind == ActionKind.DRAW:
        return "摸牌"

    if kind == ActionKind.RON:
        tile_cn = tile_to_cn(action.win_tile) if action.win_tile else ""
        return f"荣和{tile_cn}"

    if kind == ActionKind.TSUMO:
        return "自摸"

    if kind == ActionKind.OPEN_MELD and action.meld:
        return _meld_to_cn(action.meld)

    if kind == ActionKind.ANKAN and action.meld:
        return f"暗杠 {_meld_to_cn(action.meld)}"

    if kind == ActionKind.SHOUMINKAN and action.meld:
        return f"加杠 {_meld_to_cn(action.meld)}"

    if kind == ActionKind.RIICHI:
        return "立直宣言"

    return kind.value


def build_natural_prompt(obs: Observation, legal: tuple[LegalAction, ...]) -> str:
    """构建自然语言格式 prompt（更直观，节省 token）.

    格式设计：
    - 手牌按花色分组，使用中文牌名
    - 合法动作简洁描述
    - 避免JSON冗余，减少token消耗
    """
    lines = []

    # 1. 基本信息
    wind = _calculate_wind(obs.seat, obs.dealer_seat)
    lines.append(f"【当前状态】")
    lines.append(f"你是家{obs.seat}({wind}位)")

    # 2. 手牌
    hand_count = sum(obs.hand.values()) if obs.hand else 0
    lines.append(f"\n【手牌】({hand_count}张)")
    lines.append(_hand_to_cn(obs.hand))

    # 3. 副露（自家）
    if obs.melds:
        lines.append(f"\n【我的副露】")
        for m in obs.melds:
            lines.append(_meld_to_cn(m))

    # 4. 他家副露
    other_melds = []
    for seat_idx, seat_melds in enumerate(obs.all_melds):
        if seat_idx != obs.seat and seat_melds:
            for m in seat_melds:
                other_melds.append(f"家{seat_idx}: {_meld_to_cn(m)}")
    if other_melds:
        lines.append(f"\n【他家副露】")
        lines.append(", ".join(other_melds))

    # 5. 宝牌指示牌
    dora_str = ", ".join(tile_to_cn(t) for t in obs.dora_indicators)
    lines.append(f"\n【宝牌指示牌】{dora_str}")

    # 6. 牌河（完整显示）
    if obs.river:
        lines.append(f"\n【牌河】(共{len(obs.river)}张)")
        lines.append(_river_to_cn(obs.river, obs.seat))

    # 7. 立直状态
    riichi_players = [i for i, r in enumerate(obs.riichi_state) if r]
    if riichi_players:
        lines.append(f"\n【立直中】家{', 家'.join(map(str, riichi_players))}")

    # 8. 分数
    scores_str = ", ".join(f"家{i}:{s}" for i, s in enumerate(obs.scores))
    lines.append(f"\n【分数】{scores_str}")

    # 9. 最后打出的牌（用于判断能否荣和）
    if obs.last_discard:
        last_cn = tile_to_cn(obs.last_discard)
        last_seat = obs.last_discard_seat
        lines.append(f"\n【刚才打出】家{last_seat} 打 {last_cn}")

    # 10. 合法动作
    lines.append(f"\n【可选动作】")
    action_strs = [_action_to_cn(a, obs.seat) for a in legal]
    lines.append(", ".join(action_strs))

    # 11. 提示输出格式
    lines.append(f"\n【输出要求】")
    lines.append("选择一个动作，用JSON格式输出，包含 why 字段说明理由（不超过30字）。")
    lines.append("示例: {\"action\": \"打三万\", \"why\": \"孤立牌，进张面窄\"}")

    return "\n".join(lines)


# 保留原有函数供兼容（但不再使用）
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
    """构建用户提示（自然语言格式，更直观）."""
    return build_natural_prompt(obs, legal)


def build_decision_prompt(obs: Observation, legal: tuple[LegalAction, ...]) -> str:
    """构建决策提示（保留原有JSON格式供调试）."""
    body = {
        "observation": observation_to_prompt_dict(obs),
        "legal_actions": [legal_action_to_wire(la) for la in legal],
    }
    return json.dumps(body, ensure_ascii=False, indent=2)


def _calculate_hand_changes(
    prev_hand: Counter[Tile],
    curr_hand: Counter[Tile],
) -> dict[str, list[str]]:
    """计算手牌变化：摸到和打出.

    Args:
        prev_hand: 上回合手牌
        curr_hand: 当前手牌

    Returns:
        {"drew": ["7p"], "discarded": ["3m"]}
    """
    changes = {"drew": [], "discarded": []}

    all_tiles = set(prev_hand.keys()) | set(curr_hand.keys())
    for tile in all_tiles:
        prev_count = prev_hand.get(tile, 0)
        curr_count = curr_hand.get(tile, 0)
        if curr_count > prev_count:
            changes["drew"].extend([tile.to_code()] * (curr_count - prev_count))
        elif prev_count > curr_count:
            changes["discarded"].extend([tile.to_code()] * (prev_count - curr_count))

    return changes


def _river_entries_to_actions(river_entries: tuple[RiverEntry, ...]) -> list[str]:
    """将牌河条目转换为动作描述."""
    actions = []
    for entry in river_entries:
        seat_name = f"家{entry.seat}"
        tile_str = entry.tile.to_code()
        if entry.is_riichi:
            actions.append(f"{seat_name} 打{tile_str}立直")
        elif entry.is_tsumogiri:
            actions.append(f"{seat_name} 摸切{tile_str}")
        else:
            actions.append(f"{seat_name} 打{tile_str}")
    return actions


def build_delta_observation(
    curr_obs: Observation,
    prev_obs: Observation,
    prev_hand: Counter[Tile] | None = None,
) -> dict[str, Any]:
    """生成变化帧（只包含从上回合的变化）.

    Args:
        curr_obs: 当前观测
        prev_obs: 上回合观测
        prev_hand: 上回合手牌（可选，用于计算手牌变化）

    Returns:
        变化帧字典
    """
    delta: dict[str, Any] = {
        "frame_type": "delta",
        "seat": curr_obs.seat,
        "wind": _calculate_wind(curr_obs.seat, curr_obs.dealer_seat),
    }

    # 我的手牌变化
    if prev_hand and curr_obs.hand:
        my_changes = _calculate_hand_changes(prev_hand, curr_obs.hand)
        if my_changes["drew"]:
            delta["my_draw"] = my_changes["drew"][0]  # 通常只有一张
        if my_changes["discarded"]:
            delta["my_discard"] = my_changes["discarded"][0]

    # 当前完整手牌（用于确认）
    delta["current_hand"] = _hand_dict(curr_obs.hand)
    delta["current_melds"] = [
        {
            "kind": m.kind.value,
            "tiles": [t.to_code() for t in m.tiles],
        }
        for m in curr_obs.melds
    ]

    # 对手动作（从牌河新增条目推断）
    if curr_obs.river and prev_obs.river:
        new_river = curr_obs.river[len(prev_obs.river):]
        if new_river:
            delta["others_actions"] = _river_entries_to_actions(new_river)

    # 宝牌变化
    if len(curr_obs.dora_indicators) > len(prev_obs.dora_indicators):
        delta["new_dora"] = curr_obs.dora_indicators[-1].to_code()

    # 立直状态变化
    new_riichi = []
    for i, (curr, prev) in enumerate(zip(curr_obs.riichi_state, prev_obs.riichi_state)):
        if curr and not prev:
            new_riichi.append(i)
    if new_riichi:
        delta["new_riichi"] = new_riichi

    # 分数变化（如果有人和牌）
    if curr_obs.scores != prev_obs.scores:
        delta["score_changes"] = {
            i: curr - prev
            for i, (curr, prev) in enumerate(zip(curr_obs.scores, prev_obs.scores))
            if curr != prev
        }

    # 当前分数
    delta["current_scores"] = list(curr_obs.scores)

    return delta
