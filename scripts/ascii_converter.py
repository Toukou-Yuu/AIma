"""ASCII 形象转换脚本。

将图片转换为 Unicode 半块字符风格的终端艺术。
保持原始图片的显示比例。

用法:
    python scripts/ascii_converter.py <图片路径> <输出路径> [--width 60]

示例:
    python scripts/ascii_converter.py img.png configs/players/kavi/ascii.txt
    python scripts/ascii_converter.py img.png configs/players/kavi/ascii.txt --width 40
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def image_to_unicode_art_halfblock(
    image_path: str | Path,
    output_path: str | Path,
    width: int = 60,
) -> None:
    """将图片转换为 Unicode 半块字符 ASCII art。

    使用 ▀▄█░ 字符实现 2x 垂直分辨率，保持原始图片显示比例。

    Args:
        image_path: 输入图片路径
        output_path: 输出文本路径
        width: 输出宽度（字符数），高度自动计算为 width/2

    Notes:
        终端字符宽高比约为 0.5（字符宽度≈高度的0.5）。
        所以 height行 = width / 2 才能保持正方形显示。
        半块模式下每输出行对应2像素行，实现更高的垂直分辨率。
    """
    img = Image.open(image_path).convert('L')

    # 保持显示比例：宽度字符数 / 2 = 高度行数
    display_height = width // 2

    # 每行对应2像素行（半块模式）
    new_width = width
    new_height = display_height * 2

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    pixels = img.load()

    lines = []
    for y in range(0, new_height - 1, 2):
        line = []
        for x in range(new_width):
            upper = pixels[x, y]
            lower = pixels[x, y + 1]

            upper_norm = upper / 255
            lower_norm = lower / 255

            # 字符选择逻辑
            if upper_norm > 0.5 and lower_norm > 0.5:
                char = '█'  # 全亮
            elif upper_norm <= 0.5 and lower_norm <= 0.5:
                if upper_norm > 0.25 or lower_norm > 0.25:
                    char = '░'  # 半暗
                else:
                    char = ' '  # 全暗
            elif upper_norm > 0.5:
                char = '▀'  # 上亮下暗
            else:
                char = '▄'  # 上暗下亮

            line.append(char)
        lines.append(''.join(line))

    # 写入文件
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines), encoding='utf-8')

    print(f'✓ 已生成: {output_path}')
    print(f'  尺寸: {width}字符宽 x {display_height}行高')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='将图片转换为 Unicode 半块字符 ASCII art',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('image', type=str, help='输入图片路径')
    parser.add_argument('output', type=str, help='输出文本路径')
    parser.add_argument('--width', type=int, default=60, help='输出宽度（字符数），默认60')

    args = parser.parse_args()

    image_to_unicode_art_halfblock(args.image, args.output, args.width)


if __name__ == '__main__':
    main()