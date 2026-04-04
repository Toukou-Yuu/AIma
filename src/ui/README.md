# UI 模块

AIma 的用户界面组件，包括 Rich 终端实时观战和交互式菜单。

## 文件说明

| 文件 | 说明 |
|------|------|
| `terminal_rich.py` | Rich 终端实时观战渲染器 |
| `interactive.py` | 交互式终端入口（Rich + questionary） |

## 交互式终端

### 启动

```bash
# 启动交互式菜单
python -m ui.interactive

# 快速开始（Dry-run 演示）
python -m ui.interactive quick
```

### 功能

**主菜单**
- 🎮 **快速开始** - Dry-run 演示，无需 API Key
- 🀄 **开始对局** - 选择角色进行对战
- 👤 **角色管理** - 查看和创建角色
- 📺 **牌谱回放** - 回放历史牌谱

**角色创建向导**

支持 4 种人格模板：
- 🗡️ 进攻型 - 积极鸣牌、早立直
- 🛡️ 防守型 - 现物优先、安全牌
- ⚖️ 平衡型 - 攻守兼备
- 🎭 变化型 - 风格多变

自动初始化：
- `profile.json` - 角色配置
- `stats.json` - 统计数据
- `memory.json` - 记忆数据

### 依赖

```bash
pip install rich questionary
```

或

```bash
pip install -e ".[rich]"
```

## Rich 终端观战

### 用法

```python
from ui.terminal_rich import LiveMatchViewer

viewer = LiveMatchViewer(delay=0.5)
viewer.run(result)
```

### 命令行

```bash
# 实时观战
python -m llm --dry-run --watch

# 从牌谱回放
python -m llm --replay logs/replay/20250405.json --watch
```

## 显示效果

```
┌─────────────────────────────────────────────────────────────────┐
│ 场况                                                            │
├─────────────────────────────────────────────────────────────────┤
│ 步数  45/500         东家  25000                                │
│ 局    東風1局        南家  24000                                │
│ 本场  0              西家  23500 ◄                              │
│ 供托  0              北家  27500                                │
│ 余牌  62                                                        │
│ 宝牌指示器  5m                                                  │
└─────────────────────────────────────────────────────────────────┘
```
