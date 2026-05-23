"""赤五归一化工具测试（H-36 审计）。

验证要点：
1. tile_key(t) 忽略 is_red（赤五和普通五返回相同 key）
2. logical_counter 合并赤五和普通五
3. yaochu 检查不受赤五影响（赤五不是 yaochu）
"""

from __future__ import annotations

from collections import Counter

from kernel import Suit, Tile
from kernel.tiles.key import tile_key, logical_counter, TileKey


class TestTileKey:
    """tile_key 测试：忽略 is_red。"""

    def test_tile_key_normal_five(self) -> None:
        """普通五牌的 key。"""
        t = Tile(Suit.MAN, 5)
        assert tile_key(t) == (Suit.MAN, 5)

    def test_tile_key_red_five(self) -> None:
        """赤五牌的 key。"""
        t = Tile(Suit.MAN, 5, is_red=True)
        assert tile_key(t) == (Suit.MAN, 5)

    def test_tile_key_red_and_normal_five_equal(self) -> None:
        """赤五和普通五返回相同 key。"""
        normal = Tile(Suit.MAN, 5)
        red = Tile(Suit.MAN, 5, is_red=True)
        assert tile_key(normal) == tile_key(red)

    def test_tile_key_all_suits(self) -> None:
        """三种花色的赤五都归一化。"""
        for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
            normal = Tile(suit, 5)
            red = Tile(suit, 5, is_red=True)
            assert tile_key(normal) == tile_key(red)
            assert tile_key(red) == (suit, 5)

    def test_tile_key_non_five(self) -> None:
        """非五牌不受影响。"""
        for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
            for rank in (1, 2, 3, 4, 6, 7, 8, 9):
                t = Tile(suit, rank)
                assert tile_key(t) == (suit, rank)

    def test_tile_key_honor(self) -> None:
        """字牌不受影响。"""
        for rank in range(1, 8):
            t = Tile(Suit.HONOR, rank)
            assert tile_key(t) == (Suit.HONOR, rank)


class TestLogicalCounter:
    """logical_counter 测试：合并赤五和普通五。"""

    def test_logical_counter_empty(self) -> None:
        """空 Counter 返回空。"""
        c: Counter[Tile] = Counter()
        result = logical_counter(c)
        assert len(result) == 0

    def test_logical_counter_single_normal_five(self) -> None:
        """单张普通五。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 5)] = 3
        result = logical_counter(c)
        assert result[(Suit.MAN, 5)] == 3

    def test_logical_counter_single_red_five(self) -> None:
        """单张赤五。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 5, is_red=True)] = 1
        result = logical_counter(c)
        assert result[(Suit.MAN, 5)] == 1

    def test_logical_counter_merge_red_and_normal(self) -> None:
        """赤五和普通五合并。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 5)] = 2  # 两张普通 5m
        c[Tile(Suit.MAN, 5, is_red=True)] = 1  # 一张赤 5m
        result = logical_counter(c)
        # 合并后总共 3 张
        assert result[(Suit.MAN, 5)] == 3

    def test_logical_counter_all_suits(self) -> None:
        """三种花色的赤五分别合并。"""
        c: Counter[Tile] = Counter()
        # 5m: 2 normal + 1 red = 3
        c[Tile(Suit.MAN, 5)] = 2
        c[Tile(Suit.MAN, 5, is_red=True)] = 1
        # 5p: 1 normal + 2 red = 3
        c[Tile(Suit.PIN, 5)] = 1
        c[Tile(Suit.PIN, 5, is_red=True)] = 2
        # 5s: 0 normal + 1 red = 1
        c[Tile(Suit.SOU, 5, is_red=True)] = 1

        result = logical_counter(c)
        assert result[(Suit.MAN, 5)] == 3
        assert result[(Suit.PIN, 5)] == 3
        assert result[(Suit.SOU, 5)] == 1

    def test_logical_counter_mixed_tiles(self) -> None:
        """混合多种牌。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 5)] = 2
        c[Tile(Suit.MAN, 5, is_red=True)] = 1
        c[Tile(Suit.PIN, 9)] = 2
        c[Tile(Suit.HONOR, 7)] = 1

        result = logical_counter(c)
        assert result[(Suit.MAN, 1)] == 3
        assert result[(Suit.MAN, 5)] == 3  # 合并
        assert result[(Suit.PIN, 9)] == 2
        assert result[(Suit.HONOR, 7)] == 1

    def test_logical_counter_multiple_red_fives(self) -> None:
        """多张赤五。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 5, is_red=True)] = 4  # 不可能的场景，但测试归一化逻辑
        result = logical_counter(c)
        assert result[(Suit.MAN, 5)] == 4


class TestYaochuAndRedFive:
    """yaochu 检查与赤五的关系。"""

    def test_red_five_is_not_yaochu_by_rank(self) -> None:
        """赤五不是幺九牌（rank=5）。"""
        from kernel.scoring.yaku import _tile_is_yaochuu

        red_5m = Tile(Suit.MAN, 5, is_red=True)
        red_5p = Tile(Suit.PIN, 5, is_red=True)
        red_5s = Tile(Suit.SOU, 5, is_red=True)

        assert _tile_is_yaochuu(red_5m) is False
        assert _tile_is_yaochuu(red_5p) is False
        assert _tile_is_yaochuu(red_5s) is False

    def test_normal_five_is_not_yaochu_by_rank(self) -> None:
        """普通五也不是幺九牌（rank=5）。"""
        from kernel.scoring.yaku import _tile_is_yaochuu

        normal_5m = Tile(Suit.MAN, 5)
        normal_5p = Tile(Suit.PIN, 5)
        normal_5s = Tile(Suit.SOU, 5)

        assert _tile_is_yaochuu(normal_5m) is False
        assert _tile_is_yaochuu(normal_5p) is False
        assert _tile_is_yaochuu(normal_5s) is False

    def test_yaochu_tiles_do_not_include_red_five(self) -> None:
        """_YAOCHU_TILES 常量不含赤五。"""
        from kernel.call.win import _YAOCHU_TILES

        red_5m = Tile(Suit.MAN, 5, is_red=True)
        red_5p = Tile(Suit.PIN, 5, is_red=True)
        red_5s = Tile(Suit.SOU, 5, is_red=True)

        # 赤五不在常量列表中
        assert red_5m not in _YAOCHU_TILES
        assert red_5p not in _YAOCHU_TILES
        assert red_5s not in _YAOCHU_TILES

    def test_yaochu_tiles_include_normal_five(self) -> None:
        """_YAOCHU_TILES 常量也不含普通五。"""
        from kernel.call.win import _YAOCHU_TILES

        # 普通五也不是幺九
        normal_5m = Tile(Suit.MAN, 5)
        normal_5p = Tile(Suit.PIN, 5)
        normal_5s = Tile(Suit.SOU, 5)

        assert normal_5m not in _YAOCHU_TILES
        assert normal_5p not in _YAOCHU_TILES
        assert normal_5s not in _YAOCHU_TILES

    def test_yaochu_tiles_include_terminals_and_honors(self) -> None:
        """_YAOCHU_TILES 包含所有幺九牌。"""
        from kernel.call.win import _YAOCHU_TILES

        # 19 数牌
        assert Tile(Suit.MAN, 1) in _YAOCHU_TILES
        assert Tile(Suit.MAN, 9) in _YAOCHU_TILES
        assert Tile(Suit.PIN, 1) in _YAOCHU_TILES
        assert Tile(Suit.PIN, 9) in _YAOCHU_TILES
        assert Tile(Suit.SOU, 1) in _YAOCHU_TILES
        assert Tile(Suit.SOU, 9) in _YAOCHU_TILES

        # 字牌
        for rank in range(1, 8):
            assert Tile(Suit.HONOR, rank) in _YAOCHU_TILES


class TestTileKeyType:
    """TileKey 类型测试。"""

    def test_tile_key_is_tuple(self) -> None:
        """TileKey 是元组类型。"""
        t = Tile(Suit.MAN, 5)
        key = tile_key(t)
        assert isinstance(key, tuple)
        assert len(key) == 2

    def test_tile_key_hashable(self) -> None:
        """TileKey 可哈希（可作为 dict/Counter key）。"""
        t1 = Tile(Suit.MAN, 5)
        t2 = Tile(Suit.MAN, 5, is_red=True)

        d: dict[TileKey, str] = {}
        d[tile_key(t1)] = "five_man"
        d[tile_key(t2)] = "overwritten"  # 相同 key 会覆盖

        assert len(d) == 1
        assert d[tile_key(t1)] == "overwritten"

    def test_tile_key_counter(self) -> None:
        """TileKey 可用于 Counter。"""
        c: Counter[TileKey] = Counter()
        c[tile_key(Tile(Suit.MAN, 5))] += 1
        c[tile_key(Tile(Suit.MAN, 5, is_red=True))] += 1

        # 相同 key，计数合并
        assert c[(Suit.MAN, 5)] == 2