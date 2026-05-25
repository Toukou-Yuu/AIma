# v4.0 Metrics 指标文档

## 指标体系

### M1: 运行时指标

| 指标 | 来源 | 描述 |
|------|------|------|
| latency_ms | ModelBackend | LLM 调用延迟 |
| prompt_tokens | ModelBackend | Prompt token 数 |
| completion_tokens | ModelBackend | Completion token 数 |
| memory_injected_tokens | PromptRenderer | Memory 注入 token 数 |
| parse_status | OutputParser | ok/fallback/error |
| fallback_used | ActionGrounder | 是否使用 fallback |

### M2: Match 指标

| 指标 | 计算 | 描述 |
|------|------|------|
| final_points | MatchEnd | 最终点数 |
| point_delta | MatchEnd | 点数变化 |
| outcome | MatchEnd | 完成状态 |
| step_count | summary | 总步数 |
| hand_count | HandOver 计数 | 局数 |
| ron_count | Ron 计数 | Ron 次数 |
| tsumo_count | Tsumo 计数 | Tsumo 次数 |
| riichi_count | Riichi 计数 | 立直次数 |

### M3: Player 指标

| 指标 | 计算 | 描述 |
|------|------|------|
| avg_final_points | 跨 match 平均 | 平均最终点数 |
| avg_point_delta | 跨 match 平均 | 平均点数变化 |
| riichi_success_rate | 立直后和牌率 | 立直成功率 |
| parse_success_rate | ok / total | 解析成功率 |
| avg_latency_ms | 跨 decision 平均 | 平均延迟 |
| p99_latency_ms | 99 分位 | P99 延迟 |

---

## Extractor/Reducer 模式

### Extractors

从 RunData 提取 MetricRecord：

```python
class BaseExtractor(Protocol):
    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        ...
```

已实现 Extractors：
- MatchEndExtractor
- HandOverExtractor
- DecisionExtractor
- RonExtractor
- TsumoExtractor
- RiichiExtractor
- CallExtractor
- FlowExtractor

### Reducers

聚合 MetricRecord：

```python
class BaseReducer(Protocol):
    def reduce(self, records: Iterable[MetricRecord]) -> list[AggregatedMetrics]:
        ...
```

已实现 Reducers：
- MatchReducer → list[MatchMetrics]
- DecisionReducer → list[DecisionMetrics]
- PlayerReducer → list[PlayerMetrics]

---

## Pipeline 使用

```python
from metrics import create_default_pipeline, load_run_data

# 加载数据
run_data = load_run_data(Path("runs/smoke"))

# 运行 pipeline
pipeline = create_default_pipeline()
results = pipeline.run(run_data)

# 输出
# results["match"] → list[MatchMetrics]
# results["decision"] → list[DecisionMetrics]
# results["player"] → list[PlayerMetrics]
```

---

## 报告生成

```python
from metrics.report import ReportGenerator

generator = ReportGenerator(results)
generator.write_all(Path("runs/smoke/aggregate"))

# 生成文件：
# - match_metrics.csv
# - decision_metrics.csv
# - player_metrics.csv
# - reliability_summary.json
# - report.md
```

---

## 自定义指标

### 新增 Extractor

```python
from metrics.extractors.base import BaseExtractor
from metrics.schema import MetricRecord

class MyExtractor(BaseExtractor):
    name = "my_extractor"
    
    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        for event in data.events:
            if event.event.get("kind") == "my_event":
                yield MetricRecord(
                    kind="my_record",
                    match_id=data.match_id,
                    job_id=data.job_id,
                    values={"my_field": ...}
                )
```

### 新增 Reducer

```python
from metrics.reducers.base import BaseReducer

class MyReducer(BaseReducer):
    name = "my_reducer"
    
    def reduce(self, records: Iterable[MetricRecord]) -> list[MyMetrics]:
        ...
```

---

## completion_tokens 启发式

当 LLM backend 不返回 completion_tokens 时：

```python
COMPLETION_TOKEN_RATIO = 0.1
estimated_completion = prompt_tokens * COMPLETION_TOKEN_RATIO
```