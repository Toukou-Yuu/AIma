# v4.0 UI Viewer 文档

## 概述

v4.0 UI 是 **artifact viewer**，不是实验控制台。

核心定位：
- 查看已运行的实验产物
- 不调用 LLM
- 不推进 kernel 状态

---

## UI 功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 主菜单首页 | ✅ | 快速入口 |
| demo演示 | ✅ | Dry-run 观战 |
| 开始对局 | ✅ | LLM/角色配置 |
| 角色管理 | ✅ | 查看/创建角色 |
| 牌谱回放 | ✅ | 浏览并回放历史牌谱 |
| 实验列表 | ❌ | v4.3+ |
| job详情页 | ❌ | v4.3+ |
| decision trace | ❌ | v4.3+ |
| prompt viewer | ❌ | v4.3+ |
| 实验控制台 | ❌ | v4.3+ |

---

## 启动方式

```bash
python start.py        # 进入主菜单
python start.py quick  # 直接进入demo配置页
```

---

## 技术栈

- **Textual**：全屏 TUI 框架
- **Rich**：牌桌/角色卡片渲染
- **Questionary**：辅助交互

---

## v4.0 边界

### 不依赖 UI 的功能

实验平台核心功能不依赖 UI：

```bash
PYTHONPATH=src python -m experiments.run ...
PYTHONPATH=src python -m experiments.aggregate ...
PYTHONPATH=src python -m experiments.index ...
```

### UI 不参与实验运行

UI 只用于：
- 查看实验结果（通过 RunDataSource）
- 观看历史对局回放
- 配置角色和 LLM profile

---

## v4.3+ 扩展计划

| 功能 | 说明 |
|------|------|
| 实验列表页 | 浏览 runs/ 目录 |
| job详情页 | 查看单个 match 摘要 |
| decision trace | 查看每步决策详情 |
| prompt viewer | 查看 prompt_messages.jsonl |
| memory viewer | 查看 memory_snapshot.jsonl |
| metrics viewer | 查看 aggregate 指标 |
| 实验控制台 | 启动/暂停/恢复实验 |

---

## 数据来源

UI 通过 `RunDataSource` 读取 artifact：

```python
from ui.interactive.data import RunDataSource

source = RunDataSource("runs")
experiments = source.list_experiments()
jobs = source.list_jobs("smoke")
```

**不直接修改 artifact**。