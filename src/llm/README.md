# llm — LLM 牌手代理

让大语言模型作为牌手参与日式麻将对局。支持 OpenAI 兼容接口与 Anthropic API，提供实时观战、牌谱记录与回放功能。

## 安装

```bash
pip install -e ".[llm]"   # 基础 LLM 功能
pip install -e ".[rich]"  # LLM + 终端观战（推荐）
pip install pyyaml         # YAML 配置支持
```

依赖：`httpx`、`python-dotenv`、`pyyaml`。

## 环境变量

在仓库根目录运行时会自动加载 `.env` 文件（不覆盖已 export 的变量）。

| 变量 | 说明 |
|------|------|
| `AIMA_LLM_PROVIDER` | `openai`（默认）或 `anthropic` |
| `AIMA_OPENAI_API_KEY` | OpenAI 兼容端密钥 |
| `AIMA_OPENAI_BASE_URL` | 默认 `https://api.openai.com/v1` |
| `AIMA_OPENAI_MODEL` | 默认 `gpt-4o-mini` |
| `AIMA_ANTHROPIC_API_KEY` | Anthropic 密钥 |
| `AIMA_ANTHROPIC_BASE_URL` | 默认 `https://api.anthropic.com` |
| `AIMA_ANTHROPIC_MODEL` | 默认 `claude-3-5-haiku-20241022` |
| `AIMA_OPENAI_API_KEY_SEAT0` … `SEAT3` | 可选：为特定座位指定不同密钥 |
| `AIMA_LLM_TIMEOUT_SEC` | 默认 `120` |
| `AIMA_LLM_MAX_TOKENS` | 默认 `1024` |

仓库根目录 `.env.example` 提供模板；**勿将真实密钥提交版本库**。

## 命令行使用

### 使用配置文件（推荐）

```bash
# 正式对局（实时观战 + 自动记录）
python -m llm --config configs/watch_mode.yaml

# 快速测试（Dry-run，无需 API Key）
python -m llm --config configs/quick_test.yaml

# CLI 覆盖配置参数
python -m llm --config configs/watch_mode.yaml --seed 100 --max-player-steps 800
```

### 配置文件说明

配置文件位于 `configs/` 目录：

| 配置文件 | 用途 |
|---------|------|
| `default.yaml` | 完整参考模板（所有选项及枚举值注释） |
| `watch_mode.yaml` | **正式对局**（观战 + 自动记录日志） |
| `quick_test.yaml` | 快速测试（dry-run，无 API 调用） |

**配置结构**：

```yaml
match:
  seed: 42                    # 整数 (0 ~ 2^31-1)
  max_player_steps: 500       # 正整数（玩家决策步数）

llm:
  timeout_sec: 120            # 正数 (30-300)
  max_tokens: 1024            # 正整数 (512-2048)
  request_delay: 0.5          # 非负数（每次请求间隔）
  max_history_rounds: 10      # 非负整数 (0=禁用历史)
  clear_history_per_hand: false   # 新一局是否清空历史

logging:
  session: ""                 # null | "" | "自定义名称"
  json: null                  # null | "path/to/file.json"
  session_audit: true         # true/false

watch:
  enabled: true               # true/false
  delay: 0.5                  # 非负数（观战延迟）
  show_reason: true           # true/false（显示模型思考）

debug:
  verbose: false              # true/false
  dry_run: false              # true/false（随机演示，不调用 API）
```

**优先级**：CLI 参数 > YAML 配置 > 代码默认值

### 传统 CLI 方式（向后兼容）

```bash
# Dry-run 模式（随机演示，无需 API Key）
python -m llm --watch --dry-run --seed 0 --max-player-steps 200

# 真实 LLM 对局（需配置 API Key）
python -m llm --watch --seed 1 --max-player-steps 300

# 调整观战速度
python -m llm --watch --dry-run --seed 0 --watch-delay 0.5
```

### 从牌谱回放

```bash
python -m llm --watch --replay logs/replay/xxx.json --watch-delay 0.2
```

### 生成日志（后台模式）

```bash
# 生成对局日志
python -m llm --config configs/quick_test.yaml --log-session my_run_01

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
- `--max-player-steps INT` - 最大玩家决策步数
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
            max_player_steps=500,
            client=client,
            on_step_callback=callback.on_step
        )
```

## 测试

```bash
pip install -e ".[dev,llm]"
pytest tests/test_llm_*.py -q
```
