#!/usr/bin/env python3
"""运行 Demo 牌谱演示。"""

import subprocess
import sys
from pathlib import Path


def main():
    """主函数：运行牌谱回放。"""
    demo_dir = Path(__file__).parent
    json_path = demo_dir / "complex_game.json"

    if not json_path.exists():
        print(f"错误: 牌谱文件不存在: {json_path}")
        print("请先运行生成脚本或直接创建牌谱")
        sys.exit(1)

    print(f"播放牌谱: {json_path}")
    print("按 Ctrl+C 退出")
    print()

    # 运行回放
    cmd = [
        sys.executable, "-m", "llm",
        "--replay", str(json_path),
        "--watch",
        "--watch-delay", "0.3",
    ]

    try:
        subprocess.run(cmd, cwd=demo_dir.parent)
    except KeyboardInterrupt:
        print("\n\n已停止播放")


if __name__ == "__main__":
    main()
