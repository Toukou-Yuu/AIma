# v4.0 配置 Schema 文档

## 配置层次结构

```yaml
experiment:     # 实验元信息
rules:          # 规则版本
seeds:          # 随机种子配置
match:          # 对局配置
runtime:        # 运行时配置
artifacts:      # 产物输出配置
memory:         # 记忆配置
policies:       # 策略配置（按座位）
```

---

## experiment（实验元信息）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | str | 必填 | 实验ID，用于生成runs/{id}目录 |
| description | str | "" | 实验描述 |
| tags | list[str] | [] | 实验标签 |

---

## rules（规则版本）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| version | str | 必填 | 规则版本标识 |
| scope_file | str | "RULE_SCOPE.md" | 规则边界文件路径 |

---

## seeds（随机种子）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| start | int | 0 | 起始种子值 |
| count | int | 1 | 生成种子数量 |
| explicit | list[int] | None | 显式指定种子列表（优先） |
| common_walls | bool | True | 所有match使用相同牌墙 |

---

## match（对局配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| preset | str | "hanchan" | 对局预设：tonpuu(东风战)/hanchan(半庄)/custom |
| max_hands | int | None | 最大局数截断上限（None=自然终局） |
| allow_negative | bool | False | 允许负分 |
| step_limit | int | 20000 | 单局最大步数（防死循环） |

### preset 说明

| preset | 自然终局条件 |
|--------|--------------|
| tonpuu | 东风战，4局或终局点数达到 |
| hanchan | 半庄战，8局或终局点数达到 |
| custom | 需显式设置max_hands |

---

## runtime（运行时配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mode | str | "serial" | 运行模式（目前仅支持serial） |
| debug_snapshots | bool | False | 是否保存debug snapshots |
| no_persist | bool | True | 不持久化到磁盘 |
| resume | bool | True | 支持从中断恢复 |
| fail_fast | bool | False | 首次失败即停止 |

---

## artifacts（产物配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| output_root | str | "runs" | 输出根目录 |
| save_replay | bool | True | 保存replay.json |
| save_events | bool | True | 保存events.jsonl |
| save_decisions | bool | True | 保存decisions.jsonl |
| save_prompts | bool | False | 保存prompt_messages.jsonl |
| save_debug_snapshots | bool | False | 保存debug snapshots |
| sqlite_index | bool | True | 生成SQLite索引 |

---

## memory（记忆配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mode | str | "off" | 模式：off/passive（注意YAML陷阱） |
| layers | list[str] | [] | 记忆层次：hand/match/persistent/opponent |
| store | str | "in_memory" | 存储方式：in_memory/json/sqlite |
| persist | bool | False | 跨session持久化 |

### YAML布尔陷阱

YAML 1.1 会把 `mode: off` 解析为 `False`。**必须加引号**：

```yaml
memory:
  mode: "off"     # 正确：字符串"off"
  # mode: off     # 错误：解析为布尔False
```

---

## policies（策略配置）

按座位配置策略，键名格式：`seat0`/`seat1`/`seat2`/`seat3`

### 策略类型

| type | 说明 |
|------|------|
| first_legal | 选择第一个合法动作 |
| random | 随机选择合法动作 |
| llm | LLM Agent决策 |

### first_legal 配置示例

```yaml
policies:
  seat0:
    type: first_legal
    id: baseline_0
```

### llm 配置示例

```yaml
policies:
  seat0:
    type: llm
    id: agent_0
    agent:
      pipeline_id: llm_fixed_v1
      context:
        scope: stateless
      memory:
        mode: "passive"
        layers: ["match"]
      prompt:
        template_id: riichi_json_action_v1
        version: "1.0.0"
      model:
        backend: openai_compatible
        endpoint: https://api.deepseek.com/v1
        model_name: deepseek-chat
        api_key_env: DEEPSEEK_API_KEY
      fallback: first_legal
```

---

## Agent 子配置

### agent.context

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scope | str | "stateless" | 上下文范围：stateless/per_turn/per_hand/per_match |
| compression | str | "none" | 压缩策略：none/snip/collapse/autocompact(实验性) |

### agent.memory

同顶层memory配置。

### agent.prompt

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| template_id | str | 必填 | Prompt模板ID |
| version | str | 必填 | 模板版本 |
| sections | list | [] | 启用的section列表 |

### agent.model

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| backend | str | 必填 | 后端类型 |
| endpoint | str | 必填 | API endpoint |
| model_name | str | 必填 | 模型名称 |
| api_key_env | str | 必填 | API密钥环境变量名 |
| temperature | float | 0.1 | 温度参数 |
| max_tokens | int | 256 | 最大输出token |

### agent.fallback

当LLM决策失败时的fallback策略：`first_legal` 或 `random`