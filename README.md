# AIma

让大语言模型打日式麻将。支持四位魂天神社角色（一姬、八木唯、卡维、藤田佳奈）实时对战，提供全屏终端 TUI、动态观战、牌谱记录与回放。

## 快速开始

### 1. 环境准备

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[rich,llm]"
```

`rich` 依赖组现在同时包含：
- `rich`：终端渲染
- `textual`：全屏 TUI 框架
- `questionary`：保留给旧交互/辅助逻辑

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

### 3. 启动程序

```bash
python start.py
```

启动后进入全屏终端 TUI 首页：
- 🎮 **demo演示** - Dry-run 快速演示，无需 API Key
- 🀄 **开始对局** - 选择 4 位玩家并配置局数、观战模式
- 👤 **角色管理** - 预览角色卡片、创建角色、添加 ASCII 形象
- 📺 **牌谱回放** - 浏览牌谱并进入动态回放

也可以直接进入 demo 配置页：

```bash
python start.py quick
```

说明：
- 观战页是自动刷新的全屏 live 画面
- 返回/退出等操作通过界面内按钮完成，不依赖 `Esc` / `Ctrl+C`
- 对局结束后会进入结算页，而不是直接回主菜单

创建角色时可选人格模板：进攻型、防守型、平衡型、变化型。

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

  # 对话日志配置（用于调试 LLM 上下文）
  conversation_logging:
    enabled: true               # 启用后记录完整对话到 configs/players/{player_id}/conversations/

players:                        # 默认玩家配置
  - id: ichihime     # 一姬
    seat: 0
  - id: yui          # 八木唯
    seat: 1
  - id: kavi         # 卡维
    seat: 2
  - id: kana         # 膝田佳奈
    seat: 3
```

## 生成的日志

运行后自动生成：
- `logs/replay/{timestamp}.json` - 完整牌谱
- `logs/debug/{timestamp}.log` - 调试日志
- `logs/simple/{timestamp}.txt` - 可读文本日志
- `configs/players/{player_id}/conversations/{date}-{session}.md` - LLM 对话日志（需启用 conversation_logging）

其中：
- `demo演示` 和正式对局结束后都可直接从结算页跳转到回放
- 回放也使用同一套全屏 TUI，而不是单独的命令行子进程

## 项目结构

```
configs/
  aima_kernel_template.yaml    # 配置模板
  aima_kernel.yaml             # 你的配置（gitignore）

configs/players/               # 角色配置
  ichihime/profile.json        # 一姬人格配置
  yui/profile.json             # 八木唯人格配置
  kavi/profile.json            # 卡维人格配置
  kana/profile.json            # 膝田佳奈人格配置
  conversations/               # LLM 对话日志（gitignore）

src/
  kernel/                      # 日麻规则内核（K0-K15 已完成）
  llm/                         # LLM 编排与 Agent 系统
    agent/                     # PlayerAgent + 状态管理组件
  ui/
    interactive/              # Textual 全屏 TUI
    terminal/                 # Rich 牌桌/角色卡片渲染组件
```

## 开发

```bash
pip install -e ".[dev,llm]"
pytest -q
```
