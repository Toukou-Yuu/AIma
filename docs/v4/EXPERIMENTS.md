# v4.0 实验运行文档

## 快速开始

### 运行实验

```bash
python -m experiments.run --config examples/smoke.yaml
```

### 聚合指标

```bash
python -m experiments.aggregate --run runs/smoke
```

### 查看结果

```bash
python -m ui.viewer --run runs/smoke
```

---

## ExperimentSpec 配置

### 基本结构

```yaml
meta:
  id: smoke_test
  description: "快速验证实验"
  tags: [smoke, baseline]

rule:
  version: v3.1.3
  scope_file: RULE_SCOPE.md

seed:
  start: 42
  count: 1

match:
  preset: half
  max_hands: 4
  step_limit: 1000

runtime:
  mode: batch
  no_persist: true
  resume: true
  fail_fast: false

artifact:
  output_root: runs
  save_replay: true
  save_decisions: true
  sqlite_index: true

seats:
  - policy: first_legal
  - policy: first_legal
  - policy: first_legal
  - policy: first_legal
```

### Policy 配置

```yaml
seats:
  - policy: llm
    agent:
      pipeline_id: default
      model:
        backend: openai_compatible
        model_name: gpt-4o-mini
        temperature: 0.7
      prompt:
        template_id: riichi_json_action_v1
```

### MatchSpec 语义

`preset` 定义规则自然终局类型：`tonpuu` 默认 4 局，`hanchan` 默认 8 局。
`max_hands` 是实验安全截断上限，表示“完成 N 局后停止”；`null` 表示使用
`preset` 的自然局数，不额外提前截断。`step_limit` 是防死循环安全上限。

为了区分自然终局和实验截断，runner 会在局结束后执行一次 `NEXT_ROUND`，
让 kernel 判断是否进入 `match_end`。如果未到自然终局但已达到 `max_hands`，
则 artifact 中写入：

```text
outcome=truncated
stopped_reason=max_hands_reached
hand_count=<已完成局数>
```

此时 `final_phase` 可能已经是下一局的 `in_round` 初始状态，这是预期行为。

---

## 输出结构

```
runs/{experiment_id}/
├── manifest.yaml        # 实验元数据
├── RULE_SCOPE.md        # 规则范围声明
├── git_info.json        # Git 状态
├── env_info.json        # 环境信息
├── seed_plan.json       # Seed 计划
├── jobs.jsonl           # Job 列表
├── jobs/{job_id}/
│   ├── summary.json     # Match 摘要
│   ├── replay.json      # 牌谱
│   ├── events.jsonl     # 事件记录
│   ├── decisions.jsonl  # 决策记录
│   └ metrics.json       # 指标快照
│   └ debug/             # 可选调试输出
└── aggregate/
    ├── match_metrics.csv
    ├── decision_metrics.csv
    ├── player_metrics.csv
    ├── reliability_summary.json
    └ report.md
```

---

## Resume 支持

运行中断后可恢复：

```bash
python -m experiments.run --config examples/smoke.yaml
# 中断后再次运行，已成功的 job 会跳过
```

---

## SQLite 索引

### 建立索引

```bash
python -m experiments.index --rebuild runs
python -m experiments.index --rebuild runs/smoke  # 也支持单个 experiment run dir
```

### 索引表结构

- experiments: 实验元数据
- jobs: Job 状态
- matches: Match 结果
- metrics_summary: 指标摘要
- artifact_paths: 关键 artifact 路径

---

## 常见问题

### Q: 如何添加新的 Policy？

在 seats 配置中使用：

```yaml
seats:
  - policy: your_policy_name
    options:
      param1: value1
```

确保 Policy 已注册到 `policies/registry.py`。

### Q: 如何使用本地模型？

使用 llama.cpp 服务器 + OpenAI 兼容后端：

```bash
# 启动 llama.cpp 服务器
llama-server -m model.gguf --port 8080
```

```yaml
# 配置 ModelSpec
model:
  backend: openai_compatible
  endpoint: http://localhost:8080/v1
  model_name: local
```

### Q: 如何禁用 artifact 保存？

```yaml
artifact:
  save_replay: false
  save_decisions: false
```
