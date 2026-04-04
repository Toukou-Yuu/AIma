# AIma

让大语言模型打日式麻将。支持 OpenAI 与 Anthropic API，提供实时终端观战、牌谱记录与回放。

## 快速开始

### 环境准备

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[rich]"
```

### 使用配置文件运行（推荐）

```bash
# 正式对局（实时观战 + 自动记录）
python -m llm --config configs/watch_mode.yaml

# 快速测试（Dry-run，无需 API Key）
python -m llm --config configs/quick_test.yaml

# CLI 覆盖配置参数
python -m llm --config configs/watch_mode.yaml --seed 100 --max-player-steps 800
```

### 传统 CLI 方式（向后兼容）

**Dry-run 模式**（随机演示，无需 API Key）：
```bash
python -m llm --watch --dry-run --seed 42 --max-player-steps 100 --watch-delay 0.3
```

**真实 AI 对局**（需要配置 API Key）：
```bash
# 配置环境变量
export AIMA_OPENAI_API_KEY="your-key"
python -m llm --watch --seed 42 --max-player-steps 100 --watch-delay 0.5
```

### 从牌谱回放

```bash
python -m llm --watch --replay logs/replay/xxx.json --watch-delay 0.2
```

## 配置文件说明

配置文件位于 `configs/` 目录：

| 配置文件 | 用途 |
|---------|------|
| `default.yaml` | 完整参考模板（所有选项及注释） |
| `watch_mode.yaml` | **正式对局**（观战 + 自动记录日志） |
| `quick_test.yaml` | 快速测试（dry-run，无 API 调用） |

**配置结构示例**（`configs/watch_mode.yaml`）：

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

## CLI 参数说明

```bash
python -m llm --help
```

常用参数：
- `--config PATH` - **YAML 配置文件路径（推荐）**
- `--watch` - 启用 Rich 实时观战
- `--watch-delay SEC` - 观战每步间隔秒数（默认 0.3）
- `--dry-run` - 随机演示，不调用 LLM
- `--seed INT` - 洗牌种子
- `--max-player-steps INT` - 最大玩家决策步数
- `--log-session [STEM]` - 生成日志文件
- `--replay PATH` - 从牌谱回放

## 环境变量

| 变量 | 说明 |
|------|------|
| `AIMA_LLM_PROVIDER` | `openai`（默认）或 `anthropic` |
| `AIMA_OPENAI_API_KEY` | OpenAI API Key |
| `AIMA_OPENAI_BASE_URL` | 自定义 API 端点（可选） |
| `AIMA_OPENAI_MODEL` | 模型名称（默认 gpt-4o-mini） |
| `AIMA_ANTHROPIC_API_KEY` | Anthropic API Key |
| `AIMA_ANTHROPIC_BASE_URL` | Anthropic API 端点（可选） |
| `AIMA_ANTHROPIC_MODEL` | 模型名称（默认 claude-3-5-haiku） |
| `AIMA_OPENAI_API_KEY_SEAT0` … `SEAT3` | 可选：为特定座位指定不同密钥 |
| `AIMA_LLM_TIMEOUT_SEC` | 请求超时秒数（默认 120） |
| `AIMA_LLM_MAX_TOKENS` | 最大生成长度（默认 1024） |

仓库根目录 `.env.example` 提供模板；**勿将真实密钥提交版本库**。
