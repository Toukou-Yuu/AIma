# AIma v4 文档导航

## 版本状态

**v4.0-freeze** - 最小可信实验平台冻结版

> v4.0 是面向 LLM Agent 立直麻将实验的最小可信平台，支持固定流水线 Agent、Prompt DSL、被动记忆注入、实验 artifact、SQLite index、M2 指标和 replay/artifact viewer。

---

## 文档分类

### 入口文档
| 文档 | 内容 |
|------|------|
| [RELEASE_NOTES](RELEASE_NOTES.md) | v4.0 freeze 发布说明 |
| [ROADMAP](ROADMAP.md) | v4.1/v4.2/v4.3 后续路线 |

### 核心概念
| 文档 | 内容 |
|------|------|
| [ARCHITECTURE](ARCHITECTURE.md) | 模块边界与架构 |
| [EXPERIMENTS](EXPERIMENTS.md) | 实验运行与配置 |
| [CONFIG_SCHEMA](CONFIG_SCHEMA.md) | YAML配置字段解释 |

### 数据格式
| 文档 | 内容 |
|------|------|
| [ARTIFACTS](ARTIFACTS.md) | 产物文件格式 |
| [METRICS](METRICS.md) | M2 指标定义 |

### Agent机制
| 文档 | 内容 |
|------|------|
| [MEMORY](MEMORY.md) | Memory被动注入机制 |
| [CONTEXT_PROMPT](CONTEXT_PROMPT.md) | Context范围与Prompt DSL |
| [AGENT_PIPELINE](AGENT_PIPELINE.md) | Agent流水线说明 |

### 边界说明
| 文档 | 内容 |
|------|------|
| [BACKENDS](BACKENDS.md) | 模型后端类型与限制 |
| [UI_VIEWER](UI_VIEWER.md) | UI viewer边界（v4.3+扩展） |
| [TESTING](TESTING.md) | 测试分层与markers |

### 迁移指南
| 文档 | 内容 |
|------|------|
| [MIGRATION](MIGRATION.md) | v3 → v4 迁移说明 |

---

## 快速开始

```bash
# 运行实验
PYTHONPATH=src python -m experiments.run --config examples/smoke.yaml --output runs

# 聚合分析
PYTHONPATH=src python -m experiments.aggregate --run runs/smoke

# 重建索引
PYTHONPATH=src python -m experiments.index --rebuild runs
```

---

## v4.0 能力边界

### 已支持
- 固定流水线 Agent（无tool-call）
- Prompt DSL + ContextBuilder
- Memory passive injection（off/passive）
- 实验运行 + artifact + aggregate + index
- M2 指标聚合
- UI artifact viewer（只读）
- OpenAI-compatible backend

### 不支持
- Native llama.cpp/vLLM backend（使用OpenAI-compatible endpoint代替）
- 完整 GameState snapshots（v4.1计划）
- autocompact正式实现（实验性stub）
- Tool-call Agent（v4.3+计划）
- 实验控制台UI（v4.3+计划）

---

## 后续版本

详见 [ROADMAP](ROADMAP.md)