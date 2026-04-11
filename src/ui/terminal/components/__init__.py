"""终端组件.

提供可复用的渲染组件，用于构建 Rich 终端观战界面。

组件列表：
- tiles: 牌面渲染基础函数
- render: TileRenderer 牌面渲染器
- hand_display: HandDisplay 手牌显示组件
- stats_tracker: StatsTracker 统计追踪组件
- event_formatter: EventFormatter 事件格式化组件
- layout_builder: LayoutBuilder 布局构建组件
- name_resolver: NameResolver 名字解析组件
"""

# 基础函数
from .tiles import tile_to_rich, wind_with_seat, parse_hand_tiles, _WIND_NAMES

# 组件类
from .render import TileRenderer
from .hand_display import HandDisplay
from .stats_tracker import StatsTracker
from .event_formatter import EventFormatter
from .layout_builder import LayoutBuilder
from .name_resolver import NameResolver

__all__ = [
    # 基础函数
    'tile_to_rich',
    'wind_with_seat',
    'parse_hand_tiles',
    '_WIND_NAMES',
    # 组件类
    'TileRenderer',
    'HandDisplay',
    'StatsTracker',
    'EventFormatter',
    'LayoutBuilder',
    'NameResolver',
]