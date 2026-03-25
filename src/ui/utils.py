"""图片拼接工具函数。"""

from __future__ import annotations

from typing import List

from PIL import Image


def concatenate_horizontal(images: List[Image.Image], gap: int = 0) -> Image.Image:
    """
    水平拼接图片。

    Args:
        images: 图片列表
        gap: 图片间距（像素）

    Returns:
        拼接后的图片
    """
    if not images:
        raise ValueError("images list cannot be empty")

    # 计算总宽度（所有图片宽度 + 间距）
    total_width = sum(img.width for img in images) + gap * (len(images) - 1)
    # 使用最大高度
    max_height = max(img.height for img in images)

    # 创建结果图片（RGBA 透明背景）
    result = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))

    # 依次粘贴
    x_offset = 0
    for img in images:
        result.paste(img, (x_offset, 0))
        x_offset += img.width + gap

    return result


def concatenate_vertical(images: List[Image.Image], gap: int = 0) -> Image.Image:
    """
    垂直拼接图片。

    Args:
        images: 图片列表
        gap: 图片间距（像素）

    Returns:
        拼接后的图片
    """
    if not images:
        raise ValueError("images list cannot be empty")

    # 计算总高度（所有图片高度 + 间距）
    total_height = sum(img.height for img in images) + gap * (len(images) - 1)
    # 使用最大宽度
    max_width = max(img.width for img in images)

    # 创建结果图片（RGBA 透明背景）
    result = Image.new("RGBA", (max_width, total_height), (0, 0, 0, 0))

    # 依次粘贴
    y_offset = 0
    for img in images:
        result.paste(img, (0, y_offset))
        y_offset += img.height + gap

    return result


def stack_vertical(
    top: Image.Image,
    bottom: Image.Image,
    gap: int = 0,
    align: str = "left",
) -> Image.Image:
    """
    垂直堆叠两张图片。

    Args:
        top: 上方图片
        bottom: 下方图片
        gap: 间距
        align: 对齐方式（"left" / "center" / "right"）

    Returns:
        堆叠后的图片
    """
    total_height = top.height + bottom.height + gap
    total_width = max(top.width, bottom.width)

    result = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))

    # 计算 x 偏移
    if align == "center":
        top_x = (total_width - top.width) // 2
        bottom_x = (total_width - bottom.width) // 2
    elif align == "right":
        top_x = total_width - top.width
        bottom_x = total_width - bottom.width
    else:  # left
        top_x = 0
        bottom_x = 0

    result.paste(top, (top_x, 0))
    result.paste(bottom, (bottom_x, top.height + gap))

    return result


def place_overlay(
    base: Image.Image,
    overlay: Image.Image,
    position: tuple[int, int],
) -> Image.Image:
    """
    在基础图片上覆盖另一张图片。

    Args:
        base: 基础图片
        overlay: 覆盖图片（支持透明通道）
        position: 覆盖位置的左上角坐标 (x, y)

    Returns:
        覆盖后的图片
    """
    # 确保 base 是 RGBA
    if base.mode != "RGBA":
        base = base.convert("RGBA")

    # 创建副本避免修改原图
    result = base.copy()

    # 粘贴覆盖层（使用 alpha 通道作为 mask）
    result.paste(overlay, position, overlay)

    return result


# ==================== 鸣牌渲染工具函数 ====================

def rotate_variant(variant: str, clockwise: bool = True) -> str:
    """
    在现有 variant 基础上顺时针/逆时针旋转 90°。

    顺时针 90° 映射：
    - "" -> "h" -> "i" -> "hi" -> ""

    逆时针 90° 映射：
    - "" -> "hi" -> "i" -> "h" -> ""
    """
    if clockwise:
        rotate_map = {"": "h", "h": "i", "i": "hi", "hi": ""}
    else:
        rotate_map = {"": "hi", "hi": "i", "i": "h", "h": ""}
    return rotate_map.get(variant, "h")


def get_filename(tile, variant: str = "") -> str:
    """
    获取牌的图片文件名，应用旋转变体。

    Args:
        tile: 牌对象
        variant: 旋转变体（""=正向，"h"=顺时针 90°，"i"=倒置 180°，"hi"=逆时针 90°）

    Returns:
        文件名
    """
    from .tiles import tile_to_filename

    base = tile_to_filename(tile)
    if variant:
        if base.endswith(".png"):
            base = base[:-4]
        return f"{base}_{variant}.png"
    return base


def is_horizontal_variant(variant: str) -> bool:
    """
    判断 variant 是否使牌长边水平（"h" 或 "hi"）。

    Args:
        variant: 旋转变体

    Returns:
        True 如果 variant 是 "h" 或 "hi"
    """
    return variant in ("h", "hi")


def is_opposite_seat(variant: str, from_seat_variant: str) -> bool:
    """
    判断出牌者是否是自家对家。

    规则：variant 中是否包含 "i" 后缀，有 "i" 和没有 "i" 的两两互为对家。
    - "" 的对家是 "i"
    - "h" 的对家是 "hi"

    比较前先统一基准：看是否含有 "i" 后缀。
    """
    variant_has_i = "i" in variant
    variant_has_h = "h" in variant

    from_seat_has_i = "i" in from_seat_variant
    from_seat_has_h = "h" in from_seat_variant

    # 确保其中一方是 i，另一方不是 i
    if (variant_has_i and not from_seat_has_i) or (not variant_has_i and from_seat_has_i):
        # 如果两方都有/没有 h，则视为对家
        if (variant_has_h and from_seat_has_h) or (not variant_has_h and not from_seat_has_h):
            return True
        else:
            return False
    return False


def is_upper_seat(variant: str, from_seat_variant: str) -> bool:
    """
    判断出牌者是否是自家上家。

    上家的 variant 是自家 variant 逆时针旋转 90°（或顺时针旋转 270°）。
    - ""（南家）的上家是 "hi"（东家）
    - "hi"（东家）的上家是 "i"（北家）
    - "i"（北家）的上家是 "h"（西家）
    - "h"（西家）的上家是 ""（南家）
    """
    upper_map = {
        "": "hi",   # 南家的上家是东家
        "hi": "i",  # 东家的上家是北家
        "i": "h",   # 北家的上家是西家
        "h": "",    # 西家的上家是南家
    }
    return upper_map.get(variant) == from_seat_variant
