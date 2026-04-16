"""交互式终端模块 - Textual 全屏 TUI.

通过 start.py 启动::

    python start.py           # 交互式菜单
    python start.py quick     # 快速演示
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from textual.app import App
except ImportError as e:
    print(f"需要 textual: pip install '.[rich]' ({e})", file=sys.stderr)
    raise SystemExit(1)

from .tui_app import AImaTextualApp


def main(argv: list[str] | None = None) -> int:
    """主循环 - 由 start.py 调用."""
    start_mode = "quick" if argv and len(argv) > 0 and argv[0] == "quick" else None
    app: App[None] = AImaTextualApp(start_mode=start_mode)
    app.run()
    return 0
