# llm 包职责边界

## 做

- OpenAI 兼容 / Anthropic 等协议的 HTTP 请求封装。
- 将 `kernel` 的 `observation(..., human)` 与 `legal_actions` 格式化为模型输入；解析 JSON（或约定格式）并校验后映射为 `Action`。
- 编排多 seat 决策顺序、`run_llm_match` 主循环、CLI 与可选日志（`logs/replay`、`logs/debug`、`logs/simple`）。
- `kernel.replay_json`：牌谱落盘与 `--replay` 重放。

## 不做

- 改写牌山、手牌或绕过 `apply`。
- 在此包内判定和了番符、流局条件（一律委托 `kernel`）。

## 依赖

**llm → kernel**（单向）。禁止 `kernel` import `llm`。
