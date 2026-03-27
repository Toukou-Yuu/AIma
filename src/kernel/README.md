# kernel — 日麻对局内核

本目录包含**牌桌规则与状态机**实现（摸打、鸣牌、杠、立直、流局、点数、局/比赛流等），**不**包含大模型 HTTP 调用。

- **人类可读规则清单**（不参与裁决）：仓库根目录 `mahjong_rules/` 下 Markdown，版本以文件内为准。
- **架构与状态流**（给维护者/编排层）：`assets/docs/kernel-architecture.md`。
- **对外 API**（观测 / 合法动作 / `apply`）：`assets/docs/kernel-api-for-ai.md`。
- **本包目录索引**：[`docs/layout.md`](docs/layout.md)；各子包另有 `README.md`。
- **荒牌流局·流し満貫**：`BoardState` 记录各家完整舍牌与被鸣下标；`flow/settle.py` 与 `scoring/points.nagashi_mangan_payments` 实现判定与点棒（与满贯自摸分摊一致）。人类可读条文见 `mahjong_rules/Mahjong_Soul.md` §9。

## 相关代码

| 目录 | 说明 |
|------|------|
| `src/llm/` | 大模型编排，仅通过 `kernel.api` + `apply` 接入 |
| `src/ui/` | 终端 PNG 桌面渲染 |
| `src/web/` | HTTP API + 浏览器 UI |
