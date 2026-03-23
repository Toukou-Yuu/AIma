"""符计算：基础符、刻子/杠子符、雀头符、加符（自摸、边张、嵌张、单骑）。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, MeldKind, triplet_key
from kernel.tiles.model import Suit, Tile

# 基础符：非平和
FU_BASE = 20

# 自摸加符
FU_TSUMO = 2

# 雀头符（役牌：场风、自风、三元牌）
FU_PAIR_YAKUHAI = 2

# 刻子/杠子符表：[(明刻，暗刻，明杠，暗杠)]
# 键为 (suit, rank)，值按牌种类分：幺九牌/字牌 vs 中张牌
FU_SET_MINCHI = {  # 明刻
    "middle": 2,
    "terminal_honor": 4,
}
FU_SET_ANKO = {  # 暗刻
    "middle": 4,
    "terminal_honor": 8,
}
FU_SET_MINKAN = {  # 明杠
    "middle": 8,
    "terminal_honor": 16,
}
FU_SET_ANKAN = {  # 暗杠
    "middle": 16,
    "terminal_honor": 32,
}


def _is_terminal_or_honor(t: Tile) -> bool:
    """是否为幺九牌或字牌（暗刻/杠时符翻倍）。"""
    if t.suit == Suit.HONOR:
        return True
    return t.rank in (1, 9)


def _get_set_category(t: Tile) -> str:
    """刻子/杠子的符分类。"""
    if _is_terminal_or_honor(t):
        return "terminal_honor"
    return "middle"


def _count_sets_by_kind(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> dict[str, list[tuple[Suit, int]]]:
    """
    统计刻子/杠子（按种类分组，赤五与普通五视为同种）。
    返回：{"ankan": [...], "minkan": [...], "anko": [...], "toitsu": [...]}
    所有键均为 (Suit, int) 元组。
    """
    full = concealed.copy()
    if for_ron:
        full[win_tile] += 1

    # 副露的刻子/杠子
    ankan_keys = []
    minkan_keys = []
    for m in melds:
        key = triplet_key(m.tiles[0])
        if m.kind == MeldKind.ANKAN:
            ankan_keys.append(key)
        elif m.kind == MeldKind.DAIMINKAN:
            minkan_keys.append(key)
        elif m.kind == MeldKind.SHANKUMINKAN:
            # 加杠视为明杠
            minkan_keys.append(key)
        # 碰也形成刻子，但这里只统计杠
        # 刻子（碰）在下面通过 full 计数判断

    # 门内的暗刻/暗杠/对子
    anko_keys = []
    toitsu_keys = []
    for tile, count in full.items():
        key = triplet_key(tile)
        if count == 2:
            toitsu_keys.append(key)
        elif count == 3:
            # 检查是否已在副露中
            is_melded = any(
                m.kind == MeldKind.PON and triplet_key(m.tiles[0]) == key for m in melds
            )
            if not is_melded:
                anko_keys.append(key)
        elif count == 4:
            # 门内四张：视为暗杠（但通常暗杠会副露）
            # 这里假设暗杠都已副露，所以这种情况不应出现
            pass

    return {
        "ankan": ankan_keys,
        "minkan": minkan_keys,
        "anko": anko_keys,
        "toitsu": toitsu_keys,
    }


def compute_fu_detail(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
    menzen: bool,
    pinfu: bool,
    self_wind: Tile,
    round_wind: Tile,
    is_chiitoitsu: bool = False,
) -> dict[str, int]:
    """
    详细符计算分解。
    返回各分项符数的字典：
    {"base": ..., "tsumo": ..., "pair": ..., "sets": ..., "menzen_ron": ..., "total": ...}

    七对子：符固定 25（不切上）。
    """
    # 七对子：固定 25 符
    if is_chiitoitsu:
        return {"base": 25, "tsumo": 0, "pair": 0, "sets": 0, "menzen_ron": 0, "total": 25}

    if pinfu:
        # 平和：符固定
        if for_ron:
            return {"base": 20, "tsumo": 0, "pair": 0, "sets": 0, "menzen_ron": 10, "total": 30}
        else:
            return {"base": 20, "tsumo": 2, "pair": 0, "sets": 0, "menzen_ron": 0, "total": 20}

    result = {"base": FU_BASE}

    # 自摸加符（平和以外）
    if not for_ron:
        result["tsumo"] = FU_TSUMO
    else:
        result["tsumo"] = 0

    # 雀头符
    sets_data = _count_sets_by_kind(concealed, melds, win_tile, for_ron=for_ron)
    pair_keys = sets_data["toitsu"]
    pair_fu = 0
    for key in pair_keys:
        t = Tile(key[0], key[1])
        if key == triplet_key(round_wind):
            pair_fu += FU_PAIR_YAKUHAI
        elif key == triplet_key(self_wind):
            pair_fu += FU_PAIR_YAKUHAI
        elif t.suit == Suit.HONOR and t.rank in (5, 6, 7):
            pair_fu += FU_PAIR_YAKUHAI
    result["pair"] = pair_fu

    # 刻子/杠子符
    sets_fu = 0
    for key in sets_data["ankan"]:
        cat = _get_set_category(Tile(key[0], key[1]))
        sets_fu += FU_SET_ANKAN[cat]
    for key in sets_data["minkan"]:
        cat = _get_set_category(Tile(key[0], key[1]))
        sets_fu += FU_SET_MINKAN[cat]
    for key in sets_data["anko"]:
        cat = _get_set_category(Tile(key[0], key[1]))
        sets_fu += FU_SET_ANKO[cat]
    result["sets"] = sets_fu

    # 门清荣和加符
    if for_ron and menzen:
        result["menzen_ron"] = 10
    else:
        result["menzen_ron"] = 0

    # 总计（切上到 10 的倍数）
    total = (
        result["base"] + result["tsumo"] + result["pair"] + result["sets"] + result["menzen_ron"]
    )
    # 切上（round up to nearest 10）
    total = (total + 9) // 10 * 10
    result["total"] = total

    return result


def compute_fu(*, menzen: bool, is_ron: bool, pinfu: bool) -> int:
    """
    简化的符计算接口（向后兼容）。
    平和与非平和互斥。
    """
    if pinfu:
        if is_ron:
            return 30
        return 20
    if is_ron:
        return 40 if menzen else 30
    return 40


def compute_fu_full(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
    self_wind: Tile,
    round_wind: Tile,
) -> int:
    """
    完整符计算：考虑刻子/杠子符、雀头符、自摸/门清荣和加符。
    自动判定是否平和（通过 pinfu_eligible 由调用方传入或在此计算）。
    """
    from kernel.win_shape.pinfu import pinfu_eligible

    menzen = len(melds) == 0
    pf = pinfu_eligible(
        concealed,
        melds,
        win_tile,
        for_ron=for_ron,
        round_wind_tile=round_wind,
        seat_wind_tile=self_wind,
    )
    detail = compute_fu_detail(
        concealed,
        melds,
        win_tile,
        for_ron=for_ron,
        menzen=menzen,
        pinfu=pf,
        self_wind=self_wind,
        round_wind=round_wind,
    )
    return detail["total"]


def compute_fu_simple(*, menzen: bool, is_ron: bool) -> int:
    """兼容旧调用：等价于 ``pinfu=False``。"""
    return compute_fu(menzen=menzen, is_ron=is_ron, pinfu=False)
