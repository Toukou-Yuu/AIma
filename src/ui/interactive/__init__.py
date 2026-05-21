"""交互式终端模块 - Textual 全屏 TUI.

通过 start.py 启动::

    python start.py           # 交互式菜单
    python start.py quick     # 快速演示
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 不在顶层导入依赖 textual 的模块，避免阻塞非 TUI 场景


def main(argv: list[str] | None = None) -> int:
    """主循环 - 由 start.py 调用."""
    try:
        from textual.app import App
        from .tui_app import AImaTextualApp
    except ImportError:
        print("错误: 需要安装 textual 才能运行交互式 TUI", file=sys.stderr)
        print("请执行: pip install textual", file=sys.stderr)
        return 1

    start_mode = "quick" if argv and len(argv) > 0 and argv[0] == "quick" else None
    app: App[None] = AImaTextualApp(start_mode=start_mode)
    app.run()
    return 0
