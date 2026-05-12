# Agent 状态管理

`PlayerAgent` 是无状态协调类，只保留长期状态（profile/memory/stats）。运行时状态由外部（runner）管理。

组件目录结构见 `src/llm/README.md`。

## 组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| `PlayerAgent` | `__init__.py` | 协调类，组合所有组件，提供 `decide()` 接口 |
| `AgentCore` | `core.py` | 核心决策逻辑：判断唯一动作、dry-run、LLM 调用、解析响应 |
| `LocalContextPolicy` | `session.py` | AIma 本地上下文边界（stateless/per_hand/per_match） |
| `PromptProjector` | `prompt.py` | Prompt 投影，整合 profile/memory/stats/公共事件/自家历史 |
| `ContextStore` | `context_store.py` | 自家决策历史存储与渐进式压缩 |
| `MatchJournal` | `event_journal.py` | 整桌公共事件流与跨局公共归档 |
| `PromptBudgetPlanner` | `token_budget.py` | 经验公式 token 预算与压缩边界规划 |
| `DecisionParser` | `decision_parser.py` | 决策解析：JSON 解析、action 匹配、fallback 处理 |
| `PersistenceManager` | `persistence.py` | 持久化管理：load/save profile/memory/stats |
| `MatchContext` | `match_context.py` | 跨局状态管理（Context Object），创建 EpisodeContext（Factory） |
| `EpisodeContext` | `context.py` | 运行时上下文：本局统计、决策历史、帧缓存 |

## 状态分类

### 1. 长期状态（持久化到 `configs/players/<player_id>/`）

| 组件 | 文件 | 更新时机 |
|------|------|---------|
| `PlayerProfile` | `profile.json` | 手动配置 |
| `PlayerMemory` | `memory.json` | 局结束时 |
| `PlayerStats` | `stats.json` | 比赛结束时 |

### 2. 跨局状态（`MatchContext`）

| 属性 | 描述 |
|------|------|
| `_match_stats` | 本场累积统计（私有，外部只读） |
| `_episodes` | 已完成局列表 |
| `_hand_archives` | 已归档的局摘要（供 `per_match` 注入） |

### 3. 运行时状态（`EpisodeContext`）

| 属性 | 描述 |
|------|------|
| `episode_stats` | 本局统计（和了、放铳、立直） |
| `match_stats` | 本局累积统计（从 MatchContext 副本继承） |
| `match_history_archive` | 创建本局时拍下的跨局摘要快照 |
| `decision_history` | 自家决策历史 |
| `match_journal` | 共享公共事件流视图 |
| `message_ledger` | 本局 user/assistant 消息账本 |

### 4. Agent 内部（无临时状态）

`profile`、`memory`、`stats` 三项在 `PlayerAgent.__init__` 中从磁盘加载，之后只读。

## 本地上下文边界（LocalContextPolicy）

`LocalContextPolicy` 决定向模型注入哪些上下文层：

- **`stateless`**：只发当前观测
- **`per_hand`**：发本局历史 + 当前观测
- **`per_match`**：发本场前情摘要 + 本局历史 + 当前观测

## 数据流

### 局开始

`runner.py` 为每个 seat 创建 `MatchContext`（`match_contexts[s] = MatchContext(s)`）。新局开始时调用 `match_contexts[s].create_episode()` 创建 `EpisodeContext`（Factory Pattern），继承累积的 `match_stats`。

### 每步决策

`PlayerAgent.decide()` → `AgentCore.decide()`：

1. `legal_actions(state, seat)` 获取合法动作
2. 若唯一合法动作（`PASS_CALL` / `DRAW`），跳过 LLM 直接返回
3. `PromptProjector.build_projection()` 构建消息 + token 预算诊断
4. `client.complete(messages)` 调用 LLM
5. `DecisionParser.parse_llm_response()` 解析响应
6. `episode_ctx.record_decision()` 更新历史

### 局结束

`runner._finalize_agents_episode()`：

1. `seat_contexts[seat].end_episode(points)` 结算本局
2. `match_contexts[seat].close_episode(ctx)` 显式关闭，更新 MatchContext 累积统计
3. `agent.update_memory(ctx, client)` 更新长期记忆

### 比赛结束

`agent.update_stats(ctx, placement)` 更新长期统计到 `stats.json`。

## 测试

相关测试文件：
- `tests/test_llm_mock_client.py` — Agent 决策测试
- `tests/test_llm_skip_singleton_pass.py` — 单一动作跳过测试
- `tests/test_llm_session_audit.py` — Session audit 测试
- `tests/test_llm_context_projection.py` — Context 投影测试
- `tests/test_llm_token_budget.py` — Token 预算测试
