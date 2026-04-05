"""交互式终端入口 - Rich + questionary.

用法::

    python -m ui.interactive

或::

    python -m ui.interactive quick  # 快速开始
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
    """主循环."""
    # 检查快速开始参数
    if argv and len(argv) > 0 and argv[0] == "quick":
        quick_start()
        return 0

    try:
        while True:
            choice = show_main_menu()

            if choice in ("quit", "esc"):
                console.clear()
                console.print("\n[dim]再见! 👋[/dim]")
                return 0
            elif choice == "quick":
                quick_start()
            elif choice == "match":
                match_run()
            elif choice == "profile":
                profile_run()
            elif choice == "replay":
                replay_run()

    except KeyboardInterrupt:
        console.print("\n\n[dim]已退出[/dim]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
