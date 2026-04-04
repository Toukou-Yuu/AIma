"""牌面渲染组件."""

from __future__ import annotations

from rich.text import Text

# 炫彩虹宝牌颜色循环
_DORA_RAINBOW = [
    "red",      # 红
    "yellow",   # 黄
    "green",    # 绿
    "cyan",     # 青
    "blue",     # 蓝
    "magenta",  # 紫
]

_SUIT_COLORS = {
    "m": "bright_white",  # 万子
    "p": "bright_green",  # 筒子
    "s": "bright_blue",   # 索子
    "z": "bright_yellow", # 字牌
}

_HONOR_MAP = {
    "1": "東",
    "2": "南",
    "3": "西",
    "4": "北",
    "5": "白",
    "6": "發",
    "7": "中",
}

_WIND_NAMES = ["东", "南", "西", "北"]


def tile_to_rich(tile_code: str, is_dora: bool = False) -> Text:
    """将牌码（如'1m'、'5sr'、'7z'）渲染为带颜色的 Text。

    Args:
        tile_code: 牌码
        is_dora: 是否为宝牌（使用红色底色）
    """
    if not tile_code:
        return Text("")

    suit = tile_code[0] if tile_code[0] in "mpsz" else tile_code[-1]
    color = _SUIT_COLORS.get(suit, "white")

    # 宝牌使用红色底色
    if is_dora:
        fg_color = "bright_yellow" if suit == "z" else color
        style = f"bold {fg_color} on bright_red"
    else:
        style = color

    # 赤宝牌标红
    if "r" in tile_code:
        style = "bright_red"

    # 字牌用汉字
    if suit == "z":
        display = _HONOR_MAP.get(tile_code[0], tile_code[0])
        return Text(display, style=style)

    return Text(tile_code.replace("r", ""), style=style)


def wind_with_seat(wind_idx: int, seat: int, is_active: bool = False) -> Text:
    """生成带样式的风位+座位标签，如'东(S0)'。

    Args:
        wind_idx: 相对风位索引 (0=东, 1=南, 2=西, 3=北)
        seat: 绝对座位号 (0-3)
        is_active: 是否为当前操作席（高亮显示）
    """
    wind = _WIND_NAMES[wind_idx]
    style = "bold bright_cyan" if is_active else "bright_white"
    return Text.assemble(
        (wind, style),
        (f"(S{seat})", "dim")
    )


def parse_hand_tiles(hand_str: str) -> list[Text]:
    """解析手牌字符串（如'1m2m3m4p5p'）为 Text 列表。"""
    tiles = []
    i = 0
    while i < len(hand_str):
        if hand_str[i] == " ":
            i += 1
            continue
        if i + 1 < len(hand_str) and hand_str[i + 1] in "mpsz":
            if i + 2 < len(hand_str) and hand_str[i + 2] == "r":
                tiles.append(tile_to_rich(hand_str[i : i + 3]))
                i += 3
            else:
                tiles.append(tile_to_rich(hand_str[i : i + 2]))
                i += 2
        else:
            i += 1
    return tiles
