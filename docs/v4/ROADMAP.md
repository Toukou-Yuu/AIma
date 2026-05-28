# AIma v4.1 / v4.2 / v4.3+ 后续路线图

日期：2026-05-27  
前提：当前仓库已达到 **v4.0 最小可信实验平台冻结版**，后续开发应建立在 `v4.0-freeze` tag 之上。

---

## 0. 总体路线

```text
v4.0：冻结实验平台地基
v4.1：实验分析增强版
v4.2：上下文压缩与长期记忆实验版
v4.3+：高级 Agent / 工程扩展
```

三阶段定位：

| 版本 | 核心目标 | 一句话概括 |
|---|---|---|
| v4.1 | 分析能力与 baseline 增强 | 让平台从“能跑实验”变成“能解释实验” |
| v4.2 | 上下文/记忆机制实验 | 进入论文主问题：上下文、压缩、记忆是否影响小模型决策 |
| v4.3+ | 高级 Agent 与工程扩展 | 工具调用、多进程、Native backend、实验控制台 |

---

# Part 1：v4.1 实验分析增强版

## 1. v4.1 目标

v4.1 不应大改基础架构，而是在 v4.0 基础上增强：

```text
1. M3 决策情境指标
2. 启发式麻将 baseline
3. Golden artifact regression tests
4. Aggregate/report 自动化
5. UI artifact viewer 增强
```

v4.1 的核心问题是：

> 不仅知道哪个 Agent 配置表现更好，还要知道它为什么更好。

---

## 2. v4.1-M1：M3 决策情境指标

### 2.1 背景

v4.0 的 M2 指标关注：

```text
胜负 / 分数 / 和牌 / 放铳 / 立直 / 副露
parse error / fallback / latency / tokens
```

但这些只能回答：

```text
这个 Agent 是否稳定？
```

不能回答：

```text
它在什么局面中做对/做错？
上下文和记忆到底影响了哪些决策？
```

v4.1 应新增 M3 决策情境指标。

---

### 2.2 SituationTagger

建议新增模块：

```text
src/metrics/situation/
  __init__.py
  tagger.py
  schema.py
  extractors.py
```

核心接口：

```python
@dataclass(frozen=True, slots=True)
class SituationTags:
    can_win: bool
    can_riichi: bool
    under_riichi_pressure: bool
    has_call_option: bool
    has_kan_option: bool
    is_last_tile_phase: bool
    discarded_dora: bool
    passed_win: bool
    riichi_declared_when_possible: bool
    fallback_used: bool
    context_truncated: bool
    memory_used: bool
```

输入：

```text
Decision record
Legal actions
Chosen action
Kernel state / observation
Decision diagnostics
```

输出写入：

```text
decisions.jsonl diagnostics.situation_tags
decision_metrics.csv
situation_summary.csv
```

---

### 2.3 第一批 M3 标签

v4.1 第一批建议实现：

| 标签 | 含义 |
|---|---|
| `can_win` | 当前 legal actions 中存在 RON / TSUMO |
| `passed_win` | 可和时没有选择和牌 |
| `can_riichi` | legal discard 中存在 declare_riichi |
| `riichi_declared_when_possible` | 可立直时选择立直 |
| `has_call_option` | 存在 CHI / PON / KAN response |
| `has_kan_option` | 存在 KAN |
| `under_riichi_pressure` | 其他玩家已立直 |
| `discarded_dora` | 选择的弃牌是宝牌或赤宝牌 |
| `fallback_used` | 该步使用 fallback |
| `parse_failed` | 该步解析失败 |
| `context_truncated` | prompt/context 被截断 |
| `memory_used` | memory injected tokens > 0 |

---

### 2.4 M3 聚合指标

新增 CSV：

```text
aggregate/situation_metrics.csv
aggregate/decision_situation_summary.csv
```

建议字段：

```text
experiment_id
job_id
match_id
seat
policy_id
total_decisions
can_win_count
passed_win_count
passed_win_rate
can_riichi_count
riichi_when_possible_count
riichi_when_possible_rate
under_riichi_pressure_count
fallback_under_pressure_count
memory_used_count
memory_used_rate
context_truncated_count
```

---

### 2.5 验收标准

- `SituationTagger` 有单元测试；
- `can_win / can_riichi / fallback_used / memory_used` 至少四类标签端到端写入 decisions；
- aggregate 产出 `situation_metrics.csv`；
- UI viewer 能展示每步 decision 的 situation tags。

---

## 3. v4.1-M2：启发式 baseline

### 3.1 背景

v4.0 有简单 baseline：

```text
RandomPolicy
FirstLegalPolicy
FixedHeuristicPolicy
LLMPolicy
```

v4.1 应补更有麻将意义的 baseline，以便论文对照。

---

### 3.2 推荐新增 policy

```text
src/policies/heuristic/
  shanten_greedy.py
  riichi_greedy.py
  call_balanced.py
  defense_basic.py
```

第一批：

| Policy | 行为 |
|---|---|
| `ShantenGreedyPolicy` | 优先选择能降低向听数的弃牌 |
| `RiichiGreedyPolicy` | 可立直时倾向立直 |
| `CallBalancedPolicy` | 简单判断是否吃碰以推进速度 |
| `DefenseHeuristicPolicy` | 他家立直后倾向打现物/字牌/低风险牌 |

---

### 3.3 注意事项

v4.1 的 heuristic baseline 不必很强，但必须：

```text
可解释
稳定
可复现
比 Random/FirstLegal 更像麻将
```

不要为了做强 baseline 引入复杂 AI。

---

### 3.4 验收标准

- 每个 policy 有单元测试；
- 每个 policy 可以跑 smoke；
- aggregate 能区分不同 policy；
- 至少新增一个 `examples/heuristic_baseline.yaml`；
- 文档说明 baseline 是简单启发式，不是强麻将 AI。

---

## 4. v4.1-M3：Golden artifact regression tests

### 4.1 背景

v4.0 已经有 E2E contract tests，但未来 prompt/context/metrics 改动会影响实验复现性。  
v4.1 应增加 golden tests。

### 4.2 Golden 文件建议

```text
tests/golden/v4_1_smoke/
  manifest.yaml
  summary.json
  metrics.json
  match_metrics.csv
  player_metrics.csv
  decisions_head.jsonl
  prompt_messages_head.jsonl
```

不建议把完整 5000 条 decision 都做 golden；可使用：

```text
head N lines
selected checkpoints
schema-normalized snapshot
```

避免因为时间戳、路径、git hash 导致频繁变动。

---

### 4.3 验收标准

- 有 golden smoke；
- 有 golden prompt rendering；
- 有 golden metrics summary；
- 变更 prompt/metrics schema 时必须显式更新 golden；
- golden 测试默认离线运行。

---

## 5. v4.1-M4：Aggregate / Report 增强

### 5.1 新增 report.md

建议：

```bash
python -m experiments.report --run runs/context_ablation_v1
```

产出：

```text
aggregate/report.md
aggregate/tables/*.csv
aggregate/figures/*.png  # 可选，v4.1 后期
```

第一版 report 只需要 Markdown：

```text
实验配置摘要
模型/Policy 列表
总 match 数
平均 ranking / score
fallback / parse error
token usage
memory usage
situation metrics
主要异常 match/job 列表
```

---

### 5.2 验收标准

- 能对 smoke run 生成 report.md；
- 能对 context/memory ablation run 生成分组统计；
- report 不依赖 notebook。

---

## 6. v4.1-M5：UI Viewer 增强

### 6.1 目标

UI 仍然不参与实验运行，只增强 artifact 浏览能力。

建议新增：

```text
实验列表页
job 列表页
match summary 页
decision trace 页
prompt viewer
memory section viewer
metrics viewer
situation tag filter
```

### 6.2 验收标准

- UI 能按 experiment/job 选择；
- 能查看某一步 decision 的：
  - observation
  - public_history
  - memory
  - prompt
  - raw_output
  - final_action
  - situation tags
- UI 不调用 LLM，不推进 kernel。

---

# Part 2：v4.2 上下文压缩与长期记忆实验版

## 7. v4.2 目标

v4.2 是论文主方向的核心版本：

> 系统评估上下文范围、上下文压缩、被动记忆注入对小模型 LLM Agent 决策稳定性与对局表现的影响。

---

## 8. v4.2-C1：上下文范围实验

### 8.1 变量

```text
stateless
per_turn
per_hand
per_match
```

### 8.2 实验模板

```text
same model
same seed plan
same policy except context scope
same prompt template
memory off
```

### 8.3 指标

```text
M2 指标
M3 情境指标
token usage
fallback rate
parse error rate
rank / score
passed_win_rate
riichi_when_possible_rate
```

### 8.4 验收标准

- 提供 `examples/context_scope_ablation.yaml`;
- 能自动生成 report；
- 每个 run 记录 prompt/context diagnostics。

---

## 9. v4.2-C2：上下文压缩实验

### 9.1 压缩策略

v4.2 应正式实现：

```text
none
event_window
collapse
compact_summary
token_budgeted
```

不要把 v4.0 的 `autocompact` stub 直接拿来做实验。

---

### 9.2 CompressionPolicy 接口

建议：

```python
class CompressionPolicy(Protocol):
    name: str

    def compress(self, events: Sequence[ContextEvent], budget: TokenBudget) -> CompressedContext:
        ...
```

`CompressedContext`：

```python
@dataclass(frozen=True, slots=True)
class CompressedContext:
    text: str
    raw_event_count: int
    kept_event_count: int
    dropped_event_count: int
    compression_ratio: float
    diagnostics: dict[str, Any]
```

---

### 9.3 验收标准

- 每个 compression policy 有单元测试；
- diagnostics 记录 dropped/kept event；
- 不同 compression policy 产出的 prompt 不同；
- context ablation 能稳定运行。

---

## 10. v4.2-M1：长期记忆机制

### 10.1 Memory 层次

v4.2 应完善：

```text
HandMemory
MatchMemory
PersistentMemory
OpponentMemory
```

v4.0 已具备 passive injection 地基，v4.2 需要让生命周期更有研究价值。

---

### 10.2 写入时机

建议：

```text
on_decision       可选：记录重要决策
on_hand_end       写入本局摘要
on_match_end      写入半庄摘要
after_experiment  可选：写入跨实验 summary
```

---

### 10.3 摘要生成方式

第一版不要使用 LLM 自动总结，先用结构化摘要：

```text
Hand 3 ended by ron.
Winner: seat2.
Loser: seat1.
Scores: ...
Riichi players: ...
Notable events: ...
```

后续再加 LLM summary。

---

### 10.4 Memory ablation

变量：

```text
memory off
hand summary
match summary
persistent summary
opponent summary
```

必须保证：

```text
只有 memory 变量变化，其它 prompt/context/model 不变。
```

---

### 10.5 验收标准

- `examples/memory_ablation.yaml`;
- memory off/on prompt 差异稳定；
- memory diagnostics 可聚合；
- memory usage 能进入 M3/M2 report。

---

## 11. v4.2-M2：被动检索式 MemoryReader

这是可选增强，不是 LLM tool call。

### 11.1 设计边界

允许：

```text
系统侧根据当前局面检索 memory top-k
把结果被动注入 prompt
```

不允许：

```text
LLM 主动 tool call 检索 memory
多轮 tool-use 决策
```

### 11.2 第一版实现

可以先做非向量检索：

```text
recent_k
same_opponent
same_situation_tag
same_hand_phase
```

向量库可以放到 v4.3+。

---

# Part 3：v4.3+ 高级 Agent 与工程扩展

## 12. 多进程 / Job Queue

v4.0 是串行 runner。  
v4.3 可加入：

```text
worker
job retry
resume
parallel seed execution
resource lock
GPU model server concurrency control
```

核心要求：

```text
artifact 不冲突
SQLite 写入安全
失败 job 可恢复
```

---

## 13. Tool-call Agent

当前 C1 固定流水线不支持 tool call。  
v4.3+ 可单独设计 ToolAgent：

```text
LLM decide whether to call tool
tool execution
tool result injection
second model call
final action grounding
```

可能工具：

```text
memory_search
shanten_calculator
danger_estimator
tile_efficiency_analyzer
score_estimator
```

注意：

> Tool-call Agent 是新研究方向，不应混入 v4.2 的被动 memory ablation。

---

## 14. Graph Agent

暂不推荐近期做。  
只有当需要：

```text
self-reflection
multi-step planning
opponent modeling loop
tool planning
```

再考虑。

---

## 15. Native backend

v4.3+ 可实现：

```text
LlamaCppNativeBackend
VLLMNativeBackend
```

但 v4.0/v4.1/v4.2 优先使用：

```text
OpenAI-compatible endpoint
```

---

## 16. UI P3：实验控制台

v4.0/v4.1 UI 是 artifact viewer。  
v4.3+ 可推进到：

```text
启动实验
实时观战
查看运行中 trace
暂停/恢复 job
查看模型输出
```

但要保持：

```text
实验核心不依赖 UI
UI 只是控制和展示层
```

---

# Part 4：推荐论文路线

## 17. 第一篇论文建议题目方向

建议第一篇不要写“麻将 AI 能力 benchmark”，而是写：

> Context and Memory Management for Small LLM Agents in a Rule-Constrained Imperfect-Information Game

中文理解：

> 强规则约束不完全信息博弈中小模型 LLM Agent 的上下文与记忆机制研究。

---

## 18. 推荐实验路线

### 实验 1：Context scope ablation

```text
stateless
per_hand
per_match
```

看：

```text
fallback rate
parse error
rank/score
passed_win
riichi_when_possible
token usage
```

### 实验 2：Context compression ablation

```text
none
event_window
collapse
compact_summary
```

看：

```text
token cost vs decision reliability
```

### 实验 3：Passive memory ablation

```text
memory off
hand memory
match memory
opponent memory
```

看：

```text
memory injection 是否改善长期稳定性
是否增加 token 成本
是否导致更多 hallucination / parse error
```

### 实验 4：Agent mechanism ablation

```text
strict JSON
repair once
fallback first legal
fallback random
memory on/off
```

看：

```text
reliability and robustness
```

---

## 19. 论文中应避免的表述

不要说：

```text
AIma 实现完整真实雀魂级立直麻将
AIma 的 Agent 达到强麻将水平
长期记忆一定提高麻将水平
```

建议说：

```text
AIma implements a declared Riichi Mahjong ruleset sufficient for controlled LLM-agent experiments.
We study how context and passive memory mechanisms affect decision reliability and game-level outcomes.
```

---

# Part 5：v4.1 启动建议

进入 v4.1 前，建议先完成：

```text
1. 打 tag：v4.0-freeze
2. 更新 docs/v4
3. 更新 README
4. 固定 smoke / memory_passive 示例
5. 保存一份 v4.0 freeze smoke artifact 作为后续 golden seed 候选
```

v4.1 第一批任务建议：

```text
Stage 1：SituationTagger
Stage 2：M3 aggregate
Stage 3：ShantenGreedy / RiichiGreedy baseline
Stage 4：Golden artifact tests
Stage 5：report.md generator
Stage 6：UI viewer 增强
```

---

## 20. 总结

v4.1/v4.2 不应再大改 v4.0 地基。

后续路线应遵循：

```text
v4.1：解释实验结果
v4.2：正式研究上下文/记忆
v4.3+：高级 Agent 和工程扩展
```

这样 AIma 会从“能跑实验的平台”逐步成为“能支撑论文分析的平台”。
