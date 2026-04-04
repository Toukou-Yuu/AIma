# AIma

让大语言模型打日式麻将。支持四位魂天神社角色（一姬、八木唯、卡维、藤田佳奈）实时对战，提供 Rich 终端观战、牌谱记录与回放。

## 快速开始

### 1. 环境准备

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[rich]"
```

### 2. 创建配置文件

```bash
cp configs/aima_kernel_template.yaml configs/aima_kernel.yaml
```

编辑 `configs/aima_kernel.yaml`，填入你的 API Key：

```yaml
llm:
  provider: openai
  api_key: "sk-你的-api-key"      # 必填：填入你的 API Key
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
```

支持任意 OpenAI 兼容接口（DeepSeek、本地 Ollama 等）。

### 3. 运行对局

```bash
# 四位魂天神社角色对战（实时观战）
python -m llm --config configs/player_battle.yaml

# 快速测试（Dry-run，无需 API Key）
python -m llm --config configs/quick_test.yaml
```

## 四位角色

| 座位 | 名字 | 性格 | 口头禅 |
|------|------|------|--------|
| 东 | 一姬 | 活泼猫耳巫女 | "喵~大胜利！" |
| 南 | 八木唯 | 冷淡天才 | "...我不明白" |
| 西 | 卡维 | 神秘占卜师 | "命运无法改变" |
| 北 | 藤田佳奈 | 元气偶像 | "牌效好麻烦喵" |

## 配置说明

### 内核配置（aima_kernel.yaml）

```yaml
llm:
  provider: openai              # openai 或 anthropic
  api_key: "your-key"           # API 密钥（必填）
  base_url: "https://..."       # API 地址
  model: "gpt-4o-mini"          # 模型名称

players:                        # 默认玩家配置
  - id: ichihime     # 一姬
    seat: 0
  - id: yui          # 八木唯
    seat: 1
  - id: kavi         # 卡维
    seat: 2
  - id: kana         # 藤田佳奈
    seat: 3
```

### 对局配置（player_battle.yaml）

```yaml
match:
  seed: 42
  max_player_steps: 500

logging:
  session: ""           # 生成时间戳命名的日志
  session_audit: true

watch:
  enabled: true
  delay: 0.5
  show_reason: true     # 显示决策理由
```

## 常用命令

```bash
# 实时观战
python -m llm --config configs/player_battle.yaml

# 生成日志文件
python -m llm --config configs/player_battle.yaml --log-session my_match

# 从牌谱回放
python -m llm --watch --replay logs/replay/xxx.json

# 快速测试（无需 API Key）
python -m llm --config configs/quick_test.yaml
```

## 生成的日志

运行后自动生成：
- `logs/replay/{timestamp}.json` - 完整牌谱
- `logs/debug/{timestamp}.log` - 调试日志
- `logs/simple/{timestamp}.txt` - 可读文本日志

## 项目结构

```
configs/
  aima_kernel_template.yaml    # 配置模板
  aima_kernel.yaml             # 你的配置（gitignore）
  player_battle.yaml           # 四位角色对战配置
  quick_test.yaml              # 快速测试配置

configs/players/               # 角色配置
  ichihime/                    # 一姬（猫耳巫女）
  yui/                         # 八木唯（天才少女）
  kavi/                        # 卡维（占卜师）
  kana/                        # 藤田佳奈（偶像）

src/
  kernel/                      # 日麻规则内核
  llm/                         # LLM 编排与角色系统
  ui/                          # Rich 终端观战
```

## 详细文档

- [LLM 模块文档](src/llm/README.md) - LLM 编排、角色配置、API 说明
- [内核文档](src/kernel/README.md) - 日麻规则内核架构

## 开发

```bash
pip install -e ".[dev,llm]"
pytest tests/ -q
```
