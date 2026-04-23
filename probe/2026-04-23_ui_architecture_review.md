# UI模块架构审查报告

> 审查日期: 2026-04-23

## 修复任务清单

- [x] 修复 live 手牌树中“理由”分支与“副露/牌河”分支断开的显示问题。
- [x] 将上下文 token 诊断从单个瞬时面板改为按座位持久化展示。
- [x] 将点数与和了统计合并到每个角色手牌行，并保持缩进对齐。
- [x] 精简右侧栏，移除独立“和了/上下文”面板，仅保留局况和事件。
- [x] 将事件区域改为持久化历史事件展示，提升可见事件数量。
- [x] 消除 `LiveMatchViewer` 对 `StatsTracker` 私有字段的直接访问。
- [ ] 后续拆分 `tui_screens.py`，引入 Screen/ViewModel 分层。
- [ ] 后续将连接探测与数据加载下沉到 service/repository 层。
- [ ] 后续清理 viewer/layout_builder 中为旧测试保留的兼容方法。

## 一、模块结构概览

UI模块分为三个主要区域：
- `ui.terminal` - Rich实时观战器（组件化架构）
- `ui.terminal.components` - 可复用渲染组件
- `ui.interactive` - Textual全屏TUI应用

---

## 二、抽象度分析

### ✅ 优秀设计

**`ui.terminal.components` 组件化架构**：依赖注入模式清晰，职责分离良好：

```
TileRenderer → 牌面渲染
HandDisplay → 手牌显示（依赖 TileRenderer + NameResolver）
MeldDisplay → 副露显示（依赖 NameResolver）
StatsTracker → 统计追踪
EventFormatter → 事件格式化
LayoutBuilder → 布局构建（聚合上述所有组件）
```

### ❌ 抽象缺陷

**1. `tui_screens.py` (1617行单文件)**：13个Screen类堆叠在单一文件中，每个Screen内含大量私有渲染方法：

```python
# 每个Screen都有类似的重复结构
class MatchSetupScreen(BaseScreen):
    def _refresh_summary(self) -> None: ...
    def _refresh_player_buttons(self) -> None: ...
    def _seat_model_rows(self, ...) -> list: ...
    # 业务逻辑与渲染逻辑混杂
```

**问题**：缺少Screen级别的组件抽象层，每个Screen直接实现业务逻辑+渲染逻辑，违反关注点分离。

**2. 缺少View/ViewModel分离**：`MatchSetupScreen`等同时管理表单状态、数据验证、LLM配置检查和UI渲染，职责过重。

---

## 三、耦合度分析

### ❌ 高耦合问题

**1. UI直接依赖业务层**：

```python
# character_card.py:25-28
from llm.agent.memory import load_memory
from llm.agent.profile import PlayerProfile, load_profile
from llm.agent.stats import load_stats

# match_session.py:18-28
from llm.config import LLMRuntimeConfig, MatchEndCondition, ...
from llm.protocol import build_seat_clients
from llm.runner import RunResult, run_llm_match
```

UI组件直接调用LLM模块的数据加载函数，形成**跨层穿透**。

**2. `data.py` 混合UI数据装配与网络探测**：

```python
# data.py:244-326 - 在UI数据层直接做HTTP探测
def _probe_connection_status(..., timeout_sec: float = 1.5):
    import httpx
    response = client.get(url, headers=headers)
    ...
```

网络探测逻辑应位于服务层，而非UI数据装配层。

**3. Session模型职责边界模糊**：`MatchSession`和`ReplaySession`同时承担：
- 状态机管理（`MatchSessionState`枚举）
- 线程调度（`threading.Thread`）
- Viewer组合（`LiveMatchViewer`）
- 回调处理（`_on_step`）
- 日志管理（`_SessionLoggingContext`）

这是典型的**上帝类(God Class)**倾向。

---

## 四、复用度分析

### ✅ 可复用组件

- `chrome.py` - 统一视觉组件库（`render_page_header`, `render_summary_panel`等）
- `tiles.py` - 牌面渲染基础函数
- `token_diagnostics.py` - 共享格式化助手

### ❌ 复用缺陷

**1. 重复渲染模式**：`tui_screens.py`和`match_flow.py`各自定义了几乎相同的函数：

```python
# tui_screens.py:71-85
def _format_timestamp(timestamp: float | None) -> str: ...
def _format_duration(seconds: float | None) -> str: ...

# match_flow.py:36-52 - 几乎相同的定义
def _format_timestamp(timestamp: float | None) -> str: ...
def _format_duration(seconds: float | None) -> str: ...
```

**2. Textual Screen缺少组件库**：每个Screen的`compose()`方法都手动构建widget树，无共享的表单组件、列表组件抽象。

**3. Style定义重复**：

```python
# framework.py:122-129 和 Prompt._style():163-175
# 两处几乎相同的 prompt_toolkit Style 定义
Style.from_dict({
    "selected": "bold bg:#16324f #8de1ff",
    ...
})
```

---

## 五、兼容性补丁（屎山要素）

### ⚠️ 明确标记的兼容层

**`viewer.py:172-377`**：

```python
# === 公共接口（向后兼容） ===

# === 内部方法（保留用于测试兼容） ===

def _hand_to_rich(self, hand, dora_tiles: set) -> Panel:
    """手牌渲染（兼容旧测试）。"""
    return self._renderer.render_hand(hand, dora_tiles)

def _river_to_str(self, river, seat: int, ...) -> Panel:
    """牌河渲染（兼容旧测试）。"""
    ...
```

这是典型的**测试驱动兼容补丁**，表明旧测试直接调用内部实现，导致架构被锁定。

**其他兼容性痕迹**：

```python
# layout_builder.py:171
def _render_header(self, state, active_seat) -> Group:
    """兼容旧测试：返回场况摘要。"""

# hand_display.py:45
def format_melds(self, melds, owner_seat, dealer_seat) -> str:
    """格式化完整副露描述。"""
    del dealer_seat  # 参数已删除但签名保留

# data.py:545
def load_roster_entries(config_path, players_dir) -> tuple:
    del players_dir  # 预留给将来多路径扩展
```

### ⚠️ 封装破坏

```python
# viewer.py:217 - 直接访问私有成员
self._wins = list(self._stats_tracker._wins)  # _wins是私有属性
self._rounds = self._stats_tracker._rounds    # _rounds是私有属性
```

Viewer为了获取统计数据，直接穿透到StatsTracker的私有属性。

### ⚠️ 导出不一致

```python
# ui/terminal/__init__.py
"""Rich 终端实时观战."""
__all__ = []  # 空导出

# 但实际下一行又导入了viewer.py的类
# 这造成模块文档与实际行为不匹配
```

---

## 六、改进建议

| 问题 | 建议 |
|------|------|
| `tui_screens.py`过大 | 拆分为独立Screen模块 + 共享UI组件库 |
| UI穿透业务层 | 引入Service/Repository层，UI只依赖DTO |
| Session职责过重 | 拆分为：状态机、线程调度器、回调接口 |
| 兼容测试补丁 | 重构测试，使用公共API而非内部方法；删除兼容层 |
| 重复渲染函数 | 提取到`chrome.py`或新建`ui/formatting.py` |
| 封装破坏 | StatsTracker提供`get_wins()`/`get_rounds()`公共方法 |

---

## 七、总结评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 抽象度 | **B** | terminal.components优秀；interactive Screen层欠佳 |
| 耦合度 | **C** | 多处跨层穿透；Session类职责边界模糊 |
| 复用度 | **B-** | chrome/tiles组件良好；Textual层缺少组件抽象 |
| 屎山风险 | **中** | 存在明确标记的兼容补丁；需及时清理 |

**核心风险**：viewer.py的"兼容旧测试"层会持续积累，建议优先重构测试以解除架构锁定。
