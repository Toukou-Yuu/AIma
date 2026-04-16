"""交互式终端模块 - Rich + questionary.

通过 start.py 启动::

    python start.py           # 交互式菜单
    python start.py quick     # 快速演示
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保能找到 src 下的模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from rich.console import Console
except ImportError as e:
    print(f"需要 rich: pip install rich ({e})", file=sys.stderr)
    raise SystemExit(1)

try:
    import questionary
except ImportError as e:
    print(f"需要 questionary: pip install questionary ({e})", file=sys.stderr)
    raise SystemExit(1)

from .main_menu import show_main_menu
from .match_setup import quick_start, run as match_run
from .profile_manager import run as profile_run
from .replay import run as replay_run

console = Console()


def main(argv: list[str] | None = None) -> int:
    """主循环 - 由 start.py 调用."""
    # 检查快速开始参数
    if argv and len(argv) > 0 and argv[0] == "quick":
        quick_start()
        return 0

    try:
        while True:
            choice = show_main_menu()

            if choice == "quit":
                console.clear()
                console.print("\n[dim]再见! 👋[/dim]")
                return 0
            if choice == "quick":
                quick_start()
            elif choice == "match":
                match_run()
            elif choice == "profile":
                profile_run()
            elif choice == "replay":
                replay_run()
    except KeyboardInterrupt:
        console.print("\n[dim]已中断[/dim]")
        return 130
