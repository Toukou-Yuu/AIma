# Agent 状态管理流程

本文档描述 `src/llm/agent` 模块的状态管理架构和数据流。

## 核心设计原则

**Agent 是无状态的"纯函数"，只保留长期状态（profile/memory/stats）。**

运行时状态（本局统计）存储在 `EpisodeContext` 中，跨局状态存储在 `MatchContext` 中，均由外部（runner）管理。

## 职责分离架构（2026-04 重构）

重构后采用组合模式，将 `PlayerAgent` 拆分为 7 个独立组件：

```
src/llm/agent/
├── __init__.py        # PlayerAgent（协调类，无状态纯函数）
├── core.py            # AgentCore（核心决策逻辑）
├── session.py         # ModelSessionPolicy + ConversationLogNamer
├── prompt.py          # PromptProjector（上下文投影）
├── context_store.py   # ContextStore（结构化历史 + 压缩）
├── decision_parser.py # DecisionParser（决策解析）
├── persistence.py     # PersistenceManager（持久化管理）
├── match_context.py   # MatchContext（跨局状态管理）← Context Object 模式
└── context.py         # EpisodeContext（运行时上下文）
└── memory.py          # PlayerMemory + EpisodeSummarizer
└── stats.py           # PlayerStats + StatsAggregator + MatchStats
└── profile.py         # PlayerProfile
└── llm_summarizer.py  # LLMSummarizer
└── prompt_builder.py  # 基础 Prompt 函数（被 prompt.py 使用）
```

### 设计模式应用

| 设计模式 | 应用场景 |
|----------|----------|
| **Context Object Pattern** | `MatchContext` 封装跨局状态 |
| **Factory Pattern** | `MatchContext.create_episode()` 统一创建 `EpisodeContext` |
| **Composition Pattern** | `PlayerAgent` 组合各组件 |

### 组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| `PlayerAgent` | `__init__.py` | 协调类，组合所有组件，提供公共接口（无状态） |
| `AgentCore` | `core.py` | 核心决策逻辑，判断唯一动作、dry-run、LLM调用、解析响应 |
| `ModelSessionPolicy` | `session.py` | 模型会话边界（stateless/per_hand/per_match） |
| `PromptProjector` | `prompt.py` | Prompt 投影，整合 profile/memory/stats/历史视图 |
| `ContextStore` | `context_store.py` | 结构化历史存储与预算驱动压缩 |
| `DecisionParser` | `decision_parser.py` | 决策解析，JSON解析、action匹配、fallback处理 |
| `PersistenceManager` | `persistence.py` | 持久化管理，load/save profile/memory/stats |
| `MatchContext` | `match_context.py` | 跨局状态管理（Context Object），创建 EpisodeContext（Factory） |
| `EpisodeContext` | `context.py` | 运行时上下文，本局统计、历史记录 |

### 组件交互

```python
# PlayerAgent.__init__ 中的组合关系
class PlayerAgent:
    def __init__(...):
        self._persistence = PersistenceManager(player_id)  # 持久化
        self._session_policy = ModelSessionPolicy(...)     # 会话策略
        self._prompt_projector = PromptProjector(...)      # Prompt 投影
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

`ModelSessionPolicy` 为每个 `PlayerAgent` 实例生成唯一的 `_session_token`（UUID前8位）：

```python
class ModelSessionPolicy:
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

### 2. 跨局状态（存储在 `MatchContext`）

| 属性 | 描述 |
|------|------|
| `_match_stats` | 本场累积统计（私有，外部只读） |
| `_episodes` | 已完成局列表 |

### 3. 运行时状态（存储在 `EpisodeContext`）

| 属性 | 描述 |
|------|------|
| `episode_stats` | 本局统计（和了、放铳、立直） |
| `match_stats` | 本局累积统计（从 MatchContext 副本继承） |
| `decision_history` | 决策历史 |
| `last_observation` | 上一帧观测（用于变化帧） |

### 4. Agent 内部状态（无临时状态）

| 属性 | 描述 |
|------|------|
| `profile` | 玩家配置 |
| `memory` | 玩家记忆 |
| `stats` | 玩家统计 |

**注意**：Agent 不再存储任何临时跨局状态，完全无状态。

## 数据流

### 局开始时（Context Object + Factory Pattern）

```python
# runner.py - 初始化 MatchContext
match_contexts: dict[int, MatchContext] = {
    s: MatchContext(s) for s in range(4)
}

# runner.py - 创建 EpisodeContext（Factory 模式）
seat_contexts[s] = match_contexts[s].create_episode()  # 返回副本，确保隔离
```

### 每步决策时

```python
# PlayerAgent.decide() -> AgentCore.decide()
# 1. 获取合法动作
acts = legal_actions(state, seat)

# 2. 判断是否需要 LLM
if len(acts) == 1 and acts[0].kind in (PASS_CALL, DRAW):
    return Decision(acts[0], None, history)  # 跳过 LLM

# 3. 构建消息（PromptProjector）
messages = prompt_projector.build_messages(...)

# 4. 调用 LLM（ModelSessionPolicy）
session_id = session_policy.build_session_id(seat, hand_number=ctx.hand_number)
raw = client.complete(messages, session_id=session_id)

# 5. 解析响应（DecisionParser）
la, why = DecisionParser.parse_llm_response(raw, acts)

# 6. 更新历史
episode_ctx.record_decision(Decision(la, why, []))
```

### 局结束时（显式关闭）

```python
# runner._finalize_agents_episode()
seat_contexts[seat].end_episode(points)
match_contexts[seat].close_episode(seat_contexts[seat])  # 显式关闭（更新 MatchContext）
agent.update_memory(seat_contexts[seat], client)  # 更新长期记忆
```

### 比赛结束时

```python
# runner
agent.update_stats(seat_contexts[seat], placement)  # 更新长期统计
```

### 新局开始时（继承跨局统计）

```python
# runner.py - 新局创建（Factory 模式）
seat_contexts[s] = match_contexts[s].create_episode()  # 继承累积的 match_stats
```

## 重构收益

### 代码质量

- **单一职责**：每个组件职责清晰
- **高内聚**：相关功能集中在同一组件，外部无法直接修改内部状态
- **低耦合**：组件间通过接口交互，runner 与 Agent 无状态传递依赖
- **可测试**：每个组件可独立测试
- **设计模式**：Context Object + Factory Pattern 提供标准化扩展点

### 文件行数

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~100 | 协调（无状态） |
| `core.py` | ~150 | 决策 |
| `session.py` | ~50 | 会话 |
| `prompt.py` | ~100 | Prompt |
| `decision_parser.py` | ~60 | 解析 |
| `persistence.py` | ~120 | 持久化 |
| `match_context.py` | ~80 | 跨局状态（Context Object） |

### 测试覆盖

- `test_llm_mock_client.py`: Agent 决策测试
- `test_llm_skip_singleton_pass.py`: 单一动作跳过测试
- `test_llm_session_audit.py`: Session audit 测试

## 组件级测试示例

```python
# 测试 ModelSessionPolicy
def test_session_manager_isolation():
    s1 = ModelSessionPolicy("player_001")
    s2 = ModelSessionPolicy("player_001")
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

# 测试 MatchContext（Context Object Pattern）
def test_match_context_lifecycle():
    mc = MatchContext(0)
    
    # Factory 模式创建
    ctx1 = mc.create_episode()
    assert ctx1.match_stats.wins == 0
    
    # 隔离性验证
    ctx1.match_stats.wins = 1
    assert mc.get_stats().wins == 0  # 副本隔离
    
    # 显式关闭
    mc.close_episode(ctx1)
    assert mc.get_stats().wins == 1
    
    # 继承累积统计
    ctx2 = mc.create_episode()
    assert ctx2.match_stats.wins == 1
```
