#!/usr/bin/env python3
"""AIma 启动入口.

用法::

    python start           # 启动交互式菜单
    python start quick     # 快速开始 Dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保能找到 src 下的模块
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ui.interactive import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
