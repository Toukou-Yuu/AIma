# v4.0 架构文档

## 模块结构

```
src/
├── kernel/           # 规则裁判（可信，不修改）
├── arena/            # 对局运行框架
│   ├── engine.py     # GameEngine 门面
│   ├── policy.py     # Policy Protocol
│   └── match_runner.py # MatchRunner
├── policies/         # 策略实现
│   ├── random_policy.py
│   ├── first_legal_policy.py
│   ├── fixed_heuristic_policy.py
│   ├── llm_policy.py
│   └── registry.py
├── agents/           # Agent 流水线
│   ├── pipeline.py   # AgentPipeline
│   ├── schema.py     # 数据结构
│   └── components/   # 流水线组件
│       ├── parser.py
│       ├── grounding.py
│       ├── fallback.py
│       └── prompt.py
├── prompts/          # Prompt DSL
│   ├── schema.py     # PromptSpec
│   ├── renderer.py   # PromptRenderer
│   ├── sections.py   # Section 实现
│   └── loader.py     # Template 加载
├── context/          # 上下文构建
│   ├── builder.py    # ContextBuilder
│   ├── builders.py   # 各种 scope 实现
│   ├── compression.py
│   └── token_budget.py
├── memory/           # 分层记忆
│   ├── schema.py
│   ├── stores.py
│   ├── readers.py
│   ├── writers.py
│   └ lifecycle.py
├── models/           # 模型后端
│   ├── backend.py    # ModelBackend Protocol
│   ├── schema.py
│   ├── registry.py
│   └── backends/
│       ├── dummy.py
│       ├── mock.py
│       ├── openai_compatible.py
│       ├── llama_cpp.py
│       └ vllm_native.py
├── experiments/      # 实验运行
│   ├── schema.py     # ExperimentSpec
│   ├── runner.py     # ExperimentRunner
│   ├── job.py        # Job 模型
│   ├── index.py      # SQLite 索引
│   ├── aggregate.py  # Aggregate CLI
│   └ sinks/          # 输出 sink
│       ├── artifact.py
│       ├── index.py
│       └ tee.py
├── metrics/          # 指标计算
│   ├── schema.py     # MatchMetrics, DecisionMetrics
│   ├── loader.py     # 数据加载
│   ├── pipeline.py   # MetricsPipeline
│   ├── report.py     # 报告生成
│   ├── extractors/   # 提取器
│   └ reducers/       # 聚合器
├── replay/           # 牌谱序列化
│   └ serialize.py
└── ui/viewer/        # Artifact Viewer
    ├── data_source.py
    ├── app.py
    ├── screens/
    └ components/
```

## 依赖方向

```
kernel (可信核心)
  ↑
arena/engine.py (门面)
  ↑
arena/match_runner.py → policies/
  ↑
policies/llm_policy.py → agents/pipeline
  ↑
agents/components/ → prompts/, context/, memory/, models/
```

**禁止反向依赖**:
- UI → experiment 运行功能（允许数据读取）
- experiment → UI
- 任何模块 → kernel 修改

## 扩展点

1. **新增 Policy**: 实现 Policy Protocol，注册到 policies/registry.py
2. **新增 ModelBackend**: 实现 ModelBackend Protocol，注册到 models/registry.py
3. **新增 Prompt Section**: 实现 Section Protocol，添加到 prompts/sections.py
4. **新增 Memory Layer**: 实现 MemoryReader/Writer，添加到 memory/
5. **新增 Metrics**: 实现 BaseExtractor/BaseReducer，添加到 metrics/