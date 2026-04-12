# AIma

让大语言模型打日式麻将。支持四位魂天神社角色（一姬、八木唯、卡维、藤田佳奈）实时对战，提供 Rich 终端观战、牌谱记录与回放。

## 快速开始

### 1. 环境准备

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[rich,llm]"
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
# 启动交互式终端（推荐）
python -m ui.interactive

# 快速测试（Dry-run，无需 API Key）
python -m llm --dry-run --seed 42

# 实际对局（需要 API Key）
python -m llm --config configs/aima_kernel.yaml

# 四位魂天神社角色对战
python -m llm --config configs/player_battle.yaml
```

## 四位角色

| 座位 | 名字 | 性格 | 口头禅 |
|------|------|------|--------|
| 东 | 一姬 | 活泼猫耳巫女 | "喵~大胜利！" |
| 南 | 八木唯 | 冷淡天才 | "...我不明白" |
| 西 | 卡维 | 神秘占卜师 | "命运无法改变" |
| 北 | 藤田佳奈 | 元气偶像 | "牌效好麻烦喵" |


## Prompt 格式

采用**中文自然语言格式**，LLM 更易理解，节省约 70% token：

```
【手牌】(13张)
万子: 一万 三万 五万 六万 八万
筒子: 四筒 五筒 五筒(赤) 七筒 七筒
索子: 一索
字牌: 东 西西 中

【可选动作】
打一万, 打三万, 打五万...
```

LLM 输出格式：
```json
{"action": "打三万", "why": "孤立牌，进张面窄"}
```

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

## 交互式终端

启动图形化菜单界面：

```bash
python -m ui.interactive
```

功能：
- 🎮 **快速开始** - Dry-run 演示，无需 API Key
- 🀄 **开始对局** - 选择4位玩家进行对战
- 👤 **角色管理** - 查看/创建角色（支持4种人格模板）
- 📺 **牌谱回放** - 回放历史对局

创建角色时可选人格模板：进攻型、防守型、平衡型、变化型。

## 常用命令

```bash
# Dry-run 快速测试（无需 API Key）
python -m llm --dry-run --seed 42

# 实际对局
python -m llm --kernel-config configs/aima_kernel.yaml

# 生成日志文件
python -m llm --log-session my_match

# 从牌谱回放
python -m llm --replay logs/replay/xxx.json

# 查看帮助
python -m llm --help
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

configs/players/               # 角色配置
  ichihime/profile.yaml        # 一姬人格配置
  yui/profile.yaml             # 八木唯人格配置
  kavi/profile.yaml            # 卡维人格配置
  kana/profile.yaml            # 膝田佳奈人格配置
  # memory.json, stats.json 已 gitignore

src/
  kernel/                      # 日麻规则内核（K0-K15 已完成）
  llm/                         # LLM 编排与 Agent 系统
    agent/                     # PlayerAgent + 状态管理组件
    README.md                  # LLM 模块文档
  ui/                          # 交互式终端与观战
```

## 开发

```bash
pip install -e ".[dev,llm]"
pytest tests/ -q
```

```bash
pip install -e ".[dev,llm]"
pytest tests/ -q
```
