# AIma

日式麻将（四麻半庄向）对局内核 + LLM 牌手编排。**规则只在代码里裁决**；人类可读规则清单见 `mahjong_rules/Mahjong_Soul.md`（不参与运行时）。

## 仓库布局

| 路径 | 说明 |
|------|------|
| `src/kernel/` | 日麻内核：状态机、`apply`、流局、点数、`legal_actions` / `observation` 等 |
| `src/llm/` | 大模型适配：HTTP、提示拼装、解析校验、`run_llm_match` CLI（`python -m llm`） |
| `src/ui/` | **Rich 终端实时观战**（推荐） |
| `assets/docs/` | 架构与对外 API 说明（给 AI / 编排层） |
| `mahjong_rules/` | 规则子集 v1 对照（版本号以文件内为准） |
| `configs/` | **YAML 配置文件**（推荐用法） |

**依赖方向**：`llm` / `ui` → `kernel`；**禁止** `kernel` import `llm`。

**配置规范**：所有运行时配置统一通过 YAML 文件管理（`configs/*.yaml`），不再新增零散 CLI 参数或硬编码常量。

## 快速开始

### 1. 环境准备

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[rich]"
```

### 2. 使用配置文件运行（推荐）

```bash
# 正式对局（实时观战 + 自动记录）
python -m llm --config configs/watch_mode.yaml

# 快速测试（Dry-run，无需 API Key）
python -m llm --config configs/quick_test.yaml

# CLI 覆盖配置参数
python -m llm --config configs/watch_mode.yaml --seed 100 --max-steps 800
```

### 3. 传统 CLI 方式（向后兼容）

**Dry-run 模式**（随机演示，无需 API Key）：
```bash
python -m llm --watch --dry-run --seed 42 --max-steps 100 --watch-delay 0.3
```

**真实 AI 对局**（需要配置 API Key）：
```bash
# 配置环境变量
export AIMA_OPENAI_API_KEY="your-key"
python -m llm --watch --seed 42 --max-steps 100 --watch-delay 0.5
```

### 4. 从牌谱回放

```bash
python -m llm --watch --replay logs/replay/xxx.json --watch-delay 0.2
```

## 配置文件说明

配置文件位于 `configs/` 目录，所有配置项均带枚举值注释：

| 配置文件 | 用途 |
|---------|------|
| `default.yaml` | 完整参考模板（所有选项及注释） |
| `watch_mode.yaml` | **正式对局**（观战 + 自动记录日志） |
| `quick_test.yaml` | 快速测试（dry-run，无 API 调用） |

**配置结构示例**（`configs/watch_mode.yaml`）：

```yaml
match:
  seed: 42                    # 整数 (0 ~ 2^31-1)
  max_player_steps: 500       # 正整数（玩家决策步数，不含局间洗牌和自动过）

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
- `--max-player-steps INT` - 最大玩家决策步数（不含局间洗牌和自动过）
- `--log-session [STEM]` - 生成日志文件
- `--replay PATH` - 从牌谱回放

## 环境变量

| 变量 | 说明 |
|------|------|
| `AIMA_OPENAI_API_KEY` | OpenAI API Key |
| `AIMA_OPENAI_BASE_URL` | 自定义 API 端点（可选） |
| `AIMA_OPENAI_MODEL` | 模型名称（默认 gpt-4o-mini） |
| `AIMA_ANTHROPIC_API_KEY` | Anthropic API Key |
| `AIMA_ANTHROPIC_MODEL` | 模型名称（默认 claude-3-5-haiku） |

## 测试与检查

```bash
pytest
ruff check .
ruff format .
```

## 延伸阅读

- 内核模块划分与状态流：`assets/docs/kernel-architecture.md`
- 观测 / 合法动作 / `apply` 集成：`assets/docs/kernel-api-for-ai.md`
- LLM 包说明：`src/llm/README.md`
