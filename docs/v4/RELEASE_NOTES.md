# AIma v4.0-freeze 发布说明

发布日期：2026-05-27

---

## 版本定位

v4.0-freeze 是 **最小可信实验平台冻结版**。

核心能力：
- 能运行实验并生成标准 artifact
- 能聚合 M2 指标
- 能写入并重建 SQLite index
- PromptRuntime / ContextEvent / ModelBackend / Memory 主链路已接通
- UI artifact viewer 可读取 run/job/artifact

后续版本将在此基础上增强分析能力，不改变实验平台地基。

---

## 实验平台入口

```bash
# 运行实验
PYTHONPATH=src python -m experiments.run --config examples/smoke.yaml --output runs

# 聚合分析
PYTHONPATH=src python -m experiments.aggregate --run runs/smoke

# 重建索引
PYTHONPATH=src python -m experiments.index --rebuild runs
```

---

## Artifact 目录结构

```
runs/{experiment_id}/
  manifest.yaml          # 配置快照
  jobs.jsonl            # 作业记录
  jobs/{job_id}/
    summary.json        # 对局摘要
    decisions.jsonl     # 决策记录
    events.jsonl        # 事件记录
    replay.json         # 牌谱
  aggregate/
    report.md           # 分析报告
    reliability_summary.json
    match_metrics.csv
    player_metrics.csv
  runs.db               # SQLite 索引
```

---

## 已验证的测试状态

- **2389 passed, 9 skipped**
- Live DeepSeek API 测试验证通过（12.31s）

Skipped 测试均为设计意图：
- Live API 测试需环境变量 `RUN_LIVE_LLM_TESTS=1`
- SQLite 测试需预先运行的实验数据

---

## v4.0 能力边界

### 已支持
| 功能 | 状态 |
|------|------|
| 固定流水线 Agent | ✅ |
| Prompt DSL | ✅ |
| ContextBuilder | ✅ |
| Memory passive injection | ✅ |
| OpenAI-compatible backend | ✅ |
| Dummy/Mock/Replay backend | ✅ |
| 实验运行 + aggregate + index | ✅ |
| M2 指标 | ✅ |
| UI artifact viewer | ✅ |

### 不支持（v4.1+计划）
| 功能 | 计划版本 |
|------|----------|
| Native llama.cpp/vLLM backend | v4.3+ |
| 完整 GameState snapshots | v4.1 |
| autocompact 正式实现 | v4.2 |
| Tool-call Agent | v4.3+ |
| 实验控制台 UI | v4.3+ |
| M3 情境指标 | v4.1 |

---

## 本版本修复的关键问题

### P0 修复（5项）
1. MatchRunner 自然终局语义修正
2. Artifact contract 测试自包含
3. SQLite runtime index 更新
4. Debug artifact 配置实现
5. Memory lifecycle 闭环

### P1 修复（4项）
1. YAML `off` 布尔陷阱
2. Native backend 文档修正
3. ContextEvent import 清理
4. autocompact 实验性 warning

---

## 后续路线

详见 [ROADMAP](ROADMAP.md)

- **v4.1**：分析能力增强（M3指标、启发式baseline、golden tests）
- **v4.2**：上下文压缩与长期记忆实验
- **v4.3+**：高级Agent与工程扩展