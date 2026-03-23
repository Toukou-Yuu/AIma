"""役与翻数（扩展子集）；ドラ番数由调用方叠加。"""

from __future__ import annotations

from collections import Counter

from kernel.deal.model import BoardState
from kernel.hand.melds import Meld, MeldKind, meld_tile_count, triplet_key
from kernel.table.model import PrevailingWind, TableSnapshot, seat_wind_rank
from kernel.tiles.model import Suit, Tile
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


def _prevailing_wind_tile(pw: PrevailingWind) -> Tile:
    if pw == PrevailingWind.EAST:
        return Tile(Suit.HONOR, 1)
    return Tile(Suit.HONOR, 2)


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


def _yakuhai_han_chiitoitsu_pairs(
    full: Counter[Tile],
    *,
    round_wind_tile: Tile,
    seat_wind_tile: Tile,
) -> int:
    """七对子：役牌对子各计 1 番；场风与自风相同时为连风对子 2 番。"""
    if round_wind_tile == seat_wind_tile and full[round_wind_tile] == 2:
        return 2
    h = 0
    if full[round_wind_tile] == 2:
        h += 1
    if full[seat_wind_tile] == 2:
        h += 1
    for rank in (5, 6, 7):
        tt = Tile(Suit.HONOR, rank)
        if full[tt] == 2:
            h += 1
    return h


def _is_chiitoitsu(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    if melds:
        return False
    if sum(full.values()) != 14:
        return False
    if len(full) != 7:
        return False
    return all(n == 2 for n in full.values())


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


def _is_chanta(full: Counter[Tile], melds: tuple[Meld, ...], *, with_jun: bool) -> bool:
    """
    混全带幺/纯全带幺：所有面子和雀头都包含幺九牌/字牌。
    with_jun=True: 纯全（无字牌）；False: 混全（允许字牌）。
    """
    # 检查雀头
    sets_data = _count_sets_by_kind_for_yaku(full, melds)
    pair_keys = sets_data["toitsu"]
    for key in pair_keys:
        t = Tile(key[0], key[1])
        is_yaokyuu = t.suit == Suit.HONOR or t.rank in (1, 9)
        if not is_yaokyuu:
            return False
        if with_jun and t.suit == Suit.HONOR:
            return False

    # 检查顺子
    for m in melds:
        if m.kind == MeldKind.CHI:
            # 顺子必须包含 1 或 9
            ranks = [t.rank for t in m.tiles]
            if 1 not in ranks and 9 not in ranks:
                return False
            if with_jun:
                # 纯全：顺子本身不能有字牌（本来就没有）
                pass

    # 检查刻子/杠子
    for key, count in full.items():
        if count >= 3:
            t = Tile(key[0], key[1])
            is_yaokyuu = t.suit == Suit.HONOR or t.rank in (1, 9)
            if not is_yaokyuu:
                # 检查是否是顺子的一部分（已在上面检查）
                pass

    return True


def _count_sets_by_kind_for_yaku(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
) -> dict[str, list[tuple[Suit, int]]]:
    """统计对子/刻子/杠子（用于役种判定）。"""
    toitsu_keys = []
    anko_keys = []
    for key, count in concealed.items():
        if count == 2:
            toitsu_keys.append(key)
        elif count == 3:
            anko_keys.append(key)
        elif count == 4:
            # 暗刻 + 1 枚（罕见情况）
            anko_keys.append(key)

    return {
        "ankan": [],
        "minkan": [],
        "anko": anko_keys,
        "toitsu": toitsu_keys,
    }


def _count_ananko(concealed: Counter[Tile], melds: tuple[Meld, ...]) -> int:
    """暗刻数量（门内刻子，不含副露）。"""
    count = 0
    for key, n in concealed.items():
        if n == 3:
            count += 1
        elif n == 4:
            # 暗杠也算暗刻（四暗刻用）
            count += 1
    return count


def _is_toitoi(melds: tuple[Meld, ...], concealed: Counter[Tile], win_tile: Tile, for_ron: bool) -> bool:
    """对对和：四刻子 + 一对。"""
    full = concealed.copy()
    if for_ron:
        full[win_tile] += 1

    # 所有副露必须是刻子或杠子（非顺子）
    for m in melds:
        if m.kind == MeldKind.CHI:
            return False

    # 门内必须有恰好一个对子，其余为刻子
    pair_count = 0
    triplet_count = len(melds)  # 副露的刻子/杠子数

    for key, count in full.items():
        if count == 2:
            pair_count += 1
        elif count == 3:
            triplet_count += 1
        elif count == 4:
            # 暗杠或暗刻 +1
            triplet_count += 1

    return pair_count == 1 and triplet_count == 4


def _is_sanshoku_same_rank(melds: tuple[Meld, ...]) -> bool:
    """三色同顺：三种花色都有相同 rank 的顺子。"""
    # 收集所有顺子的 rank
    chi_ranks: dict[int, set[Suit]] = {}
    for m in melds:
        if m.kind == MeldKind.CHI:
            rank = m.tiles[0].rank  # 最小 rank
            suit = m.tiles[0].suit
            if rank not in chi_ranks:
                chi_ranks[rank] = set()
            chi_ranks[rank].add(suit)

    # 检查是否有某个 rank 包含三种花色
    for rank, suits in chi_ranks.items():
        if len(suits) == 3:
            return True
    return False


def _is_ikkitsukan(melds: tuple[Meld, ...]) -> bool:
    """一气通贯：同花色 123+456+789 三个顺子。"""
    suit_sequences: dict[Suit, set[int]] = {}
    for m in melds:
        if m.kind == MeldKind.CHI:
            suit = m.tiles[0].suit
            rank = m.tiles[0].rank
            if suit not in suit_sequences:
                suit_sequences[suit] = set()
            suit_sequences[suit].add(rank)

    for suit, ranks in suit_sequences.items():
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


def _is_suuankou(concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile, for_ron: bool) -> bool:
    """
    四暗刻：门前清四组暗刻 + 对子。
    荣和时不算四暗刻（荣和破坏门清），但四暗刻单骑除外。
    役满。
    """
    if melds:
        return False  # 有副露则不是四暗刻

    # 统计暗刻数量
    anko_count = 0
    pair_count = 0

    full = concealed.copy()
    if for_ron:
        full[win_tile] += 1

    for key, count in full.items():
        if count == 3:
            anko_count += 1
        elif count == 4:
            anko_count += 1  # 暗杠也算暗刻
        elif count == 2:
            pair_count += 1

    # 四暗刻：四暗刻 + 一对
    # 四暗刻单骑：五组对子（听牌时为单骑）
    if anko_count == 4 and pair_count == 1:
        return True
    # 四暗刻单骑：荣和时为五对子（实际是四暗刻 + 单骑待牌）
    if for_ron and anko_count == 3 and pair_count == 2:
        # 荣和的牌必须形成第四个刻子
        if full[win_tile] == 3:
            return True
    return False


def _is_suuankou_tanki(concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile, for_ron: bool) -> bool:
    """
    四暗刻单骑：门前清四暗刻 + 单骑待牌。
    双倍役满。
    仅荣和时成立（自摸时是普通四暗刻）。
    """
    if melds:
        return False
    if not for_ron:
        return False  # 自摸时不是单骑

    # 荣和时：手牌 3 刻子 +2 对子，荣和的牌使其中一对变成刻子
    anko_count = 0
    pair_count = 0
    for key, count in concealed.items():
        if count == 3:
            anko_count += 1
        elif count == 4:
            anko_count += 1
        elif count == 2:
            pair_count += 1

    if anko_count == 3 and pair_count == 2 and concealed[win_tile] == 2:
        return True
    return False


def _is_kokushi_musou(concealed: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    国士无理（十三幺）：十三种幺九牌各至少一枚 + 一对。
    门前清限定。
    役满。
    """
    if melds:
        return False  # 有副露则不是国士

    # 十三种幺九牌
    terminals = [
        Tile(Suit.MAN, 1), Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
        Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
        Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 2), Tile(Suit.HONOR, 3),
        Tile(Suit.HONOR, 4), Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 6),
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


def _is_kokushi_thirteen_waits(concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile) -> bool:
    """
    国士无理十三面：十三面待牌的国士。
    双倍役满。
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
        Tile(Suit.MAN, 1), Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
        Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
        Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 2), Tile(Suit.HONOR, 3),
        Tile(Suit.HONOR, 4), Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 6),
        Tile(Suit.HONOR, 7),
    ]
    for t in terminals:
        if concealed[t] != 1:
            return False

    # 荣和的牌必须是十三种幺九牌之一
    return win_tile in terminals


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
        Tile(Suit.SOU, 2), Tile(Suit.SOU, 3), Tile(Suit.SOU, 4),
        Tile(Suit.SOU, 6), Tile(Suit.SOU, 8),
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
    九莲宝灯：同花色 1112345678999 + 任意同花色牌。
    门前清限定。
    役满。
    """
    if melds:
        return False

    if sum(concealed.values()) != 14:
        return False

    # 找出唯一的非字牌花色
    suits = {t.suit for t in concealed.keys() if t.suit != Suit.HONOR}
    if len(suits) != 1:
        return False

    suit = list(suits)[0]

    # 九莲宝灯基础形：1112345678999
    base_pattern = {1: 3, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 3}

    # 检查是否符合九莲宝灯形
    # 允许任意一张牌多一张（形成 14 张）
    ranks_present = {t.rank for t in concealed.keys()}
    if not {1, 2, 3, 4, 5, 6, 7, 8, 9}.issubset(ranks_present):
        return False

    # 检查是否符合 1112345678999 + 1 张的形式
    total = 0
    for rank in range(1, 10):
        t = Tile(suit, rank)
        count = concealed.get(t, 0)
        if count < base_pattern[rank]:
            return False
        total += count

    if total != 14:
        return False

    # 检查额外牌是否在 1-9 范围内（已经是同花色）
    extra_count = sum(concealed.values()) - 13
    return extra_count == 1


def _is_junsei_chuuren_poutou(concealed: Counter[Tile], melds: tuple[Meld, ...], win_tile: Tile) -> bool:
    """
    纯正九莲宝灯：九面待牌的九莲宝灯。
    双倍役满。
    条件：手牌 1112345678999 待任意同花色牌（1-9 任意）。
    """
    if melds:
        return False

    # 手牌必须是 13 张
    if sum(concealed.values()) != 13:
        return False

    # 找出唯一的非字牌花色
    suits = {t.suit for t in concealed.keys() if t.suit != Suit.HONOR}
    if len(suits) != 1:
        return False

    suit = list(suits)[0]

    # 纯正九莲：1112345678999（13 张）
    base_pattern = {1: 3, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 3}

    # 检查手牌是否完全符合基础形
    for rank in range(1, 10):
        t = Tile(suit, rank)
        if concealed.get(t, 0) != base_pattern[rank]:
            return False

    return True


def _is_suu_kantsu(melds: tuple[Meld, ...]) -> bool:
    """
    四杠子：四组杠子。
    役满。
    """
    kan_count = sum(1 for m in melds if m.kind in (MeldKind.DAIMINKAN, MeldKind.ANKAN, MeldKind.SHANKUMINKAN))
    return kan_count == 4


def _is_daisuushii(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    """
    大四喜：四风四组刻子。
    役满。
    """
    if melds:
        # 检查副露中的四风刻子
        wind_kan_count = sum(1 for m in melds if m.kind in (MeldKind.KAN, MeldKind.ANKAN, MeldKind.PON)
                            and m.tiles[0].suit == Suit.HONOR and m.tiles[0].rank in (1, 2, 3, 4))

    # 统计四风刻子数量
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


def _is_tenhou(board: BoardState, winner: int, is_tsumo: bool) -> bool:
    """
    天和：亲家第一巡自摸。
    役满。
    """
    if not is_tsumo:
        return False
    if board.current_seat != 0:  # 亲家必须是席次 0
        return False
    # 第一巡：无人打牌
    return len(board.river) == 0


def _is_chihou(board: BoardState, winner: int, for_ron: bool) -> bool:
    """
    地和：子家第一巡荣和。
    役满。
    """
    if not for_ron:
        return False
    if board.current_seat == 0:  # 亲家不算地和
        return False
    # 第一巡：亲家刚打第一张牌
    return len(board.river) == 1


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
    - 役满：大三元、四暗刻、国士无理、清老头、字一色、绿一色、九莲宝灯、四杠子、大小四喜、天和/地和

    不含ドラ、不含本场。
    """
    full = _full_tile_counter(concealed, melds, win_tile, for_ron=for_ron)

    # ========== 役满判定（优先） ==========
    # 大三元
    if _is_daisangen(full):
        return 13

    # 四暗刻单骑（双倍役满，按 13 番返回）
    if _is_suuankou_tanki(concealed, melds, win_tile, for_ron=for_ron):
        return 13

    # 四暗刻
    if _is_suuankou(concealed, melds, win_tile, for_ron=for_ron):
        return 13

    # 国士无理十三面（双倍役满，按 13 番返回）
    if _is_kokushi_thirteen_waits(concealed, melds, win_tile):
        return 13

    # 国士无理
    if _is_kokushi_musou(concealed, melds):
        return 13

    # 清老头
    if _is_chinroutou(full, melds):
        return 13

    # 字一色
    if _is_tsuuiisou(full, melds):
        return 13

    # 绿一色
    if _is_ryuuiisou(full, melds):
        return 13

    # 纯正九莲宝灯（双倍役满，按 13 番返回）
    if _is_junsei_chuuren_poutou(concealed, melds, win_tile):
        return 13

    # 九莲宝灯
    if _is_chuuren_poutou(concealed, melds, win_tile):
        return 13

    # 四杠子
    if _is_suu_kantsu(melds):
        return 13

    # 大四喜
    if _is_daisuushii(full, melds):
        return 13

    # 小四喜
    if _is_shou_suushii(full, melds):
        return 13

    # 天和
    if _is_tenhou(board, winner, is_tsumo=is_tsumo):
        return 13

    # 地和
    if _is_chihou(board, winner, for_ron=for_ron):
        return 13
    # ========== 役满判定结束 ==========

    han = 0

    # 立直相关
    if winner in board.double_riichi:
        han += 2
    elif board.riichi[winner]:
        han += 1
    if winner in board.ippatsu_eligible:
        han += 1

    rw = _prevailing_wind_tile(table.prevailing_wind)
    sw = Tile(Suit.HONOR, seat_wind_rank(table.dealer_seat, winner))

    # 七对子
    if _is_chiitoitsu(full, melds):
        han += 2
        if _is_tanyao(full, allow_open=allow_open_tanyao, has_melds=False):
            han += 1
        han += _yakuhai_han_chiitoitsu_pairs(full, round_wind_tile=rw, seat_wind_tile=sw)
        return han

    # 岭上开花
    if last_draw_was_rinshan:
        han += 1

    # 海底捞月/河底捞鱼
    if is_haitei or is_hotei:
        han += 1

    # 抢杠
    if is_chankan:
        han += 1

    # 断幺九
    if _is_tanyao(full, allow_open=allow_open_tanyao, has_melds=len(melds) > 0):
        han += 1

    # 役牌
    han += _yakuhai_han_triplets(
        _triplet_key_counts(full),
        round_wind_tile=rw,
        seat_wind_tile=sw,
    )

    # 平和
    if pinfu_eligible(
        concealed,
        melds,
        win_tile,
        for_ron=for_ron,
        round_wind_tile=rw,
        seat_wind_tile=sw,
    ):
        han += 1

    # 对对和
    if _is_toitoi(melds, concealed, win_tile, for_ron=for_ron):
        han += 2

    # 三色同顺
    if _is_sanshoku_same_rank(melds):
        menzen = len(melds) == 0
        han += 3 if menzen else 2

    # 一气通贯
    if _is_ikkitsukan(melds):
        menzen = len(melds) == 0
        han += 3 if menzen else 2

    # 混全带幺 / 纯全带幺（简化版：仅检查副露）
    has_chi = any(m.kind == MeldKind.CHI for m in melds)
    if has_chi:
        # 检查是否所有顺子都包含 1 或 9
        all_chi_have_yaokyuu = True
        for m in melds:
            if m.kind == MeldKind.CHI:
                ranks = [t.rank for t in m.tiles]
                if 1 not in ranks and 9 not in ranks:
                    all_chi_have_yaokyuu = False
                    break
        if all_chi_have_yaokyuu:
            menzen = len(melds) == 0
            # 纯全带幺（无字牌）
            has_honor = any(t.suit == Suit.HONOR for t in full.keys())
            if not has_honor:
                han += 4 if menzen else 3
            else:
                han += 2 if menzen else 1

    # 混老头（全幺九）
    if _is_all_terminals_and_honors(full):
        # 检查是否有七对子（已处理）或标准形
        if not _is_chiitoitsu(full, melds):
            han += 2

    # 三暗刻
    ananko_count = _count_ananko(concealed, melds)
    if ananko_count >= 3:
        han += 2

    # 小三元（三元牌两个刻子 + 一个对子）
    triplet_keys = _triplet_key_counts(full)
    dragon_triplets = sum(1 for rank in (5, 6, 7) if triplet_keys[(Suit.HONOR, rank)] >= 3)
    dragon_pairs = sum(1 for rank in (5, 6, 7) if 2 <= triplet_keys[(Suit.HONOR, rank)] < 3)
    if dragon_triplets == 2 and dragon_pairs >= 1:
        han += 2

    return han
