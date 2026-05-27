# v4 迁移指南

## 破坏性重构声明

> **v4.0-experiment-platform-alpha** 是破坏性重构版本。
>
> 旧版内部 API（`llm.runner`、`PlayerAgent`、旧 CLI 入口、旧 UI 运行逻辑）将被替代，**不保证向后兼容**。

## 旧版废弃路径

以下模块将被替代或删除：

| 旧模块 | 状态 | 替代方案 |
|--------|------|----------|
| `llm.runner` | 废弃 | `arena.match_runner` + `experiments.runner` |
| `llm/agent/core.py` (PlayerAgent) | 废弃 | `agents.pipeline` + `policies.llm_policy` |
| `llm/agent/prompt_builder.py` | 废弃 | `prompts.renderer` + `prompts.sections` |
| `llm/agent/decision_parser.py` | 废弃 | `agents/components/parser.py` + `grounding.py` |
| `llm/agent/memory.py` | 废弃 | `memory/schemas.py` + `readers.py` + `writers.py` |
| `llm/agent/context*.py` | 废弃 | `context/builders.py` |
| `llm/adapters/*` | 废弃 | `models/backends/*` |
| `llm/agent/stats*.py` | 废弃 | `metrics/*` + artifact writer |
| 旧 `python -m llm --dry-run` | 废弃 | `python -m experiments.run --config ...` |
| 旧 UI interactive 运行入口 | 暂保留 | v4 UI 改为 artifact viewer |

## v4 新入口

```bash
# 运行实验
python -m experiments.run --config examples/smoke.yaml

# 聚合指标
python -m experiments.aggregate --run runs/smoke

# 重建索引
python -m experiments.index --rebuild runs
python -m experiments.index --rebuild runs/smoke  # 也支持单个 run dir

# 查看实验产物
python -m ui.viewer --run runs/smoke
```

## kernel 规则冻结

v4 重构期间 kernel 规则语义冻结：

- `kernel/engine/apply.py` 状态机不变
- `kernel/scoring/*` 计分公式不变
- `kernel/win_shape/*` 和牌形判定不变
- 允许新增 `GameEngine` 门面，但不改规则

详见 `RULE_SCOPE.md`。

## configs/players 处理

v4 实验默认 `no_persist: true`：

- 实验运行**不写入** `configs/players/*/memory.json`
- 实验运行**不写入** `configs/players/*/stats.json`
- 实验运行**不写入** `configs/players/*/conversations/`

如需 persistent memory，应明确配置并使用独立输出目录。

## 测试迁移

| 旧测试 | 处理 |
|--------|------|
| `tests/test_engine.py` 等 kernel 测试 | 保留，作为规则 gate |
| `tests/test_llm_*` | 按新架构重写 |
| `tests/test_ui.py` | 旧 UI 测试可保留为 legacy，v4 viewer 另写 |

## 迁移风险

1. **局间推进逻辑**：拆 `llm.runner` 时容易出错，由 arena runner tests 保护
2. **Prompt 语义**：迁移时可能改变 LLM 输入，需保存 prompt version
3. **Memory 污染**：默认 `no_persist` 防止实验写入玩家 profile
4. **SQLite 不一致**：必须支持 `rebuild_index`

## 迁移完成标志

- v4 smoke config 能跑通
- 旧 `llm.runner` 不再是核心路径
- 实验运行不 import `ui`
- Artifact 完整生成
- SQLite 可重建
- UI viewer 只读 artifact
- M2 metrics 可聚合
