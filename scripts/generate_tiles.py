"""生成麻将牌图片：jp 风格 + 多方向旋转。

将 mahjim 仓库的图片转换为项目可用的格式：
- 仅保留 jp（日麻）风格
- 生成横置（旋转 90°）、倒置（旋转 180°）版本
- 统一命名规范
"""

from pathlib import Path
from PIL import Image

# 源目录和目标目录
SRC_DIR = Path("ref_repository/mahjim/assets/files")
DEST_DIR = Path("assets/mahjong_tiles")

DEST_DIR.mkdir(parents=True, exist_ok=True)


def save_variants(img: Image.Image, base_name: str) -> None:
    """保存牌的所有变体：正向、横置、倒置。"""
    # 原始（正向）
    img.save(DEST_DIR / f"{base_name}.png")

    # 横置（旋转 90°，用于副露的横向摆放）
    # 注意：旋转后需要交换宽高，expand=False 保持原尺寸但会裁剪
    # 使用 expand=True 会扩大画布，但我们需要保持牌的大小一致
    # 所以先获取旋转后的图像，再粘贴到和原图一样大小的透明画布上
    rotated_90 = img.rotate(270, expand=True)  # 逆时针 90°
    rotated_90.save(DEST_DIR / f"{base_name}_h.png")

    # 倒置（旋转 180°，用于对面玩家视角）
    rotated_180 = img.rotate(180, expand=True)
    rotated_180.save(DEST_DIR / f"{base_name}_i.png")

    # 横置 + 倒置（用于副露 + 对面玩家）
    rotated_270 = img.rotate(90, expand=True)
    rotated_270.save(DEST_DIR / f"{base_name}_hi.png")


def main() -> None:
    """主函数：批量生成所有牌。"""
    generated = []

    # 数牌：万 (m)、饼 (p)、条 (s)，1-9
    # 万子和条子有 jp/cn 版本，饼子没有后缀
    # 万子：带 jp 后缀
    for num in range(1, 10):
        tile = f"{num}m"
        src_file = SRC_DIR / f"{num}mjp.png"
        if src_file.exists():
            img = Image.open(src_file)
            save_variants(img, tile)
            generated.append(tile)

    # 条子：带 jp 后缀（1s 有 1sjp.png，2-9s 直接是 2s.png 等）
    for num in range(1, 10):
        tile = f"{num}s"
        # 优先尝试 jp 版本，没有则用无后缀版本
        src_file = SRC_DIR / f"{num}sjp.png"
        if not src_file.exists():
            src_file = SRC_DIR / f"{num}s.png"
        if src_file.exists():
            img = Image.open(src_file)
            save_variants(img, tile)
            generated.append(tile)

    # 饼子：不带后缀
    for num in range(1, 10):
        tile = f"{num}p"
        src_file = SRC_DIR / f"{num}p.png"
        if src_file.exists():
            img = Image.open(src_file)
            save_variants(img, tile)
            generated.append(tile)

    # 赤牌：5m, 5p, 5s（用 0m, 0p, 0s 表示）
    for suit in ["m", "p", "s"]:
        tile = f"0{suit}"  # 内部用 0 表示赤 5
        src_file = SRC_DIR / f"0{suit}.png"
        if src_file.exists():
            img = Image.open(src_file)
            save_variants(img, f"5{suit}_red")
            generated.append(f"5{suit}_red")

    # 字牌：1-7z = 东南西北白发中（jp 顺序）
    jp_wind_names = ["东", "南", "西", "北", "白", "发", "中"]
    for i, name in enumerate(jp_wind_names, start=1):
        tile_z = f"{i}z"
        tile_name = f"{name}"

        # 优先使用汉字名 + jp 的文件
        src_file = SRC_DIR / f"{tile_name}jp.png"
        if not src_file.exists():
            src_file = SRC_DIR / f"{tile_z}jp.png"

        if src_file.exists():
            img = Image.open(src_file)
            save_variants(img, tile_z)
            generated.append(tile_z)

    # 牌背：用于宝牌指示牌、副露覆盖、明杠等
    # 源文件有 blue.png 和 orange.png 两种牌背颜色
    # 我们默认使用蓝色牌背，命名为 back
    for color in ["blue", "orange"]:
        src_file = SRC_DIR / f"{color}.png"
        if src_file.exists():
            img = Image.open(src_file)
            # 蓝色牌背命名为 back，橙色命名为 back_orange
            base_name = "back" if color == "blue" else "back_orange"
            save_variants(img, base_name)
            generated.append(base_name)

    # 花牌（如果有）：春夏秋冬梅兰竹菊（暂时跳过，日麻不用）

    print(f"生成 {len(generated)} 张牌，每个 4 个变体（原向/横置/倒置/横置 + 倒置）")
    print(f"输出目录：{DEST_DIR}")

    # 生成命名映射表
    mapping = {
        "1m-9m": "万子",
        "1p-9p": "饼子",
        "1s-9s": "条子",
        "0m/5m_red": "赤五万",
        "0p/5p_red": "赤五饼",
        "0s/5s_red": "赤五索",
        "1z": "东",
        "2z": "南",
        "3z": "西",
        "4z": "北",
        "5z": "白",
        "6z": "发",
        "7z": "中",
    }
    suffix_meaning = {
        "": "正向（自家视角）",
        "_h": "横置（顺时针旋转 90°，用于副露）",
        "_i": "倒置（旋转 180°，用于对面玩家）",
        "_hi": "横置 + 倒置（用于对面玩家副露）",
    }

    print("\n命名规则：")
    for k, v in mapping.items():
        print(f"  {k}: {v}")
    print("\n后缀含义：")
    for k, v in suffix_meaning.items():
        print(f"  {k or '(无)'}: {v}")


if __name__ == "__main__":
    main()
