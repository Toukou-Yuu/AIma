# AIma

日式麻将（四麻半庄向）对局内核 + LLM 牌手编排。**规则只在代码里裁决**；人类可读规则清单见 `mahjong_rules/Mahjong_Soul.md`（不参与运行时）。

## 仓库布局

| 路径 | 说明 |
|------|------|
| `src/kernel/` | 日麻内核：状态机、`apply`、流局、点数、`legal_actions` / `observation` 等 |
| `src/llm/` | 大模型适配：HTTP、提示拼装、解析校验、`run_llm_match` CLI（`python -m llm`） |
| `src/ui/` | 终端 PNG 桌面渲染原型 |
| `src/web/` | FastAPI + 浏览器 UI（见 `src/web/README.md`） |
| `assets/docs/` | 架构与对外 API 说明（给 AI / 编排层） |
| `mahjong_rules/` | 规则子集 v1 对照（版本号以文件内为准） |

**依赖方向**：`llm` / `web` → `kernel`；**禁止** `kernel` import `llm`。

## 环境

```bash
conda env create -f environment.yml
conda activate aima
pip install -e ".[dev]"
```

可选：`pip install -e ".[llm]"`（跑 LLM CLI）、`pip install -e ".[web]"`（Web）。

## 测试与检查

```bash
pytest
ruff check .
ruff format .
```

`pyproject.toml` 已配置 `pythonpath = src`。

## 延伸阅读

- 内核模块划分与状态流：`assets/docs/kernel-architecture.md`
- 观测 / 合法动作 / `apply` 集成：`assets/docs/kernel-api-for-ai.md`
- LLM 包说明：`src/llm/README.md`
