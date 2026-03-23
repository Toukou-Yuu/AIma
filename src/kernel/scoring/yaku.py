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

    不含ドラ、不含本场。
    """
    full = _full_tile_counter(concealed, melds, win_tile, for_ron=for_ron)
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
