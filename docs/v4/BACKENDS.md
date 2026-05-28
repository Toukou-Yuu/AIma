# v4.0 Backend 文档

## 概述

v4.0 支持多种模型后端用于 LLM Agent 决策。

---

## Backend 类型

| Backend | 状态 | 用途 |
|---------|------|------|
| openai_compatible | ✅ | OpenAI/DeepSeek/本地模型服务 |
| dummy | ✅ | 测试用假响应 |
| mock | ✅ | 预设响应序列 |
| replay | ✅ | 从牌谱回放决策 |
| llama_cpp | ❌ Stub | v4.3+ 实现 |
| vllm_native | ❌ Stub | v4.3+ 实现 |

---

## OpenAI-Compatible Backend

用于接入任何兼容 OpenAI API 的服务：

```yaml
model:
  backend: openai_compatible
  endpoint: https://api.openai.com/v1
  model_name: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.1
  max_tokens: 256
```

### 支持的服务

| 服务 | Endpoint |
|------|----------|
| OpenAI | https://api.openai.com/v1 |
| DeepSeek | https://api.deepseek.com/v1 |
| 本地 llama.cpp | http://localhost:8080/v1 |
| 本地 vLLM | http://localhost:8000/v1 |

### 本地模型接入方式

**不使用 native backend**，而是启动 OpenAI-compatible server：

```bash
# llama.cpp
llama-server -m model.gguf --port 8080

# vLLM
vllm serve model_name --port 8000
```

然后配置：

```yaml
model:
  backend: openai_compatible
  endpoint: http://localhost:8080/v1
  model_name: local
```

---

## Dummy Backend

返回固定假响应，用于测试 fallback 机制：

```yaml
model:
  backend: dummy
  model_name: dummy
  extra:
    response: "not json; force fallback"
```

---

## Mock Backend

返回预设响应序列，用于单元测试：

```yaml
model:
  backend: mock
  extra:
    responses:
      - '{"action": "打一万"}'
      - '{"action": "立直"}'
```

---

## Replay Backend

从已有牌谱回放决策，用于复现实验：

```yaml
model:
  backend: replay
  extra:
    replay_path: runs/smoke/jobs/abc123/replay.json
```

---

## Native Backend（v4.3+）

v4.0 **不实现** native llama.cpp/vLLM backend。

原因：
- OpenAI-compatible server 更通用
- native 需要额外依赖管理
- v4.2 论文实验优先使用标准 API

若尝试使用会收到 NotImplementedError：

```yaml
model:
  backend: llama_cpp  # NotImplementedError
```

---

## 配置字段

| 字段 | 类型 | 说明 |
|------|------|------|
| backend | str | 后端类型 |
| model_name | str | 模型名称 |
| endpoint | str | API endpoint（openai_compatible必填） |
| api_key_env | str | 环境变量名（openai_compatible必填） |
| temperature | float | 温度参数 |
| max_tokens | int | 最大输出token |
| extra | dict | 后端特定参数 |