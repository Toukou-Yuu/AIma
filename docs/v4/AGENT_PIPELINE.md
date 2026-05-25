# v4.0 Agent Pipeline 文档

## 流水线架构

```
DecisionContext → AgentPipeline → PolicyDecision
                      ↓
                 ┌─────────────────────────────────────────┐
                 │ 1. ObservationBuilder                    │
                 │ 2. ContextBuilder                        │
                 │ 3. MemoryReader                          │
                 │ 4. PromptRenderer                        │
                 │ 5. ModelCaller                           │
                 │ 6. OutputParser                          │
                 │ 7. ActionGrounder                        │
                 │ 8. RepairStrategy (optional)             │
                 │ 9. FallbackStrategy                      │
                 │ 10. MemoryWriter                         │
                 │ 11. DecisionTraceBuilder                 │
                 └─────────────────────────────────────────┘
```

---

## 流水线组件

### 1. ObservationBuilder

构建当前状态的观察视图：

```python
class ObservationBuilder:
    def build(self, context: DecisionContext) -> ObservationView:
        # 从 GameState 提取 seat 视角的信息
        ...
```

### 2. ContextBuilder

构建公共历史：

```python
class ContextBuilder:
    def build(self, context: DecisionContext, scope: str) -> ContextView:
        # scope: stateless, per_turn, per_hand, per_match
        ...
```

### 3. MemoryReader

读取分层记忆：

```python
class MemoryReader:
    def read(self, layers: list[str]) -> MemoryContent:
        # layers: hand, match, persistent, opponent
        ...
```

### 4. PromptRenderer

渲染 Prompt：

```python
class PromptRenderer:
    def render(self, spec: PromptSpec, context: RenderContext) -> tuple[ModelMessage, ...]:
        # 按顺序渲染 sections
        ...
```

### 5. ModelCaller

调用模型：

```python
class ModelCaller:
    def call(self, messages: tuple[ModelMessage, ...], spec: ModelSpec) -> ModelResponse:
        # 调用 ModelBackend
        ...
```

### 6. OutputParser

解析输出：

```python
class OutputParser:
    def parse(self, response: str, format: str) -> ParsedOutput:
        # format: strict_json
        # 返回 parsed action 或 parse_error
        ...
```

### 7. ActionGrounder

匹配 legal actions：

```python
class ActionGrounder:
    def ground(self, parsed: ParsedOutput, legal: tuple[LegalAction, ...]) -> GroundedAction:
        # 返回 matched action 或 illegal_action
        ...
```

### 8. FallbackStrategy

处理失败：

```python
class FallbackStrategy:
    def fallback(self, legal: tuple[LegalAction, ...]) -> Action:
        # strategy: first_legal, random_legal, none
        ...
```

---

## Diagnostics

每个决策生成完整的 diagnostics：

```python
class PromptDiagnostics:
    estimated_tokens: int
    actual_prompt_tokens: int
    completion_tokens: int
    memory_injected_tokens: int
    section_tokens: dict[str, int]
    raw_response: str
    parse_errors: list[str]
    fallback_reason: str | None
```

---

## 扩展指南

### 新增 Pipeline 组件

1. 在 `src/agents/components/` 创建新组件
2. 组件接收 PipelineContext，返回处理结果
3. 在 Pipeline 构造中注册组件

### 新增 OutputParser 格式

1. 在 `parser.py` 添加新格式处理
2. 支持 ExperimentSpec 中的 output_format 配置

### 新增 FallbackStrategy

1. 在 `fallback.py` 实现新策略
2. 注册到 FallbackStrategy 构造函数