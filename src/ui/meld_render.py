"""鸣牌（副露）渲染逻辑。"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from PIL import Image

from kernel.hand.melds import MeldKind

from .tiles import TileImageCache
from .utils import (
    concatenate_horizontal,
    concatenate_vertical,
    get_filename,
    is_horizontal_variant,
    is_opposite_seat,
    is_upper_seat,
    rotate_variant,
)

if TYPE_CHECKING:
    from kernel.hand.melds import Meld


def render_meld(
    meld: Meld,
    cache: TileImageCache,
    variant: str = "",
    from_seat_variant: str = "",
) -> Image.Image:
    """
    渲染一副副露。

    Args:
        meld: 副露对象
        cache: 图片缓存加载器
        variant: 自家旋转变体（""=正向，"h"=顺时针 90°，"i"=倒置 180°，"hi"=逆时针 90°）
        from_seat_variant: 出牌者旋转变体（用于鸣入的牌）

    Returns:
        渲染后的副露图片
    """
    tiles = meld.tiles

    if meld.kind == MeldKind.CHI:
        return _render_chi(tiles, meld.called_tile, cache, variant, from_seat_variant)
    elif meld.kind == MeldKind.PON:
        return _render_pon(tiles, cache, variant, from_seat_variant)
    elif meld.kind == MeldKind.DAIMINKAN:
        return _render_daiminkan(tiles, cache, variant, from_seat_variant)
    elif meld.kind == MeldKind.ANKAN:
        return _render_ankan(tiles, cache, variant)
    elif meld.kind == MeldKind.SHANKUMINKAN:
        return _render_shankuminkan(tiles, cache, variant, from_seat_variant)
    else:
        raise ValueError(f"unknown meld kind: {meld.kind}")


def _render_chi(
    tiles: tuple,
    called_tile,
    cache: TileImageCache,
    variant: str = "",
    from_seat_variant: str = "",
) -> Image.Image:
    """
    渲染吃（CHI）。

    鸣入的牌用出牌者的 variant，自家的牌用自家 variant。
    """
    if variant == "hi" or variant == "i":
        called_index = 0
    elif variant == "h" or variant == "":
        called_index = 2

    # 先按 tiles 顺序各加载一张（鸣入张用 from_seat_variant），再挪到显示位
    called_pos = next(i for i, t in enumerate(tiles) if t == called_tile)
    imgs: List[Image.Image] = [
        cache.load(
            get_filename(
                tiles[i],
                from_seat_variant if i == called_pos else variant,
            ),
        )
        for i in range(3)
    ]
    called_img = imgs.pop(called_pos)
    images = [called_img] + imgs if called_index == 0 else imgs + [called_img]

    # 根据自家 variant 决定拼接方向
    if is_horizontal_variant(variant):
        return concatenate_vertical(images, gap=2)
    else:
        return concatenate_horizontal(images, gap=2)


def _render_pon(
    tiles: tuple,
    cache: TileImageCache,
    variant: str = "",
    from_seat_variant: str = "",
) -> Image.Image:
    """
    渲染碰（PON）。

    鸣入的牌横置（相对于自家 variant 顺时针旋转 90°），位置根据出牌者相对位置决定：
    - 上家：鸣入的牌放在靠近上家的一侧
    - 下家：鸣入的牌放在靠近下家的一侧
    - 对家：鸣入的牌放在中间（索引 1）

    水平排列（""/i）：索引 0=左，1=中，2=右
    垂直排列（h/hi）：索引 0=上，1=中，2=下
    """
    # 判断出牌者位置
    is_opposite = is_opposite_seat(variant, from_seat_variant)
    is_upper = is_upper_seat(variant, from_seat_variant)

    images: List[Image.Image] = []
    for i, tile in enumerate(tiles):
        # 对家：鸣入的牌放在中间（索引 1）
        if is_opposite:
            if i == 1:
                filename = get_filename(tile, rotate_variant(variant, clockwise=True))
            else:
                # 自家的牌（索引 0 和 2）
                filename = get_filename(tile, variant)

        # 上家：鸣入的牌放在靠近上家的一侧
        elif is_upper:
            # 两套逻辑："hi"和"i"一套，"h"和" "一套
            if variant == "hi" or variant == "i":
                if i == 0:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
            # "h"和" "
            elif variant == "h" or variant == "":
                if i == 2:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
        # 下家：鸣入的牌放在靠近下家的一侧
        else:
            # 两套逻辑："hi"和"i"一套，"h"和" "一套
            if variant == "hi" or variant == "i":
                if i == 2:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
            # "h"和" "
            elif variant == "h" or variant == "":
                if i == 0:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
        images.append(cache.load(filename))

    # 根据自家 variant 决定拼接方向
    if is_horizontal_variant(variant):
        return concatenate_vertical(images, gap=2)
    else:
        return concatenate_horizontal(images, gap=2)


def _render_daiminkan(
    tiles: tuple,
    cache: TileImageCache,
    variant: str = "",
    from_seat_variant: str = "",
) -> Image.Image:
    """
    渲染大明杠（DAIMINKAN）。

    鸣入的牌横置（相对于自家 variant 顺时针旋转 90°），位置根据出牌者相对位置决定：
    - 上家：鸣入的牌放在靠近上家的一侧
    - 下家：鸣入的牌放在靠近下家的一侧
    - 对家：鸣入的牌放在中间偏右/下（索引 2）

    水平排列（""/i）：索引 0=左，1=中左，2=中右，3=右
    垂直排列（h/hi）：索引 0=上，1=中上，2=中下，3=下

    上/下家鸣入侧与碰一致：按自家 variant 分「hi/i」与「h/""」两套；
    四枚时上家鸣入索引 0 或 3，下家 3 或 0（与三枚碰的 0、2 同侧）。
    """
    # 判断出牌者位置
    is_opposite = is_opposite_seat(variant, from_seat_variant)
    is_upper = is_upper_seat(variant, from_seat_variant)

    images: List[Image.Image] = []
    for i, tile in enumerate(tiles):
        if is_opposite:
            # 对家：鸣入的牌放在中间偏右/下（索引 2），横置
            if i == 2:
                filename = get_filename(tile, rotate_variant(variant, clockwise=True))
            else:
                filename = get_filename(tile, variant)
        elif is_upper:
            # 上家：与碰相同规则，四枚时鸣入在 0（hi/i）或 3（h/""）
            if variant == "hi" or variant == "i":
                if i == 0:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
            elif variant == "h" or variant == "":
                if i == 3:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
        else:
            # 下家：与碰相同规则，四枚时鸣入在 3（hi/i）或 0（h/""）
            if variant == "hi" or variant == "i":
                if i == 3:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
            elif variant == "h" or variant == "":
                if i == 0:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
        images.append(cache.load(filename))

    # 根据自家 variant 决定拼接方向
    if is_horizontal_variant(variant):
        return concatenate_vertical(images, gap=2)
    else:
        return concatenate_horizontal(images, gap=2)


def _render_ankan(
    tiles: tuple,
    cache: TileImageCache,
    variant: str = "",
) -> Image.Image:
    """
    渲染暗杠（ANKAN）。

    两侧牌背覆盖，中间两张用自家 variant。
    TODO 取消硬编码，参数化
    """
    back_img = cache.load(f"back_orange_{variant}.png") if variant != "" else cache.load(f"back_orange.png")
    tile_images = [
        back_img,
        cache.load(get_filename(tiles[1], variant)),
        cache.load(get_filename(tiles[2], variant)),
        back_img,
    ]

    # 根据自家 variant 决定拼接方向
    if is_horizontal_variant(variant):
        return concatenate_vertical(tile_images, gap=2)
    else:
        return concatenate_horizontal(tile_images, gap=2)


def _render_shankuminkan(
    tiles: tuple,
    cache: TileImageCache,
    variant: str = "",
    from_seat_variant: str = "",
) -> Image.Image:
    """
    渲染加杠（SHANKUMINKAN）。

    鸣入的牌横置（相对于自家 variant 顺时针旋转 90°），位置根据出牌者相对位置决定：
    - 上家：鸣入的牌放在靠近上家的一侧
    - 下家：鸣入的牌放在靠近下家的一侧
    - 对家：鸣入的牌放在中间偏右/下（索引 2）

    水平排列（""/i）：索引 0=左，1=中左，2=中右，3=右
    垂直排列（h/hi）：索引 0=上，1=中上，2=中下，3=下

    上/下家鸣入侧与碰、大明杠一致；对家鸣入横置。
    """
    called_variant = rotate_variant(variant, clockwise=True)

    # 判断出牌者位置
    is_opposite = is_opposite_seat(variant, from_seat_variant)
    is_upper = is_upper_seat(variant, from_seat_variant)

    images: List[Image.Image] = []
    for i, tile in enumerate(tiles):
        if is_opposite:
            # 对家：鸣入的牌放在中间偏右/下（索引 2），横置
            if i == 2:
                filename = get_filename(tile, called_variant)
            else:
                filename = get_filename(tile, variant)
        elif is_upper:
            if variant == "hi" or variant == "i":
                if i == 0:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
            elif variant == "h" or variant == "":
                if i == 3:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
        else:
            if variant == "hi" or variant == "i":
                if i == 3:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
            elif variant == "h" or variant == "":
                if i == 0:
                    filename = get_filename(tile, from_seat_variant)
                else:
                    filename = get_filename(tile, variant)
        images.append(cache.load(filename))

    # 根据自家 variant 决定拼接方向
    if is_horizontal_variant(variant):
        return concatenate_vertical(images, gap=2)
    else:
        return concatenate_horizontal(images, gap=2)
