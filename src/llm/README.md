# llm — 大模型调用与编排

本包实现 **HTTP 适配、观测与合法动作的提示拼装、模型输出解析与校验、``apply`` 闭环跑局**。  
**牌桌规则与状态机仅在 `kernel`**；本包通过 `legal_actions` / `observation(..., mode="human")` / `apply` 接入，**禁止**改写内核状态或绕过校验。

职责边界见 [`docs/scope.md`](docs/scope.md)。

## 目录索引

| 模块 | 说明 |
|------|------|
| [`config.py`](config.py) | 从环境变量读取 API Key、base URL、model、超时等 |
| [`protocol.py`](protocol.py) | `ChatMessage`、`CompletionClient` 协议、`build_client` |
| [`adapters/openai_chat.py`](adapters/openai_chat.py) | OpenAI 兼容 `POST .../chat/completions`（`httpx`） |
| [`adapters/anthropic_messages.py`](adapters/anthropic_messages.py) | Anthropic `POST .../v1/messages` |
| [`wire.py`](wire.py) | 牌码 / 副露 / 动作 wire 与 `kernel` 类型互转（不依赖 `web`） |
| [`observation_format.py`](observation_format.py) | 观测与 `legal_actions` → 提示用 JSON 文本 |
| [`parse.py`](parse.py) | 从模型原文中提取 JSON 对象 |
| [`validate.py`](validate.py) | 解析结果与当前 `legal_actions` 逐项匹配 |
| [`action_build.py`](action_build.py) | `LegalAction` → `Action` |
| [`turns.py`](turns.py) | 当前待决策的 `seat` 列表（`CALL_RESPONSE` 为多席） |
| [`runner.py`](runner.py) | `run_llm_match`：局间 `NOOP`+牌山、步数上限；可选简单日志 |
| [`table_snapshot_text.py`](table_snapshot_text.py) | 全桌「读谱式」纯文本快照（简体中文）；合并摸打时标本巡摸牌，主串去重 |
| [`simple_log.py`](simple_log.py) | `--log-session` 时与内核事件配套的块级追加（调试用） |
| [`cli.py`](cli.py) / [`__main__.py`](__main__.py) | `python -m llm` |

## 安装

```bash
pip install -e ".[llm]"
```

依赖为 `httpx` 与 `python-dotenv`；与 `kernel` 共用同一仓库时确保 `pythonpath` 含 `src`（可编辑安装已配置）。

## 环境变量

在**仓库根目录**运行 `python -m llm` 时，若已安装 `python-dotenv`（随 `[llm]` 一并安装），会自动从当前工作目录加载 `.env`，**不会覆盖**你已在 shell 里 export 的变量。

| 变量 | 说明 |
|------|------|
| `AIMA_LLM_PROVIDER` | `openai`（默认）或 `anthropic` |
| `AIMA_OPENAI_API_KEY` | OpenAI 兼容端密钥 |
| `AIMA_OPENAI_BASE_URL` | 默认 `https://api.openai.com/v1` |
| `AIMA_OPENAI_MODEL` | 默认 `gpt-4o-mini` |
| `AIMA_ANTHROPIC_API_KEY` | Anthropic 密钥 |
| `AIMA_ANTHROPIC_BASE_URL` | 默认 `https://api.anthropic.com` |
| `AIMA_ANTHROPIC_MODEL` | 默认 `claude-3-5-haiku-20241022` |
| `AIMA_OPENAI_API_KEY_SEAT0` … `SEAT3` | 可选：按席覆盖密钥 |
| `AIMA_LLM_TIMEOUT_SEC` | 默认 `120` |
| `AIMA_LLM_MAX_TOKENS` | 默认 `1024` |

仓库根目录 `.env.example` 提供键名模板；**勿将真实密钥提交版本库**。

## 命令行

```bash
# 不调用 API：每步取 legal_actions 首项（确定性调试）
python -m llm --dry-run --seed 0 --max-steps 200

# 需已配置环境变量与 pip install -e ".[llm]"
python -m llm --seed 1 --max-steps 300

# 牌谱：跑完后写入 JSON（含每步 Action wire + 内核事件镜像，可完整 replay_from_actions）
python -m llm --dry-run --seed 0 --max-steps 200 --log-json match.json

# 仅从牌谱 JSON 重放（不请求 API）
python -m llm --replay match.json

# 终端里看对局进度（每步 phase / 动作种类）；默认已压低 httpx 的 HTTP 访问 INFO
python -m llm --seed 0 --max-steps 300 -v

# 配对日志（项目根下）：对局牌谱 logs/replay/{STEM}.json + 调试文本 logs/debug/{STEM}.log
python -m llm --dry-run --seed 0 --max-steps 100 --log-session
python -m llm --dry-run --seed 0 --max-steps 100 --log-session my_run_01
```

**日志目录约定**（需在仓库根执行，以便 `logs/` 落在项目根；目录已在 `.gitignore` 中忽略）：

| 路径 | 内容 |
|------|------|
| `logs/replay/{stem}.json` | **整局结束后**一次性写入：供 `replay_from_actions` 的 `actions` + 内核事件 `events` wire（确定性回放，非战报） |
| `logs/debug/{stem}.log` | **运行过程中**持续追加：`apply` 每步摘要、模型解析出的 `llm_choice`、仅写入本文件的 `httpx` HTTP 行（控制台仍隐藏） |
| `logs/simple/{stem}.txt` | **`--log-session`**：简体中文全桌快照 + 「执行」行；风位旁有绝对座位 **`(S0)`–`(S3)`**；合并摸打时先把本步打出张加回再标本巡摸牌，使摸后打前门内为 14 枚（与主串去重一致） |

`--log-session` 单独写可自动生成 `stem`（本地时间 `YYYYMMDD-HHMMSS`）；也可 `--log-session 自定义名`。仍可与 `--log-json 其它路径.json` 同时写入第二份牌谱。

牌谱 JSON 的设计目标是**确定性回放**；人类读谱优先看 `logs/simple/*.txt` 或 Web UI（`observation(..., human)`）。

牌谱字段与编解码见内核模块 `kernel.replay_json`；`RunResult.as_match_log()` 可程序化得到与 `--log-json` 相同结构的 dict。

## 程序调用

```python
from llm import build_client, load_llm_config, run_llm_match

cfg = load_llm_config()
if cfg:
    client = build_client(cfg)
    rr = run_llm_match(seed=42, max_steps=500, client=client)
else:
    rr = run_llm_match(seed=42, max_steps=500, dry_run=True)
```

## 测试

```bash
pip install -e ".[dev,llm]"
pytest tests/test_llm_*.py -q
```

## 下一阶段（编排层）

维护者约定的**近期优先事项**（与 `AGENTS.md` / `idea.md` 同步）：

1. **优化日志**：`logs/simple`、`logs/debug` 的可读性、噪声与体积控制。
2. **可视化指标**：token 用量、HTTP 请求次数、按 seat/局次聚合等（便于观战或批跑分析）。
3. **LLM 记忆化**：在公平对局与调试隔离前提下，探索上下文缓存或压缩策略。
4. **架构检查**：`llm` 与 `kernel` 的分层、`runner`/CLI 职责、观测→解析→校验→`apply` 管线一致性。

## 说明

- 正式对局每位模型选手应使用 **`observation(..., mode="human")`**；不要用 `debug` 观测当选手输入。
- `legal_actions` 已枚举 `OPEN_MELD` / `ANKAN` / `SHANKUMINKAN`（与 `kernel.api.meld_candidates` 一致）；仍以 `apply` 为最终校验。
- **API 省调用**：某席 `legal_actions` **仅有** `pass_call` 时，`choose_legal_action` **不调用** `complete`，直接过（有 `RON`/鸣牌等其它选项时仍会请求模型）。
