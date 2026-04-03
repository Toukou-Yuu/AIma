# llm — 大模型调用与编排

本包实现 **HTTP 适配、观测与合法动作的提示拼装、模型输出解析与校验、``apply`` 闭环跑局**。**牌桌规则与状态机仅在 `kernel`**；本包通过 `legal_actions` / `observation(..., mode="human")` / `apply` 接入，**禁止**改写内核状态或绕过校验。

> **配置规范**：所有运行时配置统一通过 **YAML 配置文件** 管理（`configs/*.yaml`），不再新增零散 CLI 参数或硬编码常量。

## 目录索引

| 模块 | 说明 |
|------|------|
| [`config.py`](config.py) | 从环境变量/YAML 读取 API Key、base URL、model、超时等 |
| [`protocol.py`](protocol.py) | `ChatMessage`、`CompletionClient` 协议、`build_client` |
| [`adapters/openai_chat.py`](adapters/openai_chat.py) | OpenAI 兼容 `POST .../chat/completions`（`httpx`） |
| [`adapters/anthropic_messages.py`](adapters/anthropic_messages.py) | Anthropic `POST .../v1/messages` |
| [`wire.py`](wire.py) | 牌码 / 副露 / 动作 wire 与 `kernel` 类型互转（不依赖 `web`） |
| [`observation_format.py`](observation_format.py) | 观测与 `legal_actions` → 提示用 JSON 文本 |
| [`parse.py`](parse.py) | 从模型原文中提取 JSON 对象 |
| [`validate.py`](validate.py) | 解析结果与当前 `legal_actions` 逐项匹配 |
| [`action_build.py`](action_build.py) | `LegalAction` → `Action` |
| [`turns.py`](turns.py) | 当前待决策的 `seat` 列表（`CALL_RESPONSE` 为多席） |
| [`runner.py`](runner.py) | `run_llm_match`：局间 `NOOP`+牌山、步数上限；支持实时观战回调 |
| [`table_snapshot_text.py`](table_snapshot_text.py) | 全桌「读谱式」纯文本快照（简体中文） |
| [`simple_log.py`](simple_log.py) | `--log-session` 时与内核事件配套的块级追加（调试用） |
| [`cli.py`](cli.py) / [`__main__.py`](__main__.py) | `python -m llm` |

## 安装

```bash
pip install -e ".[llm]"   # 仅 LLM 功能
pip install -e ".[rich]"  # LLM + 终端观战（推荐）
pip install pyyaml         # YAML 配置支持
```

依赖为 `httpx`、`python-dotenv`、`pyyaml`；与 `kernel` 共用同一仓库时确保 `pythonpath` 含 `src`（可编辑安装已配置）。

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

### 使用配置文件（推荐）

```bash
# 正式对局（实时观战 + 自动记录）
python -m llm --config configs/watch_mode.yaml

# 快速测试（Dry-run，无需 API Key）
python -m llm --config configs/quick_test.yaml

# CLI 覆盖配置参数
python -m llm --config configs/watch_mode.yaml --seed 100 --max-steps 800
```

### 配置文件说明

配置文件位于 `configs/` 目录：

| 配置文件 | 用途 |
|---------|------|
| `default.yaml` | 完整参考模板（所有选项及枚举值注释） |
| `watch_mode.yaml` | **正式对局**（观战 + 自动记录日志） |
| `quick_test.yaml` | 快速测试（dry-run，无 API 调用） |

**配置结构**（所有配置项均带枚举值注释）：

```yaml
match:
  seed: 42                    # 整数 (0 ~ 2^31-1)
  max_steps: 500              # 正整数

llm:
  timeout_sec: 120            # 正数 (30-300)
  max_tokens: 1024            # 正整数 (512-2048)
  request_delay: 0.5          # 非负数
  max_history_rounds: 10      # 非负整数 (0=禁用历史)
  clear_history_per_hand: false   # true/false

logging:
  session: ""                 # null | "" | "自定义名称"
  json: null                  # null | "path/to/file.json"
  session_audit: true         # true/false

watch:
  enabled: true               # true/false
  delay: 0.5                  # 非负数
  show_reason: true           # true/false

debug:
  verbose: false              # true/false
  dry_run: false              # true/false
```

**优先级**：CLI 参数 > YAML 配置 > 代码默认值

### 传统 CLI 方式（向后兼容）

```bash
# Dry-run 模式（随机演示，无需 API Key）
python -m llm --watch --dry-run --seed 0 --max-steps 200

# 真实 LLM 对局（需配置 API Key）
python -m llm --watch --seed 1 --max-steps 300

# 调整观战速度
python -m llm --watch --dry-run --seed 0 --watch-delay 0.5
```

### 从牌谱回放

```bash
python -m llm --watch --replay logs/replay/xxx.json --watch-delay 0.2
```

### 生成日志（后台模式）

```bash
# 生成配对日志
python -m llm --config configs/quick_test.yaml --log-session my_run_01

# 或传统方式
python -m llm --dry-run --seed 0 --max-steps 100 --log-session my_run_01

# 生成的文件：
# logs/replay/my_run_01.json   - 完整牌谱
# logs/debug/my_run_01.log     - 调试日志
# logs/simple/my_run_01.txt    - 可读文本日志
```

### 完整 CLI 参考

```bash
python -m llm --help
```

常用参数：
- `--config PATH` - **YAML 配置文件路径（推荐）**
- `--watch` - 启用 Rich 实时观战
- `--watch-delay SEC` - 观战步间延迟（默认 0.3）
- `--dry-run` - 随机演示，不调用 API
- `--seed INT` - 洗牌种子
- `--max-steps INT` - 最大步数
- `--log-session [STEM]` - 生成日志文件
- `--replay PATH` - 从牌谱回放

## 程序调用

```python
from llm import build_client, load_llm_config, run_llm_match
from ui.terminal_rich import LiveMatchCallback

# 带实时观战的 LLM 对局
llm_cfg = load_llm_config()
if llm_cfg:
    client = build_client(llm_cfg)
    with LiveMatchCallback(delay=0.5) as callback:
        rr = run_llm_match(
            seed=42,
            max_steps=500,
            client=client,
            on_step_callback=callback.on_step
        )
```

## 测试

```bash
pip install -e ".[dev,llm]"
pytest tests/test_llm_*.py -q
```

## 说明

- 正式对局每位模型选手应使用 **`observation(..., mode="human")`**；不要用 `debug` 观测当选手输入。
- `legal_actions` 已枚举 `OPEN_MELD` / `ANKAN` / `SHANKUMINKAN`（与 `kernel.api.meld_candidates` 一致）；仍以 `apply` 为最终校验。
- **API 省调用**：某席 `legal_actions` **仅有** `pass_call` 时，`choose_legal_action` **不调用** `complete`，直接过（有 `RON`/鸣牌等其它选项时仍会请求模型）。
