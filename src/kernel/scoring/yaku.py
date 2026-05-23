"""役与翻数（扩展子集）；ドラ番数由调用方叠加。"""

from __future__ import annotations

from collections import Counter

from kernel.config import get_default_config, MahjongConfig
from kernel.board import BoardState
from kernel.hand.melds import Meld, MeldKind, triplet_key
from kernel.table.model import PrevailingWind, TableSnapshot, seat_wind_rank
from kernel.tiles.model import Suit, Tile
from kernel.tiles.key import logical_counter, tile_key  # H-15: 赤五归一化
from kernel.win_shape.decompose import menzen_peikou_level
from kernel.win_shape.pinfu import pinfu_eligible


def _full_tile_counter(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> Counter[Tile]:
    c = concealed.copy()
    if for_ron:
        c[win_tile] += 1
    for m in melds:
        for t in m.tiles:
            c[t] += 1
    return c


def prevailing_wind_tile(pw: PrevailingWind) -> Tile:
    """将 PrevailingWind 枚举转换为对应的牌张。"""
    if pw == PrevailingWind.EAST:
        return Tile(Suit.HONOR, 1)
    return Tile(Suit.HONOR, 2)


def _is_menzen(melds: tuple[Meld, ...]) -> bool:
    """门前清判定：无副露或仅有暗杠时为门前清。"""
    for m in melds:
        if m.kind != MeldKind.ANKAN:
            return False
    return True


def _is_tanyao(full: Counter[Tile], *, allow_open: bool, has_melds: bool) -> bool:
    if has_melds and not allow_open:
        return False
    for t, n in full.items():
        for _ in range(n):
            if t.suit == Suit.HONOR:
                return False
            if t.rank in (1, 9):
                return False
    return True


def _triplet_key_counts(full: Counter[Tile]) -> Counter[tuple[Suit, int]]:
    out: Counter[tuple[Suit, int]] = Counter()
    for t, n in full.items():
        out[triplet_key(t)] += n
    return out


def _yakuhai_han_triplets(
    keys: Counter[tuple[Suit, int]],
    *,
    round_wind_tile: Tile,
    seat_wind_tile: Tile,
) -> int:
    h = 0
    if keys[triplet_key(round_wind_tile)] >= 3:
        h += 1
    if keys[triplet_key(seat_wind_tile)] >= 3:
        h += 1
    for rank in (5, 6, 7):
        if keys[(Suit.HONOR, rank)] >= 3:
            h += 1
    return h


def _is_chiitoitsu(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """七对子：14 张门内牌恰好 7 种各 2 张（赤五归一化）。"""
    if melds:
        return False
    logical = logical_counter(full)  # H-15: 赤五归一化
    if sum(logical.values()) != 14:
        return False
    if len(logical) != 7:
        return False
    return all(n == 2 for n in logical.values())


def _is_all_terminals_and_honors(full: Counter[Tile]) -> bool:
    """是否全为幺九牌和字牌（混老头、清老头用）。"""
    for t, n in full.items():
        if t.suit not in (Suit.HONOR,):
            if t.rank not in (1, 9):
                return False
    return True


def _count_suits(full: Counter[Tile]) -> dict[Suit, int]:
    """统计各花色的牌数。"""
    counts: dict[Suit, int] = {Suit.MAN: 0, Suit.PIN: 0, Suit.SOU: 0, Suit.HONOR: 0}
    for t, n in full.items():
        counts[t.suit] += n
    return counts


def _is_chinitsu_full(full: Counter[Tile]) -> bool:
    """清一色：无字牌，万／筒／索恰有一种非零。"""
    s = _count_suits(full)
    if s[Suit.HONOR] != 0:
        return False
    return sum(1 for su in (Suit.MAN, Suit.PIN, Suit.SOU) if s[su] > 0) == 1


def _is_honitsu_full(full: Counter[Tile]) -> bool:
    """混一色：有字牌，万／筒／索恰有一种非零。"""
    s = _count_suits(full)
    if s[Suit.HONOR] == 0:
        return False
    return sum(1 for su in (Suit.MAN, Suit.PIN, Suit.SOU) if s[su] > 0) == 1


def _is_sanshoku_doukou(full: Counter[Tile]) -> bool:
    """三色同刻：存在 rank 使万／筒／索上同 rank 刻（含杠）均 ≥3。"""
    keys = _triplet_key_counts(full)
    for r in range(1, 10):
        if keys[(Suit.MAN, r)] >= 3 and keys[(Suit.PIN, r)] >= 3 and keys[(Suit.SOU, r)] >= 3:
            return True
    return False


def _count_kan_melds(melds: tuple[Meld, ...]) -> int:
    """副露中大明杠／暗杠／加杠的组数。"""
    return sum(
        1 for m in melds if m.kind in (MeldKind.DAIMINKAN, MeldKind.ANKAN, MeldKind.KAKAN)
    )


def _has_ryanmen_chiito(melds: tuple[Meld, ...]) -> bool:
    """是否有顺子（两面子）。"""
    for m in melds:
        if m.kind == MeldKind.CHI:
            return True
    return False


def _count_chi_sequences(full: Counter[Tile], melds: tuple[Meld, ...]) -> dict[Suit, int]:
    """统计各花色顺子数量（仅副露）。"""
    counts: dict[Suit, int] = {Suit.MAN: 0, Suit.PIN: 0, Suit.SOU: 0}
    for m in melds:
        if m.kind == MeldKind.CHI:
            suit = m.tiles[0].suit
            if suit in counts:
                counts[suit] += 1
    return counts


def _has_same_suit_sequences(melds: tuple[Meld, ...], target: int) -> tuple[bool, Suit]:
    """是否有 target 个同花色顺子。返回 (是否满足，花色)。"""
    suit_counts: dict[Suit, int] = {Suit.MAN: 0, Suit.PIN: 0, Suit.SOU: 0}
    for m in melds:
        if m.kind == MeldKind.CHI:
            suit = m.tiles[0].suit
            if suit in suit_counts:
                suit_counts[suit] += 1
    for suit, count in suit_counts.items():
        if count >= target:
            return (True, suit)
    return (False, Suit.HONOR)


def _tile_is_yaochuu(t: Tile) -> bool:
    """幺九或字牌（混全/纯全带幺用）。"""
    return t.suit == Suit.HONOR or t.rank in (1, 9)


def _remaining_after_open_melds(full: Counter[Tile], melds: tuple[Meld, ...]) -> Counter[Tile]:
    """从和了全体牌数减去副露张数，得到门内（含荣和牌）。"""
    rem = Counter(full)
    for m in melds:
        for t in m.tiles:
            rem[t] -= 1
            if rem[t] <= 0:
                del rem[t]
    return rem


def _is_chanta(
    full: Counter[Tile],
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
    with_jun: bool,
) -> bool:
    """
    混全带幺/纯全带幺：所有面子和雀头均须「带幺」（含门内分解）。
    with_jun=True: 纯全（手牌无字牌）；False: 混全（允许字牌）。
    """
    from kernel.win_shape.decompose import (
        enumerate_concealed_decompositions,
        index_to_suit_rank,
    )

    if with_jun and any(t.suit == Suit.HONOR for t in full.keys()):
        return False

    # 副露检查
    for m in melds:
        if m.kind == MeldKind.CHI:
            ranks = [t.rank for t in m.tiles]
            if 1 not in ranks and 9 not in ranks:
                return False
        else:
            if not all(_tile_is_yaochuu(t) for t in m.tiles):
                return False

    # 门内分解检查
    decomps = enumerate_concealed_decompositions(
        concealed, melds, win_tile, for_ron=for_ron,
    )
    if not decomps:
        return False

    for decomp in decomps:
        all_ok = True
        for kind, idx in decomp:
            suit_val, rank = index_to_suit_rank(idx)
            if kind == "chi":
                # 顺子起始 rank 为 1 → 123（带幺），7 → 789（带幺），其他不带幺
                if rank not in (1, 7):
                    all_ok = False
                    break
            else:  # pon
                # 刻子/雀头的牌须为幺九牌
                if suit_val < 3:
                    tile = Tile([Suit.MAN, Suit.PIN, Suit.SOU][suit_val], rank)
                else:
                    tile = Tile(Suit.HONOR, rank)
                if not _tile_is_yaochuu(tile):
                    all_ok = False
                    break
        if all_ok:
            return True
    return False


def _count_ananko(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile | None = None,
    for_ron: bool = False,
) -> int:
    """
    暗刻数量（门内刻子，不含副露，赤五归一化）。

    Args:
        concealed: 门内牌张计数
        melds: 副露（当前未使用）
        win_tile: 和牌（荣和时为被荣的牌，自摸时为自摸牌）
        for_ron: 是否荣和

    Returns:
        暗刻数量

    Note:
        荣和时 concealed 为 13 张（不含荣和牌），自摸时 concealed 为 14 张（含自摸牌）。
        因此荣和补成刻子的牌在 concealed 中只有 2 张，不会被统计为暗刻。
        自摸补成刻子的牌在 concealed 中有 3 张，会被统计为暗刻。
        这个显式参数版本与隐式版本行为一致，但更清晰地表达了意图。
    """
    logical = logical_counter(concealed)  # H-15: 赤五归一化
    count = 0
    for key, n in logical.items():
        if n >= 3:
            count += 1
    return count


def _is_toitoi(
    melds: tuple[Meld, ...], concealed: Counter[Tile], win_tile: Tile, for_ron: bool
) -> bool:
    """对对和：四刻子 + 一对（赤五归一化）。"""
    full = concealed.copy()
    if for_ron:
        full[win_tile] += 1

    logical = logical_counter(full)  # H-15: 赤五归一化

    # 所有副露必须是刻子或杠子（非顺子）
    for m in melds:
        if m.kind == MeldKind.CHI:
            return False

    # 门内必须有恰好一个对子，其余为刻子
    pair_count = 0
    triplet_count = len(melds)  # 副露的刻子/杠子数

    for key, count in logical.items():
        if count == 2:
            pair_count += 1
        elif count == 3:
            triplet_count += 1
        elif count == 4:
            # 暗杠或暗刻 +1
            triplet_count += 1

    return pair_count == 1 and triplet_count == 4


def _is_sanshoku_same_rank(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> bool:
    """三色同顺：三种花色都有相同 rank 的顺子（含门内分解）。"""
    from kernel.win_shape.decompose import (
        enumerate_concealed_decompositions,
        index_to_suit_rank,
    )

    # 收集副露中的顺子
    chi_ranks: dict[int, set[Suit]] = {}
    for m in melds:
        if m.kind == MeldKind.CHI:
            rank = m.tiles[0].rank
            suit = m.tiles[0].suit
            chi_ranks.setdefault(rank, set()).add(suit)

    # 枚举门内分解，合并检查
    decomps = enumerate_concealed_decompositions(
        concealed, melds, win_tile, for_ron=for_ron,
    )
    for decomp in decomps:
        merged: dict[int, set[Suit]] = {r: set(s) for r, s in chi_ranks.items()}
        for kind, idx in decomp:
            if kind == "chi":
                suit_val, rank = index_to_suit_rank(idx)
                suit = [Suit.MAN, Suit.PIN, Suit.SOU][suit_val]
                merged.setdefault(rank, set()).add(suit)
        for suits in merged.values():
            if len(suits) == 3:
                return True
    return False


def _is_ikkitsukan(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> bool:
    """一气通贯：同花色 123+456+789 三个顺子（含门内分解）。"""
    from kernel.win_shape.decompose import (
        enumerate_concealed_decompositions,
        index_to_suit_rank,
    )

    # 收集副露顺子
    suit_sequences: dict[Suit, set[int]] = {}
    for m in melds:
        if m.kind == MeldKind.CHI:
            suit = m.tiles[0].suit
            rank = m.tiles[0].rank
            suit_sequences.setdefault(suit, set()).add(rank)

    # 枚举门内分解
    decomps = enumerate_concealed_decompositions(
        concealed, melds, win_tile, for_ron=for_ron,
    )
    for decomp in decomps:
        merged: dict[Suit, set[int]] = {s: set(r) for s, r in suit_sequences.items()}
        for kind, idx in decomp:
            if kind == "chi":
                suit_val, rank = index_to_suit_rank(idx)
                suit = [Suit.MAN, Suit.PIN, Suit.SOU][suit_val]
                merged.setdefault(suit, set()).add(rank)
        for ranks in merged.values():
            if {1, 4, 7}.issubset(ranks):
                return True
    return False


def _count_yakuhai_triplets(
    full: Counter[Tile],
    *,
    round_wind_tile: Tile,
    seat_wind_tile: Tile,
) -> int:
    """役牌刻子数量。"""
    count = 0
    keys = _triplet_key_counts(full)
    if keys[triplet_key(round_wind_tile)] >= 3:
        count += 1
    if keys[triplet_key(seat_wind_tile)] >= 3:
        count += 1
    for rank in (5, 6, 7):
        if keys[(Suit.HONOR, rank)] >= 3:
            count += 1
    return count


def _is_daisangen(full: Counter[Tile]) -> bool:
    """
    大三元：三元牌（白・发・中）三组刻子。
    役满。
    """
    keys = _triplet_key_counts(full)
    for rank in (5, 6, 7):
        if keys[(Suit.HONOR, rank)] < 3:
            return False
    return True


def _is_suuankou(
    concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile, for_ron: bool
) -> bool:
    """
    四暗刻：门前清四组暗刻 + 对子（赤五归一化）。
    荣和时不算四暗刻（荣和破坏门清）。
    单骑等待由 ``_is_suuankou_tanki`` 单独处理。
    役满。
    """
    if melds:
        return False  # 有副露则不是四暗刻
    if for_ron:
        return False  # 荣和破坏门清，四暗刻仅由 _is_suuankou_tanki 处理

    anko_count = 0
    pair_count = 0

    full = concealed.copy()
    if for_ron:
        full[win_tile] += 1

    logical = logical_counter(full)  # H-15: 赤五归一化

    for key, count in logical.items():
        if count == 3:
            anko_count += 1
        elif count == 4:
            anko_count += 1  # 暗杠也算暗刻
        elif count == 2:
            pair_count += 1

    if anko_count == 4 and pair_count == 1:
        return True
    return False


def _is_suuankou_tanki(
    concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile, for_ron: bool
) -> bool:
    """
    四暗刻单骑：门前清四暗刻 + 单骑待牌（赤五归一化）。
    役满。
    仅荣和时成立（自摸时是普通四暗刻）。
    """
    if melds:
        return False
    if not for_ron:
        return False  # 自摸时不是单骑

    # 荣和时：手牌 3 刻子 +2 对子，荣和的牌使其中一对变成刻子
    logical = logical_counter(concealed)  # H-15: 赤五归一化
    anko_count = 0
    pair_count = 0
    for key, count in logical.items():
        if count == 3:
            anko_count += 1
        elif count == 4:
            anko_count += 1
        elif count == 2:
            pair_count += 1

    # 荣和牌需要检查逻辑牌种（赤五与普通五等价）
    win_key = tile_key(win_tile)
    if anko_count == 3 and pair_count == 2 and logical.get(win_key, 0) == 2:
        return True
    return False


def is_kokushi_musou(concealed: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    国士无理（十三幺）：十三种幺九牌各至少一枚 + 一对。
    门前清限定。
    役满。
    """
    if melds:
        return False  # 有副露则不是国士

    # 十三种幺九牌
    terminals = [
        Tile(Suit.MAN, 1),
        Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 1),
        Tile(Suit.PIN, 9),
        Tile(Suit.SOU, 1),
        Tile(Suit.SOU, 9),
        Tile(Suit.HONOR, 1),
        Tile(Suit.HONOR, 2),
        Tile(Suit.HONOR, 3),
        Tile(Suit.HONOR, 4),
        Tile(Suit.HONOR, 5),
        Tile(Suit.HONOR, 6),
        Tile(Suit.HONOR, 7),
    ]

    # 必须有恰好 14 张牌
    if sum(concealed.values()) != 14:
        return False

    # 必须有恰好 13 种幺九牌
    if len(concealed) != 13:
        return False

    # 检查是否包含所有十三种幺九牌
    for t in terminals:
        if concealed[t] < 1:
            return False

    # 检查是否有一对（某一种幺九牌有 2 张）
    pair_count = sum(1 for count in concealed.values() if count == 2)
    return pair_count == 1


def is_kokushi_thirteen_waits(
    concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile
) -> bool:
    """
    国士无理十三面：十三面待牌的国士。
    役满。
    """
    if melds:
        return False

    # 十三面待牌：手牌 13 种幺九牌各 1 张，待第 14 张成对
    if sum(concealed.values()) != 13:
        return False

    if len(concealed) != 13:
        return False

    # 检查是否所有牌都是幺九牌且各 1 张
    for count in concealed.values():
        if count != 1:
            return False

    # 检查是否包含所有十三种幺九牌
    terminals = [
        Tile(Suit.MAN, 1),
        Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 1),
        Tile(Suit.PIN, 9),
        Tile(Suit.SOU, 1),
        Tile(Suit.SOU, 9),
        Tile(Suit.HONOR, 1),
        Tile(Suit.HONOR, 2),
        Tile(Suit.HONOR, 3),
        Tile(Suit.HONOR, 4),
        Tile(Suit.HONOR, 5),
        Tile(Suit.HONOR, 6),
        Tile(Suit.HONOR, 7),
    ]
    for t in terminals:
        if concealed[t] != 1:
            return False

    # 荣和的牌必须是十三种幺九牌之一
    return win_tile in terminals


def hand_pattern_label(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> str:
    """返回和了形分类：「国士无双」/「七对子」/「一般形」。"""
    from kernel.call.win import can_ron_seven_pairs, can_win_seven_pairs_concealed_14

    if for_ron:
        if can_ron_seven_pairs(concealed, melds, win_tile):
            return "七对子"
    elif can_win_seven_pairs_concealed_14(concealed, melds):
        return "七对子"
    # H-29: 国士判断修复
    kokushi_hand = concealed.copy()
    if for_ron:
        kokushi_hand[win_tile] += 1
    if for_ron:
        if is_kokushi_thirteen_waits(concealed, melds, win_tile) or is_kokushi_musou(kokushi_hand, melds):
            return "国士无双"
    else:
        kokushi_before = concealed.copy()
        kokushi_before[win_tile] -= 1
        if is_kokushi_thirteen_waits(kokushi_before, melds, win_tile) or is_kokushi_musou(concealed, melds):
            return "国士无双"
    return "一般形"


def _is_chinroutou(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    清老头：仅 19 数牌（四组刻子/杠子 + 对子）。
    役满。
    """
    if melds:
        # 有副露时，检查副露是否都是 19 数牌
        for m in melds:
            for t in m.tiles:
                if t.suit == Suit.HONOR:
                    return False
                if t.rank not in (1, 9):
                    return False

    # 检查所有牌是否都是 19 数牌
    for t, count in full.items():
        if t.suit == Suit.HONOR:
            return False
        if t.rank not in (1, 9):
            return False

    # 必须有恰好 7 种牌（4 种刻子 +1 种对子，或对对和形）
    # 清老头只能是对对和形（因为顺子需要中间牌）
    return True


def _is_tsuuiisou(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    字一色：仅字牌。
    役满。
    """
    if melds:
        # 有副露时，检查副露是否都是字牌
        for m in melds:
            for t in m.tiles:
                if t.suit != Suit.HONOR:
                    return False

    # 检查所有牌是否都是字牌
    for t in full.keys():
        if t.suit != Suit.HONOR:
            return False
    return True


def _is_ryuuiisou(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    绿一色：仅 23468 索 + 发。
    役满。
    """
    # 绿一色允许的牌
    allowed_tiles = {
        Tile(Suit.SOU, 2),
        Tile(Suit.SOU, 3),
        Tile(Suit.SOU, 4),
        Tile(Suit.SOU, 6),
        Tile(Suit.SOU, 8),
        Tile(Suit.HONOR, 6),  # 发
    }

    if melds:
        # 有副露时，检查副露是否都是绿一色牌
        for m in melds:
            for t in m.tiles:
                if t not in allowed_tiles:
                    return False

    # 检查所有牌是否都是绿一色牌
    for t in full.keys():
        if t not in allowed_tiles:
            return False
    return True


def _is_chuuren_poutou(concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile) -> bool:
    """
    九莲宝灯：同花色 1112345678999 + 任意同花色牌（赤五归一化）。
    门前清限定。
    役满。
    """
    if melds:
        return False

    logical = logical_counter(concealed)  # H-15: 赤五归一化
    if sum(logical.values()) != 14:
        return False

    # 找出唯一的非字牌花色
    suits = {key[0] for key in logical.keys() if key[0] != Suit.HONOR}
    if len(suits) != 1:
        return False

    suit = list(suits)[0]

    # 九莲宝灯基础形：1112345678999
    base_pattern = {1: 3, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 3}

    # 检查是否符合九莲宝灯形
    # 允许任意一张牌多一张（形成 14 张）
    ranks_present = {key[1] for key in logical.keys() if key[0] == suit}
    if not {1, 2, 3, 4, 5, 6, 7, 8, 9}.issubset(ranks_present):
        return False

    # 检查是否符合 1112345678999 + 1 张的形式
    total = 0
    for rank in range(1, 10):
        key = (suit, rank)
        count = logical.get(key, 0)
        if count < base_pattern[rank]:
            return False
        total += count

    if total != 14:
        return False

    # 检查额外牌是否在 1-9 范围内（已经是同花色）
    extra_count = sum(logical.values()) - 13
    return extra_count == 1


def _is_junsei_chuuren_poutou(
    concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile
) -> bool:
    """
    纯正九莲宝灯：九面待牌的九莲宝灯（赤五归一化）。
    役满。
    条件：手牌 1112345678999 待任意同花色牌（1-9 任意）。
    """
    if melds:
        return False

    logical = logical_counter(concealed)  # H-15: 赤五归一化
    # 手牌必须是 13 张
    if sum(logical.values()) != 13:
        return False

    # 找出唯一的非字牌花色
    suits = {key[0] for key in logical.keys() if key[0] != Suit.HONOR}
    if len(suits) != 1:
        return False

    suit = list(suits)[0]

    # 纯正九莲：1112345678999（13 张）
    base_pattern = {1: 3, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 3}

    # 检查手牌是否完全符合基础形
    for rank in range(1, 10):
        key = (suit, rank)
        if logical.get(key, 0) != base_pattern[rank]:
            return False

    return True


def _is_suu_kantsu(melds: tuple[Meld, ...]) -> bool:
    """
    四杠子：四组杠子。
    役满。
    """
    kan_count = sum(
        1 for m in melds if m.kind in (MeldKind.DAIMINKAN, MeldKind.ANKAN, MeldKind.KAKAN)
    )
    return kan_count == 4


def _is_daisuushii(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    大四喜：四风四组刻子。
    役满。
    """
    # ``full`` 已含副露与和了牌，直接数四风刻子即可。
    keys = _triplet_key_counts(full)
    wind_kan_count = 0
    for rank in (1, 2, 3, 4):
        if keys[(Suit.HONOR, rank)] >= 3:
            wind_kan_count += 1

    return wind_kan_count == 4


def _is_shou_suushii(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    小四喜：四风三组刻子 + 一对风牌。
    役满。
    """
    keys = _triplet_key_counts(full)

    # 统计四风刻子数量
    wind_triplet_count = 0
    for rank in (1, 2, 3, 4):
        if keys[(Suit.HONOR, rank)] >= 3:
            wind_triplet_count += 1

    # 统计四风对子数量（除去已算作刻子的）
    wind_pair_count = 0
    for rank in (1, 2, 3, 4):
        count = keys[(Suit.HONOR, rank)]
        if count == 2:
            wind_pair_count += 1

    return wind_triplet_count == 3 and wind_pair_count >= 1


def _is_tenhou(board: BoardState, winner: int, is_tsumo: bool, dealer_seat: int = 0) -> bool:
    """
    天和：亲家第一巡自摸。
    役满。
    """
    if not is_tsumo:
        return False
    if winner != dealer_seat:
        return False
    if board.current_seat != dealer_seat:
        return False
    # H-14: 第一巡 = 无舍牌 + 无鸣牌
    if len(board.river) != 0:
        return False
    return all(len(m) == 0 for m in board.melds)


def _is_chihou(board: BoardState, winner: int, is_tsumo: bool, dealer_seat: int = 0) -> bool:
    """
    地和：子家第一巡自摸。
    役满。
    """
    if not is_tsumo:
        return False
    if board.current_seat == dealer_seat:  # 亲家不算地和
        return False
    # H-14: 第一巡 = 当前玩家无舍牌 + 无鸣牌
    if len(board.all_discards_per_seat[winner]) != 0:
        return False
    return all(len(m) == 0 for m in board.melds)


def _yakuhai_labels_for_triplets(
    keys: Counter[tuple[Suit, int]],
    *,
    round_wind_tile: Tile,
    seat_wind_tile: Tile,
) -> list[str]:
    t_r = triplet_key(round_wind_tile)
    t_s = triplet_key(seat_wind_tile)
    out: list[str] = []
    if t_r == t_s:
        if keys[t_r] >= 3:
            out.append("连风刻")
    else:
        if keys[t_r] >= 3:
            out.append("场风刻")
        if keys[t_s] >= 3:
            out.append("自风刻")
    for rank, name in ((5, "白"), (6, "发"), (7, "中")):
        if keys[(Suit.HONOR, rank)] >= 3:
            out.append(f"{name}刻")
    return out


def non_dora_yaku_han_and_labels(
    board: BoardState,
    table: TableSnapshot,
    winner: int,
    *,
    for_ron: bool,
    win_tile: Tile,
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    allow_open_tanyao: bool = True,
    last_draw_was_rinshan: bool = False,
    is_haitei: bool = False,
    is_hotei: bool = False,
    is_chankan: bool = False,
    is_tsumo: bool = False,
    config: MahjongConfig | None = None,
) -> tuple[int, tuple[str, ...]]:
    """
    与 ``count_yaku_han`` 相同的非ドラ役番累计，并返回简体役名列表（供事件日志）。

    一般形路径中染手／一杯口系／三色同刻／三杠子 等与 ``count_yaku_han`` 文档一致。
    """
    config = config or get_default_config()
    full = _full_tile_counter(concealed, melds, win_tile, for_ron=for_ron)
    labels: list[str] = []

    if _is_daisangen(full):
        return 13, ("大三元",)
    if _is_suuankou_tanki(concealed, melds, win_tile, for_ron=for_ron):
        return 13, ("四暗刻单骑",)
    if _is_suuankou(concealed, melds, win_tile, for_ron=for_ron):
        return 13, ("四暗刻",)
    # H-29: 国士无双计分修复 - 正确处理 RON/TSUMO 的 concealed 张数差异
    kokushi_hand = concealed.copy()
    if for_ron:
        kokushi_hand[win_tile] += 1  # RON: concealed=13张，需加 win_tile 构造14张
    if for_ron:
        # RON: concealed 是 13 张
        # 十三面判断：用原始 13 张检查是否为十三面听牌
        if is_kokushi_thirteen_waits(concealed, melds, win_tile):
            return 13, ("国士无双十三面",)
        # 普通国士：用构造的 14 张检查完成形
        if is_kokushi_musou(kokushi_hand, melds):
            return 13, ("国士无双",)
    else:
        # TSUMO: concealed 是 14 张
        # 十三面判断：移除自摸牌得到 13 张，检查是否为十三面听牌
        kokushi_before = concealed.copy()
        kokushi_before[win_tile] -= 1
        if is_kokushi_thirteen_waits(kokushi_before, melds, win_tile):
            return 13, ("国士无双十三面",)
        # 普通国士：用原始 14 张检查完成形
        if is_kokushi_musou(concealed, melds):
            return 13, ("国士无双",)
    if _is_chinroutou(full, melds):
        return 13, ("清老头",)
    if _is_tsuuiisou(full, melds):
        return 13, ("字一色",)
    if _is_ryuuiisou(full, melds):
        return 13, ("绿一色",)
    if _is_junsei_chuuren_poutou(concealed, melds, win_tile):
        return 13, ("纯正九莲宝灯",)
    if _is_chuuren_poutou(concealed, melds, win_tile):
        return 13, ("九莲宝灯",)
    if _is_suu_kantsu(melds):
        return 13, ("四杠子",)
    if _is_daisuushii(full, melds):
        return 13, ("大四喜",)
    if _is_shou_suushii(full, melds):
        return 13, ("小四喜",)
    if _is_tenhou(board, winner, is_tsumo=is_tsumo, dealer_seat=table.dealer_seat):
        return 13, ("天和",)
    if _is_chihou(board, winner, is_tsumo=is_tsumo, dealer_seat=table.dealer_seat):
        return 13, ("地和",)

    han = 0
    if winner in board.double_riichi:
        han += 2
        labels.append("双立直")
    elif board.riichi[winner]:
        han += 1
        labels.append("立直")
    if config.ippatsu_enabled and winner in board.ippatsu_eligible:
        han += 1
        labels.append("一发")

    rw = prevailing_wind_tile(table.prevailing_wind)
    sw = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, winner))

    if _is_chiitoitsu(full, melds):
        han += 2
        labels.append("七对子")
        menzen_c7 = _is_menzen(melds)
        if _is_chinitsu_full(full):
            han += 6 if menzen_c7 else 5
            labels.append("清一色(门清)" if menzen_c7 else "清一色")
        elif _is_honitsu_full(full):
            han += 3 if menzen_c7 else 2
            labels.append("混一色(门清)" if menzen_c7 else "混一色")
        if _is_tanyao(full, allow_open=allow_open_tanyao, has_melds=False):
            han += 1
            labels.append("断幺九")
        # 门前清自摸和：门清自摸时加 1 番（役满不叠加）
        if menzen_c7 and is_tsumo:
            han += 1
            labels.append("门前清自摸和")
        return han, tuple(labels)

    menzen = _is_menzen(melds)
    if _is_chinitsu_full(full):
        han += 6 if menzen else 5
        labels.append("清一色(门清)" if menzen else "清一色")
    elif _is_honitsu_full(full):
        han += 3 if menzen else 2
        labels.append("混一色(门清)" if menzen else "混一色")

    pl = menzen_peikou_level(concealed, melds, win_tile, for_ron=for_ron)
    if pl == 2:
        han += 3
        labels.append("二杯口")
    elif pl == 1:
        han += 1
        labels.append("一杯口")

    if _is_sanshoku_doukou(full):
        han += 2
        labels.append("三色同刻")

    if _count_kan_melds(melds) == 3:
        han += 2
        labels.append("三杠子")

    if last_draw_was_rinshan:
        han += 1
        labels.append("岭上开花")
    if is_haitei:
        han += 1
        labels.append("海底捞月")
    elif is_hotei:
        han += 1
        labels.append("河底捞鱼")
    if is_chankan:
        han += 1
        labels.append("抢杠")
    if _is_tanyao(full, allow_open=allow_open_tanyao, has_melds=len(melds) > 0):
        han += 1
        labels.append("断幺九")

    yh = _yakuhai_han_triplets(
        _triplet_key_counts(full),
        round_wind_tile=rw,
        seat_wind_tile=sw,
    )
    if yh:
        han += yh
        labels.extend(
            _yakuhai_labels_for_triplets(
                _triplet_key_counts(full), round_wind_tile=rw, seat_wind_tile=sw
            )
        )

    if pinfu_eligible(
        concealed,
        melds,
        win_tile,
        for_ron=for_ron,
        round_wind_tile=rw,
        seat_wind_tile=sw,
    ):
        han += 1
        labels.append("平和")

    if _is_toitoi(melds, concealed, win_tile, for_ron=for_ron):
        han += 2
        labels.append("对对和")

    if _is_sanshoku_same_rank(concealed, melds, win_tile, for_ron=for_ron):
        menzen = _is_menzen(melds)
        han += 3 if menzen else 2
        labels.append("三色同顺(门清)" if menzen else "三色同顺")

    if _is_ikkitsukan(concealed, melds, win_tile, for_ron=for_ron):
        menzen = _is_menzen(melds)
        han += 3 if menzen else 2
        labels.append("一气通贯(门清)" if menzen else "一气通贯")

    if _is_chanta(full, concealed, melds, win_tile, for_ron=for_ron, with_jun=True):
        menzen = _is_menzen(melds)
        han += 4 if menzen else 3
        labels.append("纯全带幺九(门清)" if menzen else "纯全带幺九")
    elif _is_chanta(full, concealed, melds, win_tile, for_ron=for_ron, with_jun=False):
        menzen = _is_menzen(melds)
        han += 2 if menzen else 1
        labels.append("混全带幺九(门清)" if menzen else "混全带幺九")

    if _is_all_terminals_and_honors(full):
        if not _is_chiitoitsu(full, melds):
            han += 2
            labels.append("混老头")

    ananko_count = _count_ananko(concealed, melds, win_tile=win_tile, for_ron=for_ron)
    if ananko_count >= 3:
        han += 2
        labels.append("三暗刻")

    triplet_keys = _triplet_key_counts(full)
    dragon_triplets = sum(1 for rank in (5, 6, 7) if triplet_keys[(Suit.HONOR, rank)] >= 3)
    dragon_pairs = sum(1 for rank in (5, 6, 7) if 2 <= triplet_keys[(Suit.HONOR, rank)] < 3)
    # 门前清自摸和：门清自摸时加 1 番（役满不叠加）
    if menzen and is_tsumo and han < 13:
        han += 1
        labels.append("门前清自摸和")
    if dragon_triplets == 2 and dragon_pairs >= 1:
        han += 2
        labels.append("小三元")

    return han, tuple(labels)


def count_yaku_han(
    board: BoardState,
    table: TableSnapshot,
    winner: int,
    *,
    for_ron: bool,
    win_tile: Tile,
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    allow_open_tanyao: bool = True,
    last_draw_was_rinshan: bool = False,
    is_haitei: bool = False,
    is_hotei: bool = False,
    is_chankan: bool = False,
    is_tsumo: bool = False,
    config: MahjongConfig | None = None,
) -> int:
    """
    役与翻数（扩展子集）：
    - 立直/双立直/一发
    - 断幺九
    - 役牌（场风、自风、三元牌）
    - 七对子
    - 平和
    - 岭上开花（1 番）
    - 海底捞月/河底捞鱼（1 番）
    - 抢杠（1 番）
    - 对对和（2 番）
    - 三色同顺（2 番副露/3 番门清）
    - 一气通贯（2 番副露/3 番门清）
    - 混全带幺（1 番副露/2 番门清）
    - 纯全带幺（3 番副露/4 番门清）
    - 混老头（2 番）
    - 三暗刻（2 番）
    - 小三元（2 番）
    - 清一色（6 门清 / 5 副露）、混一色（3 / 2）
    - 一杯口（1，门清一般形）、二杯口（3，门清）
    - 三色同刻（2）、三杠子（2；四杠子为役满早退）
    - 役满：大三元、四暗刻、国士无理、清老头、字一色、绿一色、九莲宝灯、四杠子、大小四喜、天和/地和

    不含ドラ、不含本场。
    """
    config = config or get_default_config()
    return non_dora_yaku_han_and_labels(
        board,
        table,
        winner,
        for_ron=for_ron,
        win_tile=win_tile,
        concealed=concealed,
        melds=melds,
        allow_open_tanyao=allow_open_tanyao,
        last_draw_was_rinshan=last_draw_was_rinshan,
        is_haitei=is_haitei,
        is_hotei=is_hotei,
        is_chankan=is_chankan,
        is_tsumo=is_tsumo,
        config=config,
    )[0]
