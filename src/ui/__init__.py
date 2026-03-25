"""桌面渲染（PIL）：拼接牌图生成局面 PNG。

不含 Rich / 终端 Unicode 牌面；预览请运行 ``demo.py`` 生成 ``output.png`` 后用看图软件打开。
"""

from .render import TableRenderer
from .tiles import TileImageCache, tile_to_filename

__all__ = ["TableRenderer", "TileImageCache", "tile_to_filename"]
