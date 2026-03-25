"""主渲染器：渲染完整桌面。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from PIL import Image, ImageDraw, ImageFont

from kernel.deal.model import BoardState

from .meld_render import render_meld
from .tiles import TileImageCache, tile_to_filename
from .utils import concatenate_horizontal, concatenate_vertical, stack_vertical

if TYPE_CHECKING:
    from kernel.engine.state import GameState


# 默认字体（使用系统字体）
def _get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """获取字体。"""
    # 尝试加载中文字体
    font_paths = [
        "C:\\Windows\\Fonts\\msyh.ttc",  # 微软雅黑 (Windows)
        "/System/Library/Fonts/PingFang.ttc",  # PingFang (macOS)
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",  # Noto CJK (Linux)
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    #  fallback 到默认字体
    return ImageFont.load_default()


class TableRenderer:
    """
    桌面渲染器。

    用法:
        >>> renderer = TableRenderer()
        >>> image = renderer.render(state)
        >>> image.save("output.png")
    """

    def __init__(self, tile_dir: Path = Path("assets/mahjong_tiles")):
        """
        初始化渲染器。

        Args:
            tile_dir: 牌图片目录
        """
        self.tile_cache = TileImageCache(tile_dir)
        self._font = _get_font()

    def render(self, state: GameState) -> Image.Image:
        """
        渲染当前局面。

        Args:
            state: 游戏状态

        Returns:
            渲染后的图片
        """
        board = state.board
        table = state.table

        if board is None:
            return self._render_empty()

        # 1. 渲染宝牌指示器（包含未翻开时的牌背）
        dora_image = self._render_dora(board.revealed_indicators)

        # 2. 渲染场况信息（移动到中间区域）
        info_image = self._render_info(table, len(board.live_wall))

        # 3. 渲染四家手牌（应用方向）
        # seat 0=东家（右侧）：牌用 hi 变体，垂直排列
        # seat 1=南家（下方，自家）：牌正向，水平排列
        # seat 2=西家（左侧）：牌用 h 变体，垂直排列
        # seat 3=北家（上方，对家）：牌用 i 变体，水平排列
        player_images = []
        for seat in range(4):
            if seat == 0 or seat == 2:
                # 东家/西家：垂直排列
                img = self._render_player_hand_vertical(board, seat, variant="hi" if seat == 0 else "h")
            elif seat == 1:
                # 南家/自家：水平排列，副露在下方
                img = self._render_player_hand_horizontal(board, seat, variant="", meld_below=True)
            else:
                # 北家/对家：水平排列，副露在下方（因为手牌倒置后，下方就是朝向牌桌中心）
                img = self._render_player_hand_horizontal(board, seat, variant="i", meld_below=True)
            player_images.append(img)

        # 4. 渲染四家牌河
        river_images = self._render_river(board.river)

        # 5. 组合完整布局
        return self._compose_layout(
            dora=dora_image,
            info=info_image,
            players=player_images,
            rivers=river_images,
        )

    def _render_empty(self) -> Image.Image:
        """渲染空局面（游戏未开始）。"""
        img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((350, 280), "对局未开始", font=self._font, fill=(255, 255, 255, 255))
        return img

    def _render_dora(self, indicators: tuple) -> Image.Image:
        """渲染宝牌指示器（未翻开时显示牌背）。"""
        if not indicators:
            # 没有宝牌指示器时显示牌背
            return self.tile_cache.load("back.png")

        images = [
            self.tile_cache.load(tile_to_filename(tile))
            for tile in indicators
        ]
        return concatenate_horizontal(images, gap=4)

    def _render_info(self, table, wall_remaining: int) -> Image.Image:
        """渲染场况信息（不含宝牌）。"""
        # 构建信息文本
        # table.prevailing_wind 是 PrevailingWind 枚举
        wind_str = table.prevailing_wind.value  # "east" or "south"
        wind_display = "东" if wind_str == "east" else "南"

        # table.round_number 是 RoundNumber 枚举，value 是 1-4
        round_num = table.round_number.value

        lines = [
            f"{wind_display}{round_num}局",
            f"本场：{table.honba}",
            f"余牌：{wall_remaining}",
        ]

        # 添加点数
        seat_names = ["东", "南", "西", "北"]
        for i, score in enumerate(table.scores):
            lines.append(f"{seat_names[i]}: {score}")

        # 计算文本边界
        max_width = 0
        total_height = 0
        for line in lines:
            bbox = self._font.getbbox(line)
            max_width = max(max_width, bbox[2])
            total_height += bbox[3] - bbox[1] + 2

        # 创建背景
        padding = 4
        img = Image.new(
            "RGBA",
            (max_width + padding * 2, total_height + padding * 2),
            (0, 0, 0, 180),
        )
        draw = ImageDraw.Draw(img)

        # 绘制文本
        y = padding
        for line in lines:
            draw.text((padding, y), line, font=self._font, fill=(255, 255, 255, 255))
            bbox = self._font.getbbox(line)
            y += bbox[3] - bbox[1] + 2

        return img

    def _render_player_hand_horizontal(
        self,
        board: BoardState,
        seat: int,
        variant: str = "",
        meld_below: bool = True,
    ) -> Image.Image:
        """
        渲染一家手牌（含副露）- 水平排列（用于南家/北家）。

        Args:
            seat: 座位号（0=东，1=南，2=西，3=北）
            variant: 牌的旋转变体（""=正向，"i"=倒置 180°）
            meld_below: 副露是否在手牌下方（True=下方，False=上方）
        """
        hand = board.hands[seat]
        melds = board.melds[seat]

        # 手牌部分
        tile_images = [
            self.tile_cache.load_tile(tile, variant)
            for tile in hand.elements()
        ]
        if tile_images:
            hand_row = concatenate_horizontal(tile_images, gap=1)
        else:
            hand_row = Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        # 副露部分
        if melds:
            # 构建 variant 映射表
            seat_variants = {0: "hi", 1: "", 2: "h", 3: "i"}
            meld_images = []
            for m in melds:
                # 根据 from_seat 获取出牌者的 variant
                from_seat_variant = seat_variants.get(m.from_seat, "") if m.from_seat is not None else ""
                meld_images.append(render_meld(m, self.tile_cache, variant, from_seat_variant))
            meld_row = concatenate_horizontal(meld_images, gap=4)
            # 根据 meld_below 决定副露位置
            if meld_below:
                # 手牌在上，副露在下（南家/自家）
                return stack_vertical(hand_row, meld_row, gap=2, align="left")
            else:
                # 副露在上，手牌在下（北家/对家）
                return stack_vertical(meld_row, hand_row, gap=2, align="left")

        return hand_row

    def _render_player_hand_vertical(
        self,
        board: BoardState,
        seat: int,
        variant: str = "h",
    ) -> Image.Image:
        """
        渲染一家手牌（含副露）- 垂直排列（用于东家/西家）。

        Args:
            seat: 座位号（0=东，1=南，2=西，3=北）
            variant: 牌的旋转变体（"h"=顺时针 90°，"hi"=逆时针 90°）
        """
        hand = board.hands[seat]
        melds = board.melds[seat]

        # 手牌部分 - 垂直排列（直接应用 variant）
        tile_images = [
            self.tile_cache.load_tile(tile, variant)
            for tile in hand.elements()
        ]
        if tile_images:
            hand_col = concatenate_vertical(tile_images, gap=1)
        else:
            hand_col = Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        # 副露部分 - 直接用自家 variant 渲染
        if melds:
            # 构建 variant 映射表
            seat_variants = {0: "hi", 1: "", 2: "h", 3: "i"}
            meld_cols = []
            for m in melds:
                # 根据 from_seat 获取出牌者的 variant
                from_seat_variant = seat_variants.get(m.from_seat, "") if m.from_seat is not None else ""
                # 用自家 variant + 出牌者 variant 渲染副露
                meld_v = render_meld(m, self.tile_cache, variant, from_seat_variant)
                meld_cols.append(meld_v)

            meld_col = concatenate_vertical(meld_cols, gap=4)
            # 东家：手牌在右，副露在左（朝向牌桌中心）
            # 西家：副露在右，手牌在左（朝向牌桌中心）
            if seat == 0:
                return concatenate_horizontal([meld_col, hand_col], gap=2)
            else:
                return concatenate_horizontal([hand_col, meld_col], gap=2)

        return hand_col

    def _render_river(self, river) -> Image.Image:
        """渲染牌河（四家合并）。"""
        if not river:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        # 按家分组
        rivers_by_seat = {0: [], 1: [], 2: [], 3: []}
        for entry in river:
            rivers_by_seat[entry.seat].append(entry.tile)

        # 渲染每家的牌河
        river_images = [
            self._render_single_river(rivers_by_seat[seat], seat)
            for seat in range(4)
        ]

        return river_images

    def _render_single_river(self, tiles: list, seat: int) -> Image.Image:
        """
        渲染一家牌河。

        Args:
            tiles: 该家的舍牌列表
            seat: 座位号（决定牌河方向）
        """
        if not tiles:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        # 每行 6 张牌
        ROW_SIZE = 6
        rows: List[List[Image.Image]] = []
        current_row: List[Image.Image] = []

        for tile in tiles:
            tile_img = self.tile_cache.load(tile_to_filename(tile))
            current_row.append(tile_img)

            if len(current_row) >= ROW_SIZE:
                rows.append(current_row)
                current_row = []

        if current_row:
            rows.append(current_row)

        # 拼接每行
        row_images = [
            concatenate_horizontal(row, gap=1) for row in rows
        ]

        # 垂直拼接行
        return concatenate_vertical(row_images, gap=2)

    def _compose_layout(
        self,
        dora: Image.Image,
        info: Image.Image,
        players: List[Image.Image],
        rivers: List[Image.Image],
    ) -> Image.Image:
        """
        组合完整布局。

        布局：
        - 左上角：宝牌指示器
        - 上方：北家 (players[3])
        - 右侧：东家 (players[0])
        - 下方：南家 (players[1])
        - 左侧：西家 (players[2])
        - 中间：场况信息
        - 四家牌河：各家手牌内侧
        """
        # 2k 画布尺寸
        margin = 40  # 增大边距
        total_width = 2560
        total_height = 1440

        result = Image.new("RGBA", (total_width, total_height), (30, 30, 30, 255))

        # 放置宝牌指示器（左上角）
        result.paste(dora, (margin, margin), dora if dora.mode == "RGBA" else None)

        # 计算中心区域（画布中心）
        center_x = total_width // 2
        center_y = total_height // 2

        # 放置场况信息（中心区域）
        info_x = center_x - info.width // 2
        info_y = center_y - info.height // 2
        result.paste(info, (info_x, info_y), info if info.mode == "RGBA" else None)

        # 放置四家手牌 - 增大与中心的距离
        # 东家（右侧）- 垂直居中，离中心更远
        east_x = total_width - margin - players[0].width
        east_y = (total_height - players[0].height) // 2
        east_mask = players[0] if players[0].mode == "RGBA" else None
        result.paste(players[0], (east_x, east_y), east_mask)

        # 南家（下方）- 水平居中，离中心更远
        south_x = (total_width - players[1].width) // 2
        south_y = total_height - margin - players[1].height
        south_mask = players[1] if players[1].mode == "RGBA" else None
        result.paste(players[1], (south_x, south_y), south_mask)

        # 西家（左侧）- 垂直居中，离中心更远
        west_x = margin
        west_y = (total_height - players[2].height) // 2
        west_mask = players[2] if players[2].mode == "RGBA" else None
        result.paste(players[2], (west_x, west_y), west_mask)

        # 北家（上方）- 水平居中，离中心更远
        north_x = (total_width - players[3].width) // 2
        north_y = margin
        north_mask = players[3] if players[3].mode == "RGBA" else None
        result.paste(players[3], (north_x, north_y), north_mask)

        # 放置四家牌河 - 各家手牌内侧
        # 东家牌河（右侧手牌左边）
        if rivers[0].width > 1 and rivers[0].height > 1:
            river0_x = east_x - rivers[0].width - 20
            river0_y = (total_height - rivers[0].height) // 2
            result.paste(rivers[0], (river0_x, river0_y), rivers[0] if rivers[0].mode == "RGBA" else None)

        # 南家牌河（下方手牌上边）
        if rivers[1].width > 1 and rivers[1].height > 1:
            river1_x = (total_width - rivers[1].width) // 2
            river1_y = south_y - rivers[1].height - 20
            result.paste(rivers[1], (river1_x, river1_y), rivers[1] if rivers[1].mode == "RGBA" else None)

        # 西家牌河（左侧手牌右边）
        if rivers[2].width > 1 and rivers[2].height > 1:
            river2_x = west_x + players[2].width + 20
            river2_y = (total_height - rivers[2].height) // 2
            result.paste(rivers[2], (river2_x, river2_y), rivers[2] if rivers[2].mode == "RGBA" else None)

        # 北家牌河（上方手牌下边）
        if rivers[3].width > 1 and rivers[3].height > 1:
            river3_x = (total_width - rivers[3].width) // 2
            river3_y = north_y + players[3].height + 20
            result.paste(rivers[3], (river3_x, river3_y), rivers[3] if rivers[3].mode == "RGBA" else None)

        return result
