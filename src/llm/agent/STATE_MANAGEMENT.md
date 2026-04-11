# Agent 状态管理流程

本文档描述 `src/llm/agent` 模块的状态管理架构和数据流。

## 核心设计原则

**Agent 是无状态的"纯函数"，只保留长期状态（profile/memory/stats）。**

运行时状态（本局统计、本场统计、决策历史）存储在 `EpisodeContext` 中，由外部（runner）管理。

## 职责分离架构（2026-04 重构）

重构后采用组合模式，将 `PlayerAgent` 拆分为 6 个独立组件：

```
src/llm/agent/
├── __init__.py        # PlayerAgent（协调类）
├── core.py            # AgentCore（核心决策逻辑）
├── session.py         # SessionManager（会话管理）
├── prompt.py          # PromptBuilder（Prompt 构建）
├── decision_parser.py # DecisionParser（决策解析）
├── persistence.py     # PersistenceManager（持久化管理）
└── context.py         # EpisodeContext（运行时上下文）
└── memory.py          # PlayerMemory + EpisodeSummarizer
└── stats.py           # PlayerStats + StatsAggregator
└── profile.py         # PlayerProfile
└── llm_summarizer.py  # LLMSummarizer
└── prompt_builder.py  # 基础 Prompt 函数（被 prompt.py 使用）
```

### 组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| `PlayerAgent` | `__init__.py` | 协调类，组合所有组件，提供公共接口 |
| `AgentCore` | `core.py` | 核心决策逻辑，判断唯一动作、dry-run、LLM调用、解析响应 |
| `SessionManager` | `session.py` | 会话管理，生成唯一 session_token，构建 session_id |
| `PromptBuilder` | `prompt.py` | Prompt 构建，整合 profile/memory/stats，选择帧类型 |
| `DecisionParser` | `decision_parser.py` | 决策解析，JSON解析、action匹配、fallback处理 |
| `PersistenceManager` | `persistence.py` | 持久化管理，load/save profile/memory/stats |
| `EpisodeContext` | `context.py` | 运行时上下文，本局统计、历史记录 |

### 组件交互

```python
# PlayerAgent.__init__ 中的组合关系
class PlayerAgent:
    def __init__(...):
        self._persistence = PersistenceManager(player_id)  # 持久化
        self._session = SessionManager(player_id)          # 会话
        self._prompt_builder = PromptBuilder(...)          # Prompt
        self._core = AgentCore(...)                        # 决策核心
        
        # 加载长期状态
        self.profile = self._persistence.load_profile()
        self.memory = self._persistence.load_memory()
        self.stats = self._persistence.load_stats()

# PlayerAgent.decide 中的委托
def decide(...):
    return self._core.decide(
        state, seat, episode_ctx,
        prompt_builder=self._prompt_builder,
        session_manager=self._session,
        client=client, ...
    )
```

## 会话隔离机制

`SessionManager` 为每个 `PlayerAgent` 实例生成唯一的 `_session_token`（UUID前8位）：

```python
class SessionManager:
    def __init__(self, player_id: str | None = None):
        self._session_token = str(uuid4())[:8]
    
    def build_session_id(self, seat: int) -> str:
        session_key = self.player_id or f"seat_{seat}"
        return f"majiang_player_{session_key}_{self._session_token}"
```

**效果**：
- 不同实例：不同 session_id，会话隔离
- 同一实例：相同 session_id，对话历史连续

## 状态分类

### 1. 长期状态（持久化到 `configs/players/<player_id>/`）

| 组件 | 文件 | 更新时机 |
|------|------|---------|
| `PlayerProfile` | `profile.json` | 手动配置 |
| `PlayerMemory` | `memory.json` | **局结束** |
| `PlayerStats` | `stats.json` | **比赛结束** |

### 2. 运行时状态（存储在 `EpisodeContext`）

| 属性 | 描述 |
|------|------|
| `episode_stats` | 本局统计（和了、放铳、立直） |
| `match_stats` | 本场统计（跨局累积） |
| `decision_history` | 决策历史 |
| `last_observation` | 上一帧观测（用于变化帧） |

### 3. Agent 内部临时状态

| 属性 | 描述 |
|------|------|
| `_temp_match_stats` | 跨局统计临时存储 |

## 数据流

### 局开始时

```python
# runner.py
for s in range(4):
    match_stats = seat_agents[s].load_match_stats()
    seat_contexts[s] = EpisodeContext(s, match_stats=match_stats)
```

### 每步决策时

```python
# PlayerAgent.decide() -> AgentCore.decide()
# 1. 获取合法动作
acts = legal_actions(state, seat)

# 2. 判断是否需要 LLM
if len(acts) == 1 and acts[0].kind in (PASS_CALL, DRAW):
    return Decision(acts[0], None, history)  # 跳过 LLM

# 3. 构建消息（PromptBuilder）
messages = prompt_builder.build_messages(obs, acts, history_text, ...)

# 4. 调用 LLM（SessionManager）
session_id = session_manager.build_session_id(seat)
raw = client.complete(messages, session_id=session_id)

# 5. 解析响应（DecisionParser）
la, why = DecisionParser.parse_llm_response(raw, acts)

# 6. 更新历史
episode_ctx.record_decision(Decision(la, why, []))
```

### 局结束时

```python
# runner._finalize_agents_episode()
seat_contexts[seat].end_episode(points)
agent.save_match_stats(seat_contexts[seat].match_stats)
agent.update_memory(seat_contexts[seat], client)  # 更新长期记忆
```

### 比赛结束时

```python
# runner
agent.update_stats(seat_contexts[seat], placement)  # 更新长期统计
```

## 重构收益

### 代码质量

- **单一职责**：每个组件职责清晰
- **高内聚**：相关功能集中在同一组件
- **低耦合**：组件间通过接口交互
- **可测试**：每个组件可独立测试

### 文件行数

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~100 | 协调 |
| `core.py` | ~150 | 决策 |
| `session.py` | ~50 | 会话 |
| `prompt.py` | ~100 | Prompt |
| `decision_parser.py` | ~60 | 解析 |
| `persistence.py` | ~120 | 持久化 |

### 测试覆盖

- `test_llm_mock_client.py`: Agent 决策测试
- `test_llm_skip_singleton_pass.py`: 单一动作跳过测试
- `test_llm_session_audit.py`: Session audit 测试

## 组件级测试示例

```python
# 测试 SessionManager
def test_session_manager_isolation():
    s1 = SessionManager("player_001")
    s2 = SessionManager("player_001")
    assert s1.build_session_id(0) != s2.build_session_id(0)

# 测试 DecisionParser
def test_decision_parser_fallback():
    la, why = DecisionParser.parse_llm_response("invalid json", acts)
    assert la is None
    assert why is None

# 测试 PersistenceManager
def test_persistence_load_default():
    pm = PersistenceManager(None)
    profile = pm.load_profile()
    assert profile.id == "default"
```