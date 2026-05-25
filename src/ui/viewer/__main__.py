"""UI artifact viewer - CLI 入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(
        prog="python -m ui.viewer",
        description="AIma 对局回放查看器",
    )
    parser.add_argument(
        "--run",
        type=Path,
        default=Path("runs"),
        help="对局运行根目录路径 (默认: runs)",
    )
    parser.add_argument(
        "--job",
        type=str,
        default=None,
        help="对局 Job ID (可选，不指定则显示实验列表)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        help="初始步数 (默认 0)",
    )

    args = parser.parse_args(argv)

    # 延迟导入 Textual 依赖
    try:
        from ui.viewer.app import ViewerApp
    except ImportError as e:
        print(f"错误: 无法加载 viewer 模块: {e}", file=sys.stderr)
        return 1

    app = ViewerApp(
        run_dir=args.run,
        job_id=args.job,
        initial_step=args.step,
    )
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())