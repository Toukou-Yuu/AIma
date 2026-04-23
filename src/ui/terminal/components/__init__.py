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
- meld_display: MeldDisplay 副露显示组件
- token_budget_display: TokenBudgetDisplay 上下文 token 压力组件
- character_card: 角色卡片渲染组件
"""

from .character_card import render_all_cards, render_character_card
from .event_formatter import EventFormatter
from .hand_display import HandDisplay
from .layout_builder import LayoutBuilder
from .meld_display import MeldDisplay
from .name_resolver import NameResolver
from .render import TileRenderer
from .stats_tracker import StatsTracker
from .tiles import (
    _WIND_NAMES,
    parse_hand_tiles,
    tile_to_rich,
    tiles_to_display,
    wind_with_seat,
)
from .token_budget_display import TokenBudgetDisplay

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
    'MeldDisplay',
    'NameResolver',
    'TokenBudgetDisplay',
    'tiles_to_display',
    # 角色卡片
    'render_character_card',
    'render_all_cards',
]
