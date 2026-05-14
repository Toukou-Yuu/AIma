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


def _wait_type_fu(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> int:
    """
    听牌类型加符：嵌张/单骑/边张 +2，两面/双碰 0。
    仅在荣和时判定（自摸的听牌类型由荣和同理推导）。
    """
    # 构造和了前的 13 张门内
    before = Counter(concealed)
    if for_ron:
        # 荣和：concealed 是 13 张，win_tile 是第 14 张
        pass
    else:
        # 自摸：concealed 是 14 张（含摸到的牌），减去 win_tile 得到 13 张
        before[win_tile] -= 1
        if before[win_tile] == 0:
            del before[win_tile]

    wt_key = triplet_key(win_tile)

    # 单骑听：win_tile 在 before 中恰好 1 张（对子听第 3 张）
    if before.get(win_tile, 0) == 1:
        test = Counter(before)
        test[win_tile] -= 1
        if test[win_tile] == 0:
            del test[win_tile]
        # 移除对子的一张后，剩余应恰好组成 4 - 副露组面子
        mentsu_needed = 4 - len(melds)
        if sum(test.values()) == mentsu_needed * 3:
            if _can_fill_mentsu(_to_vec34(test), mentsu_needed):
                return 2

    # 顺子听：win_tile 与 before 中的牌组成顺子
    if win_tile.suit != Suit.HONOR:
        suit = win_tile.suit
        rank = win_tile.rank

        mentsu_needed = 4 - len(melds) - 1  # 等待的面子 + 副露

        # 嵌张：1_3 → 2（中间牌）
        if 2 <= rank <= 8:
            low = Tile(suit, rank - 1, False)
            high = Tile(suit, rank + 1, False)
            if before.get(low, 0) >= 1 and before.get(high, 0) >= 1:
                test = Counter(before)
                test[low] -= 1
                test[high] -= 1
                if test[low] == 0:
                    del test[low]
                if test[high] == 0:
                    del test[high]
                if _can_form_melds_and_pair(test, mentsu_needed):
                    return 2

        # 边张：12 → 3
        if rank == 3:
            t1, t2 = Tile(suit, 1, False), Tile(suit, 2, False)
            if before.get(t1, 0) >= 1 and before.get(t2, 0) >= 1:
                test = Counter(before)
                test[t1] -= 1
                test[t2] -= 1
                for t in (t1, t2):
                    if test[t] == 0:
                        del test[t]
                if _can_form_melds_and_pair(test, mentsu_needed):
                    return 2

        # 边张：89 → 7
        if rank == 7:
            t8, t9 = Tile(suit, 8, False), Tile(suit, 9, False)
            if before.get(t8, 0) >= 1 and before.get(t9, 0) >= 1:
                test = Counter(before)
                test[t8] -= 1
                test[t9] -= 1
                for t in (t8, t9):
                    if test[t] == 0:
                        del test[t]
                if _can_form_melds_and_pair(test, mentsu_needed):
                    return 2

    return 0


def _can_form_melds_and_pair(tiles: Counter[Tile], melds_needed: int) -> bool:
    """检查 tiles 能否恰好分解为 melds_needed 组面子 + 1 对子。"""
    total = sum(tiles.values())
    if total != melds_needed * 3 + 2:
        return False
    vec = _to_vec34(tiles)
    # 枚举所有可能的对子
    for i in range(34):
        if vec[i] >= 2:
            vec[i] -= 2
            if _can_fill_mentsu(vec, melds_needed):
                vec[i] += 2
                return True
            vec[i] += 2
    return False


def _tile_to_idx(t: Tile) -> int:
    """Tile → vec34 下标。"""
    if t.suit == Suit.HONOR:
        return 27 + (t.rank - 1)
    return t.suit.value * 9 + (t.rank - 1)


def _to_vec34(tiles: Counter[Tile]) -> list[int]:
    """Counter[Tile] → vec34。"""
    vec = [0] * 34
    for t, n in tiles.items():
        vec[_tile_to_idx(t)] = n
    return vec


def _can_decompose_12(tiles: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """检查门内牌 + 已有副露能否分解为 4 组面子（刻子/顺子）。"""
    mentsu_needed = 4 - len(melds)
    return _can_fill_mentsu(_to_vec34(tiles), mentsu_needed)


def _can_fill_mentsu(vec: list[int], needed: int) -> bool:
    """递归检查 vec 中的牌能否恰好组成 needed 组面子。"""
    if needed == 0:
        return all(v == 0 for v in vec)
    # 找第一个非零位置
    for i in range(34):
        if vec[i] > 0:
            # 尝试刻子
            if vec[i] >= 3:
                vec[i] -= 3
                if _can_fill_mentsu(vec, needed - 1):
                    vec[i] += 3
                    return True
                vec[i] += 3
            # 尝试顺子（仅数牌，rank <= 7）
            if i < 27 and i % 9 <= 6 and vec[i + 1] > 0 and vec[i + 2] > 0:
                vec[i] -= 1
                vec[i + 1] -= 1
                vec[i + 2] -= 1
                if _can_fill_mentsu(vec, needed - 1):
                    vec[i] += 1
                    vec[i + 1] += 1
                    vec[i + 2] += 1
                    return True
                vec[i] += 1
                vec[i + 1] += 1
                vec[i + 2] += 1
            return False
    return False


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

    # 听牌类型加符（非平和时）
    wait_fu = _wait_type_fu(concealed, melds, win_tile, for_ron=for_ron)
    result["wait"] = wait_fu

    # 总计（切上到 10 的倍数）
    total = (
        result["base"] + result["tsumo"] + result["pair"] + result["sets"]
        + result["menzen_ron"] + result["wait"]
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


def _is_chiitoitsu_14(concealed: Counter[Tile], win_tile: Tile) -> bool:
    """检测七对子：14 张门内牌恰好 7 种各 2 张。"""
    full = Counter(concealed)
    full[win_tile] += 1
    if sum(full.values()) != 14:
        return False
    return all(n == 2 for n in full.values())


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
    自动判定是否平和或七对子。
    """
    menzen = len(melds) == 0
    if menzen and _is_chiitoitsu_14(concealed, win_tile):
        return 25

    from kernel.win_shape.pinfu import pinfu_eligible

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
