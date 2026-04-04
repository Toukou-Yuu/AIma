# llm — LLM 牌手代理

让大语言模型作为牌手参与日式麻将对局。支持 OpenAI 兼容接口与 Anthropic API，提供实时观战、牌谱记录与回放功能。

## 安装

```bash
pip install -e ".[llm]"   # 基础 LLM 功能
pip install -e ".[rich]"  # LLM + 终端观战（推荐）
pip install pyyaml         # YAML 配置支持
```

依赖：`httpx`、`pyyaml`。

## 快速开始

### 1. 创建配置文件

```bash
cp configs/aima_kernel_template.yaml configs/aima_kernel.yaml
```

编辑 `configs/aima_kernel.yaml`，填入你的 API Key：

```yaml
llm:
  provider: openai
  api_key: "sk-你的-api-key"      # 必填
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
  timeout_sec: 120.0
  max_tokens: 1024
```

支持任意 OpenAI 兼容接口（如 DeepSeek、本地 Ollama 等）。

### 2. 运行对局

```bash
# 四位魂天神社角色对战（实时观战）
python -m llm --config configs/player_battle.yaml

# 快速测试（Dry-run，无需 API Key）
python -m llm --config configs/quick_test.yaml
```

## 配置系统

### 内核配置（aima_kernel.yaml）

位于 `configs/aima_kernel.yaml`（已从 gitignore，不提交到仓库）：

```yaml
llm:
  provider: openai              # openai 或 anthropic
  api_key: "your-key"           # API 密钥
  base_url: "https://..."       # API 地址
  model: "gpt-4o-mini"          # 模型名称
  timeout_sec: 120.0
  max_tokens: 1024

players:                        # 默认玩家
  - id: ichihime     # 一姬（猫耳巫女）
    seat: 0
  - id: yui          # 八木唯（天才少女）
    seat: 1
  - id: kavi         # 卡维（占卜师）
    seat: 2
  - id: kana         # 藤田佳奈（偶像）
    seat: 3

logging:
  level: "INFO"
  file_output: true
```

### 对局配置（player_battle.yaml / quick_test.yaml）

```yaml
match:
  seed: 42
  max_player_steps: 500
  players:                      # 可选：覆盖默认玩家
    - id: ichihime
      seat: 0
    - id: yui
      seat: 1

logging:
  session: ""                   # 生成时间戳命名的日志
  session_audit: true

watch:
  enabled: true
  delay: 0.5
  show_reason: true             # 显示决策理由

debug:
  dry_run: false
```

## 四位角色

| 座位 | ID | 名字 | 性格 | 口头禅 |
|------|-----|------|------|--------|
| 东 | ichihime | 一姬 | 活泼猫耳巫女 | "喵~大胜利！" |
| 南 | yui | 八木唯 | 冷淡天才 | "...我不明白" |
| 西 | kavi | 卡维 | 神秘占卜师 | "命运无法改变" |
| 北 | kana | 藤田佳奈 | 元气偶像 | "牌效好麻烦喵" |

每位角色有独特的说话风格和决策理由表现。

## 命令行使用

### 使用配置文件（推荐）

```bash
# 正式对局（实时观战）
python -m llm --config configs/player_battle.yaml

# 快速测试（Dry-run）
python -m llm --config configs/quick_test.yaml

# 生成日志
python -m llm --config configs/player_battle.yaml --log-session my_match

# 指定内核配置
python -m llm --config configs/player_battle.yaml --kernel-config configs/my_kernel.yaml
```

### 从牌谱回放

```bash
python -m llm --watch --replay logs/replay/xxx.json --watch-delay 0.2
```

### 生成日志

设置 `logging.session: ""` 会自动生成时间戳命名的日志：

- `logs/replay/20260405-120000.json` - 完整牌谱
- `logs/debug/20260405-120000.log` - 调试日志
- `logs/simple/20260405-120000.txt` - 可读文本日志

## 程序调用

```python
from llm.config import load_llm_config, load_match_config
from llm import build_client, run_llm_match
from ui.terminal_rich import LiveMatchCallback

# 加载配置
llm_cfg = load_llm_config()
match_cfg = load_match_config("configs/player_battle.yaml")

if llm_cfg:
    client = build_client(llm_cfg)
    with LiveMatchCallback(delay=0.5) as callback:
        rr = run_llm_match(
            seed=match_cfg.seed,
            max_player_steps=match_cfg.max_player_steps,
            client=client,
            players=match_cfg.players,
            on_step_callback=callback.on_step
        )
```

## 测试

```bash
pip install -e ".[dev,llm]"
pytest tests/test_llm_*.py -q
```

## 目录结构

```
configs/
  aima_kernel_template.yaml    # 配置模板（提交到仓库）
  aima_kernel.yaml             # 你的配置（gitignore）
  player_battle.yaml           # 四位角色对战配置
  quick_test.yaml              # 快速测试配置

logs/
  replay/                      # 牌谱 JSON
  debug/                       # 调试日志
  simple/                      # 可读文本日志

configs/players/               # 角色配置
  ichihime/                    # 一姬
  yui/                         # 八木唯
  kavi/                        # 卡维
  kana/                        # 藤田佳奈
```
