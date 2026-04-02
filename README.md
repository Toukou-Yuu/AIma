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

**依赖方向**：`llm` / `ui` → `kernel`；**禁止** `kernel` import `llm`。

## 快速开始

### 1. 环境准备

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[rich]"
```

### 2. 实时观战（推荐）

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

### 3. 从牌谱回放

```bash
python -m llm --watch --replay logs/replay/xxx.json --watch-delay 0.2
```

### 4. 生成对局日志（后台模式）

```bash
# 不显示实时 UI，只生成日志文件
python -m llm --seed 42 --max-steps 200 --log-session my_match
```

生成文件：
- `logs/simple/my_match.txt` - 可读文本日志
- `logs/replay/my_match.json` - 完整牌谱
- `logs/debug/my_match.log` - 调试日志

## CLI 参数说明

```bash
python -m llm --help
```

常用参数：
- `--watch` - 启用 Rich 实时观战
- `--watch-delay SEC` - 观战每步间隔秒数（默认 0.3）
- `--dry-run` - 随机演示，不调用 LLM
- `--seed INT` - 洗牌种子
- `--max-steps INT` - 最大步数
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
