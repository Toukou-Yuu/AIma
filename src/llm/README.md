# LLM 模块 - 大语言模型编排与角色系统

本模块负责将麻将内核与 LLM 对接，实现 AI 牌手对局。

## 架构

```
src/llm/
├── __main__.py           # CLI 入口
├── cli.py                # 命令行解析与对局启动
├── runner.py             # 对局主循环（run_llm_match）
├── config.py             # 配置加载与 MatchEndCondition
├── protocol.py           # HTTP 客户端抽象（OpenAI/Anthropic）
├── agent/                # Agent 系统
│   ├── __init__.py       # PlayerAgent（协调类）
│   ├── core.py           # AgentCore（核心决策逻辑）
│   ├── session.py        # ModelSessionPolicy + ConversationLogNamer
│   ├── prompt.py         # PromptProjector（显式上下文投影）
│   ├── context_store.py  # ContextStore（结构化历史 + 压缩）
│   ├── decision_parser.py # DecisionParser（决策解析）
│   ├── persistence.py    # PersistenceManager（持久化管理）
│   ├── match_context.py  # MatchContext（跨局状态管理）
│   ├── context.py        # EpisodeContext（运行时上下文）
│   ├── memory.py         # PlayerMemory + EpisodeSummarizer
│   ├── stats.py          # PlayerStats + MatchStats
│   ├── profile.py        # PlayerProfile
│   └── STATE_MANAGEMENT.md # 状态管理文档
├── observation_format.py # 观测格式化（自然语言）
├── validate.py           # 决策校验与匹配
├── parse.py              # JSON 解析
├── wire.py               # 动作序列化
├── action_build.py       # LegalAction → Action
└── docs/
    └── scope.md          # 职责边界说明
```

## 设计原则

1. **Agent 是无状态纯函数**：只保留长期状态（profile/memory/stats），运行时状态由外部管理
2. **单向依赖**：`llm → kernel`，禁止 `kernel` import `llm`
3. **规则在代码里**：LLM 只是操作端，不能改写规则或偷看隐藏信息

## 核心组件

### PlayerAgent

协调类，组合各组件实现职责分离：

```python
agent = PlayerAgent(player_id="kavi")
decision = agent.decide(state, seat, episode_ctx=ctx, client=client)
```

### MatchContext

跨局状态管理（Context Object + Factory Pattern）：

```python
mc = MatchContext(seat=0)
ctx = mc.create_episode()  # 创建新局上下文
mc.close_episode(ctx)      # 关闭本局，更新统计
```

### PromptProjector

按“长期状态 + 结构化局内历史 + 当前观测”显式投影 Prompt：

```
system = base_prompt + persona + memory + stats
history = ContextStore.project_history(...)
user = natural/json keyframe or json delta
```

## 配置

### aima_kernel.yaml

```yaml
llm:
  provider: openai
  api_key: "your-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
  prompt_format: natural
  session_scope: per_hand
  compression_level: collapse
  history_budget: 10
  system_prompt: |
    你是日式麻将牌手...

players:
  - id: ichihime
    seat: 0
  - id: yui
    seat: 1
```

### 角色配置

每个角色在 `configs/players/{id}/` 下有：
- `profile.json` - 人格、策略提示词
- `memory.json` - 历史表现记忆（gitignore）
- `stats.json` - 长期统计（gitignore）

## CLI 命令

```bash
# Dry-run（无需 API Key）
python -m llm --dry-run --seed 42

# 实际对局
python -m llm --config configs/aima_kernel.yaml

# 生成日志
python -m llm --log-session my_match

# 牌谱回放
python -m llm --replay logs/replay/xxx.json

# 详细选项
python -m llm --help
```

## 日志

运行后生成：
- `logs/replay/{timestamp}.json` - 完整牌谱（replay_json）
- `logs/debug/{timestamp}.log` - 调试日志
- `logs/simple/{timestamp}.txt` - 可读文本日志

## 状态管理

详见 `agent/STATE_MANAGEMENT.md`。

关键设计：
- **长期状态**：profile/memory/stats（持久化到文件）
- **跨局状态**：MatchContext 管理（本场统计）
- **运行时状态**：EpisodeContext（本局统计、帧缓存、结构化历史）
- **投影视图**：ContextStore + PromptProjector 负责预算驱动压缩与 prompt 生成
