# LLM 模块 — 大语言模型编排与角色系统

将麻将内核与 LLM 对接，实现 AI 牌手对局。

## 目录结构

```
src/llm/
├── __main__.py           # CLI 入口
├── cli.py                # 命令行解析与对局启动
├── runner.py             # 对局主循环（run_llm_match）
├── config.py             # 配置加载
├── protocol.py           # HTTP 客户端抽象（OpenAI/Anthropic）
├── agent/                # Agent 系统（详见 STATE_MANAGEMENT.md）
│   ├── __init__.py       # PlayerAgent（协调类）
│   ├── core.py           # AgentCore（决策逻辑）
│   ├── prompt.py         # PromptProjector（上下文投影）
│   ├── context_store.py  # ContextStore（自家历史 + 压缩）
│   ├── event_journal.py  # MatchJournal（公共事件流）
│   ├── token_budget.py   # token 预算与压缩规划
│   ├── decision_parser.py # 决策解析
│   ├── persistence.py    # 持久化管理
│   ├── match_context.py  # MatchContext（跨局状态）
│   ├── context.py        # EpisodeContext（运行时上下文）
│   ├── memory.py         # PlayerMemory + EpisodeSummarizer
│   ├── stats.py          # PlayerStats + MatchStats
│   ├── profile.py        # PlayerProfile
│   └── STATE_MANAGEMENT.md # 状态管理架构文档
├── observation_format.py # 观测格式化（自然语言）
├── validate.py           # 决策校验与匹配
├── parse.py              # JSON 解析
├── wire.py               # 动作序列化
└── action_build.py       # LegalAction → Action
```

## 设计原则

1. **Agent 是无状态纯函数**：只保留长期状态（profile/memory/stats），运行时状态由外部管理。
2. **单向依赖**：`llm → kernel`，禁止 `kernel` import `llm`。
3. **规则在代码里**：LLM 只是操作端，不能改写规则或偷看隐藏信息。

## 职责边界

- **做**：HTTP 请求封装（OpenAI/Anthropic）；将 `observation` + `legal_actions` 格式化为模型输入；解析 JSON 校验后映射为 `Action`；多 seat 编排、CLI、日志。
- **不做**：改写牌山/手牌或绕过 `apply`；判定和了番符/流局条件（一律委托 `kernel`）。
- **依赖**：`llm → kernel`（单向）。

## 核心组件

| 组件 | 职责 |
|------|------|
| `PlayerAgent` | 协调类，组合各组件，提供 `decide()` 接口 |
| `MatchContext` | 跨局状态管理（Context Object + Factory Pattern） |
| `EpisodeContext` | 运行时上下文（本局统计、决策历史） |
| `PromptProjector` | 按"长期状态 + 本地上下文窗口 + 当前观测"投影 Prompt |

状态管理的完整架构（状态分类、数据流、LocalContextPolicy 语义）见 `agent/STATE_MANAGEMENT.md`。

## 配置

配置文件为 `configs/aima_kernel.yaml`（已 gitignore），模板见 `configs/aima_kernel_template.yaml`。

关键配置项：

```yaml
llm:
  prompt_format: natural        # natural（中文自然语言）或 json
  context_scope: per_hand       # stateless / per_hand / per_match
  compression_level: collapse   # none / snip / micro / collapse / autocompact
  history_budget: 10
  profiles:                     # LLM 连接配置
    default:
      provider: openai
      api_key: "your-key"
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o-mini"
  seats:                        # 座位 → profile 绑定
    seat0: { profile: default }
    seat1: { profile: default }
    seat2: { profile: default }
    seat3: { profile: default }

players:                        # 角色 → 座位绑定
  - id: ichihime
    seat: 0
```

每个角色在 `configs/players/{id}/` 下有 `profile.json`（人格）、`memory.json`（记忆，gitignore）、`stats.json`（统计，gitignore）。

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
- `logs/replay/{timestamp}.json` — 完整牌谱（replay_json）
- `logs/debug/{timestamp}.log` — 调试日志
- `logs/simple/{timestamp}.txt` — 可读文本日志
