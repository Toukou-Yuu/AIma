"""牌图片映射与缓存。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from kernel.tiles.model import Tile


def tile_to_filename(tile: Tile) -> str:
    """
    将 Tile 转换为图片文件名。

    Args:
        tile: 内核的 Tile 对象

    Returns:
        图片文件名（不含路径）

    Examples:
        >>> Tile(Suit.MAN, 1, False) -> "1m.png"
        >>> Tile(Suit.MAN, 5, True) -> "5m_red.png"
        >>> Tile(Suit.HONOR, 1, False) -> "1z.png"
    """
    from kernel.tiles.model import Suit

    if tile.suit == Suit.HONOR:
        return f"{tile.rank}z.png"

    suit_map = {Suit.MAN: "m", Suit.PIN: "p", Suit.SOU: "s"}
    letter = suit_map[tile.suit]

    if tile.rank == 5 and tile.is_red:
        return f"5{letter}_red.png"

    return f"{tile.rank}{letter}.png"


def filename_with_variant(filename: str, variant: str = "") -> str:
    """
    根据旋转变体生成文件名。

    Args:
        filename: 基础文件名（如 "1m.png"）
        variant: 变体后缀（"" / "h" / "i" / "hi"）
            - "": 正向
            - "h": 横置（顺时针 90°）
            - "i": 倒置（180°）
            - "hi": 横置 + 倒置

    Returns:
        完整文件名

    Examples:
        >>> filename_with_variant("1m.png", "") -> "1m.png"
        >>> filename_with_variant("1m.png", "h") -> "1m_h.png"
        >>> filename_with_variant("5m_red.png", "i") -> "5m_red_i.png"
    """
    if not variant:
        return filename

    # 移除 .png 后缀，添加变体后缀
    base = filename[:-4] if filename.endswith(".png") else filename
    return f"{base}_{variant}.png"


class TileImageCache:
    """
    牌图片缓存加载器。

    用法:
        >>> cache = TileImageCache(Path("assets/mahjong_tiles"))
        >>> img = cache.load("1m.png")
        >>> img_h = cache.load("1m_h.png")
    """

    def __init__(self, tile_dir: Path):
        """
        初始化缓存。

        Args:
            tile_dir: 牌图片目录
        """
        self._cache: dict[str, Image.Image] = {}
        self._tile_dir = tile_dir

    def load(self, filename: str) -> Image.Image:
        """
        加载图片（带缓存）。

        Args:
            filename: 文件名

        Returns:
            PIL Image 对象
        """
        if filename not in self._cache:
            path = self._tile_dir / filename
            self._cache[filename] = Image.open(path)
        return self._cache[filename]

    def load_tile(self, tile: Tile, variant: str = "") -> Image.Image:
        """
        加载指定 Tile 的图片。

        Args:
            tile: 内核的 Tile 对象
            variant: 旋转变体（"" / "h" / "i" / "hi"）

        Returns:
            PIL Image 对象
        """
        filename = filename_with_variant(tile_to_filename(tile), variant)
        return self.load(filename)

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()
