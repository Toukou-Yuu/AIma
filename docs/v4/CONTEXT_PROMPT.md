# v4.0 Context 与 Prompt 文档

## 概述

v4.0 使用统一的 ContextBuilder + PromptRuntime 构建决策 prompt：

```
GameState → Observation → ContextBuilder → PromptRuntime → LLM Prompt
```

---

## Context 范围（scope）

| Scope | 包含内容 | Token估算 |
|-------|----------|-----------|
| stateless | 仅当前局面 | ~500 |
| per_turn | 本回合事件 | ~800 |
| per_hand | 本局完整事件 | ~2000 |
| per_match | 跨局完整事件 | ~5000+ |

### 配置示例

```yaml
agent:
  context:
    scope: stateless
```

---

## Context 压缩（compression）

| 策略 | 说明 | 状态 |
|------|------|------|
| none | 不压缩 | ✅ |
| snip | 截断最早事件 | ✅ |
| collapse | 合并为摘要 | ✅ |
| autocompact | 高密度折叠 | ⚠️ 实验性stub |

### autocompact 警告

`autocompact` 在 v4.0 是 stub 实现，仅作为 `collapse` 的 alias。**不应用于实验对照**。

```yaml
# 不推荐用于实验
compression: autocompact

# 推荐用于实验对照
compression: none
compression: collapse
```

---

## Prompt DSL

### 模板配置

```yaml
agent:
  prompt:
    template_id: riichi_json_action_v1
    version: "1.0.0"
    sections: []
```

### Section 类型

| Section | 内容 |
|---------|------|
| hand | 手牌信息 |
| public_history | 公共事件历史 |
| memory | 记忆注入（memory mode=passive时） |
| scoreboard | 分数表 |
| legal_actions | 可选动作列表 |

### 输出格式

| 格式 | 说明 |
|------|------|
| json_action | JSON结构化输出 |
| natural_action | 自然语言输出 |

### JSON Action 格式

LLM 输出：

```json
{"action": "打三万", "why": "孤立牌，进张面窄"}
```

解析为 kernel Action：

```python
Action(kind="discard", tile="3m")
```

---

## Token 预算

```yaml
agent:
  prompt:
    budget:
      max_prompt_tokens: 4000
      truncation_policy: drop_oldest_public_events
```

---

## Context Ablation 实验

v4.2 推荐实验变量：

```yaml
# baseline: stateless
context:
  scope: stateless

# treatment: per_match
context:
  scope: per_match
```

观察指标：
- token usage
- fallback rate
- parse error rate
- 决策情境指标（passed_win, riichi_when_possible）

---

## Diagnostics

决策记录包含 context diagnostics：

```json
{
  "diagnostics": {
    "prompt_tokens": 2000,
    "memory_injected_tokens": 150,
    "context_truncated": false
  }
}
```